"""
Simulation API Endpoints.
Uses Spatial-for-Temporal substitution to estimate rainfall sensitivity.
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
import asyncpg

from app.api.deps import get_db
from app.analytics.advanced import get_advanced_analyzer, SimulationResult
from app.ml.prediction_engine import PredictionEngine
from app.exceptions import NotFoundError, ValidationError

router = APIRouter()


class SimulationResponse(BaseModel):
    district: str
    state: str
    crop: str
    result: SimulationResult
    note: str
    validity: dict | None = None


@router.get("/", response_model=SimulationResponse)
async def get_simulation(
    district: str = Query(..., description="District Name"),
    crop: str = Query(..., description="Crop Name"),
    year: int = Query(..., description="Reference Year for Yield"),
    state: str = Query(..., description="State Name"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Get simulation model for Rainfall vs Yield.

    LIMITATION: Lacking historical rainfall time-series, we use SPATIAL regression.
    We regress Yield vs Rainfall Normals across all districts in the state.
    Slope = Sensitivity of yield to long-term rainfall differences.
    We apply this sensitivity to simulate "Deviation from Normal".
    """
    # Cache Key Generation
    cache_key = f"sim:{state}:{district}:{crop}:{year}"

    from app.cache import get_cache, CacheTTL
    cache = get_cache()
    cached_result = await cache.get(cache_key)
    if cached_result:
        return cached_result

    analyzer = get_advanced_analyzer()

    # 1. Fetch Yields for ALL districts in the state for the given year
    # 1. Fetch Yields for ALL districts in the state for the given year
    # We need to construct the variable name. Simulation usually runs on
    # "yield".
    variable_name = f"{crop.lower()}_yield"

    # Try total yield first
    yield_query = """
        SELECT d.district_name, m.value as yield
        FROM agri_metrics m
        JOIN districts d ON m.district_lgd = d.lgd_code
        WHERE UPPER(d.state_name) = UPPER($1)
        AND m.variable_name = $2
        AND m.year = $3
        AND m.value IS NOT NULL AND m.value > 0
    """
    yield_rows = await db.fetch(yield_query, state, variable_name, year)

    # Fallback to season-specific yield if total yield is missing
    if len(yield_rows) < 5:
        # Define season map
        season_map = {
            "rice": "kharif",
            "wheat": "rabi",
            "maize": "kharif",
            "soyabean": "kharif",
            "groundnut": "kharif"
        }
        season = season_map.get(crop.lower())
        if season:
            seasonal_variable = f"{crop.lower()}_yield_{season}"
            yield_rows = await db.fetch(yield_query, state, seasonal_variable, year)

    if len(yield_rows) < 5:
        # Fallback: Try average over last 5 years if single year is sparse?
        # For now, strict fail or maybe relax? Let's return empty result.
        raise NotFoundError(
            detail="Insufficient state data for spatial regression")

    # 2. Fetch Rainfall Normals for these districts
    # We can join or loop. Loop is easier given rainfall_service.py structure and likely small N (<50 districts).
    # But efficient approach: Query all rainfall for state.
    rain_query = """
        SELECT district, annual
        FROM rainfall_normals
        WHERE UPPER(state_ut) = UPPER($1)
    """
    rain_rows = await db.fetch(rain_query, state)
    rain_map = {r["district"].upper(): float(r["annual"] or 0)
                for r in rain_rows}

    # 3. Match Data (X=Rain, Y=Yield)
    rainfall_x = []
    yields_y = []
    years = []  # Dummy years (indices really)

    idx = 0
    for row in yield_rows:
        d_name = row["district_name"]
        d_yield = float(row["yield"])

        # Fuzzy match or exact? Try Exact Upper first.
        r_val = rain_map.get(d_name.upper())

        if r_val and r_val > 0:
            rainfall_x.append(r_val)
            yields_y.append(d_yield)
            years.append(idx)
            idx += 1

    if len(rainfall_x) < 5:
        raise NotFoundError(detail="Insufficient matching rainfall/yield data")

    # 4. Run Regression
    # We use the existing 'calculate_impact_simulation' which expects (rain, yield, years).
    # It calculates slope (kg/ha per mm).
    sim_result = analyzer.calculate_impact_simulation(
        rainfall_x, yields_y, years)

    # Override logic: 'calculate_impact_simulation' calculates a baseline based on MEAN rainfall.
    # We want to be able to simulate deviations from *target_district_rain*.

    # The slope is generic for the state.
    # Prediction = Intercept + Slope * Rain.

    result = SimulationResponse(
        district=district,
        state=state,
        crop=crop,
        result=sim_result,
        note="Spatial Regression Proxy: Sensitivity derived from cross-district comparison within state.",
        validity={
            "climate_assumption": "stationary",
            "baseline_period": "1951-2000",
            "warning": "Simulation based on historic climate normals. Not valid for real-time weather impact."
        }
    )

    # Cache Result
    await cache.set(cache_key, result, CacheTTL.ANALYSIS)
    return result


# ──────────────────────────────────────────────────────────────────────────────
# V2 — Multi-Factor Prediction Endpoint
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/v2")
async def get_prediction_v2(
    district: str = Query(..., description="District Name"),
    crop: str = Query(..., description="Crop Name"),
    year: int = Query(..., description="Reference Year"),
    state: str = Query(..., description="State Name"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    V2 Prediction: Multi-factor Ridge regression with full explainability.

    Gathers rainfall (with seasonal breakdown), historical yield trend,
    yield volatility, and crop area for every district in the state,
    then runs the PredictionEngine.
    """
    from app.cache import get_cache, CacheTTL

    cache_key = f"pred_v2:{state}:{district}:{crop}:{year}"
    cache = get_cache()
    cached = await cache.get(cache_key)
    if cached:
        return cached

    # 1. Resolve variable name (with season fallback)
    variable_name = f"{crop.lower()}_yield"
    yield_query = """
        SELECT d.district_name, m.value as yield
        FROM agri_metrics m
        JOIN districts d ON m.district_lgd = d.lgd_code
        WHERE UPPER(d.state_name) = UPPER($1)
        AND m.variable_name = $2
        AND m.year = $3
        AND m.value IS NOT NULL AND m.value > 0
    """
    yield_rows = await db.fetch(yield_query, state, variable_name, year)

    if len(yield_rows) < 5:
        season_map = {"rice": "kharif", "wheat": "rabi", "maize": "kharif",
                      "soyabean": "kharif", "groundnut": "kharif"}
        season = season_map.get(crop.lower())
        if season:
            variable_name = f"{crop.lower()}_yield_{season}"
            yield_rows = await db.fetch(
                yield_query, state, variable_name, year
            )

    if len(yield_rows) < 5:
        raise NotFoundError(detail="Insufficient yield data for prediction")

    # 2. Rainfall normals (with seasonal breakdown)
    rain_query = """
        SELECT district, annual, jjas
        FROM rainfall_normals
        WHERE UPPER(state_ut) = UPPER($1)
    """
    rain_rows = await db.fetch(rain_query, state)
    rain_map = {}
    for r in rain_rows:
        rain_map[r["district"].upper()] = {
            "annual": float(r["annual"] or 0),
            "monsoon_jjas": float(r["jjas"] or 0),
        }

    # 3. Historical yield data for each district (for trend & CV)
    hist_query = """
        SELECT d.district_name, m.year, m.value
        FROM agri_metrics m
        JOIN districts d ON m.district_lgd = d.lgd_code
        WHERE UPPER(d.state_name) = UPPER($1)
        AND m.variable_name = $2
        AND m.value IS NOT NULL AND m.value > 0
        ORDER BY d.district_name, m.year
    """
    hist_rows = await db.fetch(hist_query, state, variable_name)
    hist_map: dict = {}  # district_name -> [(year, value)]
    for r in hist_rows:
        dn = r["district_name"]
        hist_map.setdefault(dn, []).append((r["year"], float(r["value"])))

    # 4. Crop area
    area_var = f"{crop.lower()}_area"
    area_query = """
        SELECT d.district_name, m.value as area
        FROM agri_metrics m
        JOIN districts d ON m.district_lgd = d.lgd_code
        WHERE UPPER(d.state_name) = UPPER($1)
        AND m.variable_name = $2
        AND m.year = $3
        AND m.value IS NOT NULL AND m.value > 0
    """
    area_rows = await db.fetch(area_query, state, area_var, year)
    area_map = {r["district_name"].upper(): float(r["area"])
                for r in area_rows}

    # 5. Assemble district_data for PredictionEngine
    district_data = []
    for row in yield_rows:
        d_name = row["district_name"]
        d_yield = float(row["yield"])

        rain_info = rain_map.get(d_name.upper())
        if not rain_info or rain_info["annual"] <= 0:
            continue

        # Calculate trend & CV from historical yields
        hist = hist_map.get(d_name, [])
        yield_trend = 0.0
        yield_cv = 0.0
        if len(hist) >= 5:
            years_arr = [h[0] for h in hist]
            vals_arr = [h[1] for h in hist]
            import numpy as np
            from scipy import stats as sp_stats
            slope, _, _, _, _ = sp_stats.linregress(years_arr, vals_arr)
            yield_trend = float(slope)
            mean_v = np.mean(vals_arr)
            std_v = np.std(vals_arr, ddof=1)
            yield_cv = float((std_v / mean_v) * 100) if mean_v > 0 else 0.0

        entry = {
            "district": d_name,
            "yield_value": d_yield,
            "rainfall": rain_info["annual"],
            "monsoon_jjas": rain_info["monsoon_jjas"],
            "yield_trend": yield_trend,
            "yield_cv": yield_cv,
            "crop_area": area_map.get(d_name.upper(), 0),
        }
        district_data.append(entry)

    if len(district_data) < 5:
        raise NotFoundError(detail="Insufficient matched data for prediction")

    # 6. Run PredictionEngine
    engine = PredictionEngine()
    result = engine.predict(district_data, district)

    if result is None:
        raise ValidationError(detail="Prediction engine returned no result")

    response = {
        "district": district,
        "state": state,
        "crop": crop,
        "year": year,
        "prediction": result.to_dict(),
        "validity": {
            "climate_assumption": "stationary",
            "baseline_period": "1951-2000",
            "warning": "Prediction based on historic climate normals and cross-sectional spatial regression. Not valid for real-time weather impact."
        }
    }

    await cache.set(cache_key, response, CacheTTL.ANALYSIS)
    return response
