"""
Climate API endpoints: Rainfall data and correlation analysis.
Data served from database (populated via ETL from IMD API).
"""


import asyncpg
from fastapi import APIRouter, Depends, Query

from app.analytics import get_analyzer
from app.api.deps import get_db
from app.exceptions import NotFoundError
from app.services.rainfall_service import (
    get_all_rainfall,
    get_rainfall_by_district,
    get_rainfall_count,
    get_state_rainfall_stats,
    get_water_stress_index,
)

router = APIRouter()


@router.get("/rainfall/stats")
async def get_rainfall_db_stats(db: asyncpg.Connection = Depends(get_db)):
    """Get database statistics for rainfall data."""
    count = await get_rainfall_count(db)
    return {
        "source": "IMD 1951-2000 Normals (database)",
        "record_count": count,
        "status": "loaded" if count > 0 else "empty",
    }


@router.get("/rainfall")
async def get_rainfall(
    state: str = Query(..., description="State name", max_length=50),
    district: str = Query(..., description="District name", max_length=50),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get rainfall normals for a specific district.

    Returns monthly, seasonal, and annual rainfall data (1951-2000 normals).
    """
    rainfall = await get_rainfall_by_district(db, state, district)

    if not rainfall:
        return {"error": f"No rainfall data found for {district}, {state}"}

    return {
        "state": rainfall.state,
        "district": rainfall.district,
        "monthly": {
            "jan": rainfall.jan,
            "feb": rainfall.feb,
            "mar": rainfall.mar,
            "apr": rainfall.apr,
            "may": rainfall.may,
            "jun": rainfall.jun,
            "jul": rainfall.jul,
            "aug": rainfall.aug,
            "sep": rainfall.sep,
            "oct": rainfall.oct,
            "nov": rainfall.nov,
            "dec": rainfall.dec,
        },
        "seasonal": {
            "winter_jf": rainfall.winter_jf,
            "pre_monsoon_mam": rainfall.pre_monsoon_mam,
            "monsoon_jjas": rainfall.monsoon_jjas,
            "post_monsoon_ond": rainfall.post_monsoon_ond,
        },
        "annual": rainfall.annual,
        "source": "IMD 1951-2000 Normals",
    }


@router.get("/rainfall/all")
async def get_all_rainfall_data(
    state: str | None = Query(None, description="Filter by state", max_length=50),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get rainfall data for all districts (or filter by state).
    For map visualization.
    """
    data = await get_all_rainfall(db, state)
    return data


@router.get("/rainfall/state-stats")
async def get_state_stats(
    state: str = Query(..., description="State name", max_length=50),
    db: asyncpg.Connection = Depends(get_db),
):
    """Get aggregated rainfall statistics for a state."""
    return await get_state_rainfall_stats(db, state)


@router.get("/water-stress")
async def get_water_stress(
    state: str = Query(..., description="State name", max_length=50),
    year: int = Query(2020, description="Year to analyze (e.g., 2020)", ge=1950, le=2025),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get Water Stress Index (Mismatch Index) mapping water-intensive crops against annual rainfall.
    """
    results = await get_water_stress_index(db, state, year)
    if not results:
        raise NotFoundError(
            detail=f"Insufficient data to compute water stress for {state} in {year}")

    return {
        "state": state,
        "year": year,
        "districts": results,
        "validity": {
            "climate_assumption": "stationary",
            "baseline_period": "1951-2000",
            "warning": "Water stress mismatch index is based on historic annual rainfall normals. Not valid for current real-time drought assessment."
        }
    }


@router.get("/correlation")
async def get_rainfall_yield_correlation(
    state: str = Query(..., description="State name", max_length=50),
    crop: str = Query(..., description="Crop name", max_length=30),
    year: int = Query(..., description="Year to analyze", ge=1950, le=2025),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Calculate correlation between rainfall and yield for districts in a state.

    Compares annual/monsoon rainfall against district yields.
    """
    analyzer = get_analyzer()

    # Get yield data for state using the correct schema
    variable = f"{crop.lower()}_yield"
    yield_query = """
        SELECT d.district_name, m.value as yield_val
        FROM agri_metrics m
        JOIN districts d ON m.district_lgd = d.lgd_code
        WHERE UPPER(d.state_name) = UPPER($1) AND m.variable_name = $2 AND m.year = $3
        AND m.value IS NOT NULL AND m.value > 0
    """
    yield_rows = await db.fetch(yield_query, state, variable, year)

    # Fallback to seasonal
    if not yield_rows or len(yield_rows) < 5:
        season_map = {
            "rice": "kharif", "wheat": "rabi", "maize": "kharif",
            "soyabean": "kharif", "groundnut": "kharif", "cotton": "kharif",
        }
        season = season_map.get(crop.lower())
        if season:
            variable = f"{crop.lower()}_yield_{season}"
            yield_rows = await db.fetch(yield_query, state, variable, year)

    if not yield_rows or len(yield_rows) < 5:
        return {"error": "Insufficient yield data (need at least 5 districts)"}

    # Match with rainfall data
    matched_data = []
    for row in yield_rows:
        district_name = row["district_name"]
        rainfall = await get_rainfall_by_district(db, state, district_name)

        if rainfall:
            matched_data.append({
                "district": district_name,
                "yield": float(row["yield_val"]),
                "annual_rainfall": rainfall.annual,
                "monsoon_rainfall": rainfall.monsoon_jjas,
            })

    if len(matched_data) < 5:
        return {"error": f"Could not match sufficient districts with rainfall data ({len(matched_data)} found)"}

    # Calculate correlations
    yields = [d["yield"] for d in matched_data]
    annual_rain = [d["annual_rainfall"] for d in matched_data]
    monsoon_rain = [d["monsoon_rainfall"] for d in matched_data]

    annual_corr = analyzer.pearson_correlation(annual_rain, yields)
    monsoon_corr = analyzer.pearson_correlation(monsoon_rain, yields)

    def interpret_correlation(r: float) -> str:
        """Interpret correlation coefficient."""
        if abs(r) < 0.2:
            return "negligible"
        elif abs(r) < 0.4:
            return "weak"
        elif abs(r) < 0.6:
            return "moderate"
        elif abs(r) < 0.8:
            return "strong"
        else:
            return "very strong"

    return {
        "state": state,
        "crop": crop,
        "year": year,
        "sample_size": len(matched_data),
        "correlations": {
            "annual_rainfall": {
                "r": round(annual_corr, 4),
                "interpretation": interpret_correlation(annual_corr),
                "direction": "positive" if annual_corr > 0 else "negative",
            },
            "monsoon_rainfall": {
                "r": round(monsoon_corr, 4),
                "interpretation": interpret_correlation(monsoon_corr),
                "direction": "positive" if monsoon_corr > 0 else "negative",
            },
        },
        "data_points": matched_data,
        "note": "Correlation uses IMD 1951-2000 rainfall normals vs actual yields",
        "validity": {
            "climate_assumption": "stationary",
            "baseline_period": "1951-2000",
            "warning": "Correlation based on historic climate normals. Not valid for real-time weather impact."
        }
    }
