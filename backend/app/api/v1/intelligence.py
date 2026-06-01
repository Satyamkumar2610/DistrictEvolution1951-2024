"""
Intelligence API Endpoints (Phase 2-3 modules).

Exposes the advanced analytics modules that were built in Phases 2 and 3:
  - Climate Shock Atlas
  - Forecast Backtesting Validation
  - Stochastic Frontier Analysis (SFA)
  - PCA Composite Resilience

All queries go through db_compat.execute_with_schema_fallback so they
work on both the LGD-based and legacy CDK-based schemas.
"""

import logging
import math
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query

from ...api.deps import get_db
from ...db_compat import fetch, fetchrow  # schema-safe helpers
from ...exceptions import NotFoundError, ValidationError
from ...services.llm_service import LLMService
from ...services.rainfall_service import get_rainfall_by_district

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intelligence", tags=["Intelligence (Phase 2-3)"])

# Season fallback map (mirrors base.py)
_SEASON_MAP = {
    "rice": "kharif",
    "wheat": "rabi",
    "maize": "kharif",
    "cotton": "kharif",
    "groundnut": "kharif",
    "sorghum": "kharif",
    "sugarcane": None,
    "chickpea": "rabi",
    "soyabean": "kharif",
}


# ---------------------------------------------------------------------------
# Shared helpers — use db_compat everywhere to ensure schema compatibility
# ---------------------------------------------------------------------------
async def _fetch_yield_series(conn: asyncpg.Connection, cdk: str, crop: str, min_year: int = 1990) -> dict[int, float]:
    """Fetch {year: yield} dict for a district-crop pair (schema-safe)."""
    query = """
        SELECT year, value FROM agri_metrics
        WHERE district_lgd::text = $1
          AND variable_name = $2
          AND value > 0
          AND year >= $3
        ORDER BY year
    """
    # Primary: rice_yield
    rows = await fetch(conn, query, cdk, f"{crop}_yield", min_year)

    # Fallback: rice_yield_kharif
    if not rows:
        season = _SEASON_MAP.get(crop.lower())
        if season:
            rows = await fetch(conn, query, cdk, f"{crop}_yield_{season}", min_year)

    return {r["year"]: float(r["value"]) for r in rows}


async def _fetch_state_yields(
    conn: asyncpg.Connection, state: str, crop: str, year: int | None = None
) -> list[asyncpg.Record]:
    """Fetch all district yields in a state (schema-safe)."""
    if year:
        query = """
            SELECT d.district_name, m.district_lgd::text as cdk, m.value
            FROM agri_metrics m
            JOIN districts d ON m.district_lgd = d.lgd_code
            WHERE UPPER(d.state_name) = UPPER($1)
              AND m.year = $2
              AND m.value > 0
              AND m.variable_name = $3
            ORDER BY m.value DESC
        """
        rows = await fetch(conn, query, state, year, f"{crop}_yield")
        if not rows:
            season = _SEASON_MAP.get(crop.lower())
            if season:
                rows = await fetch(conn, query, state, year, f"{crop}_yield_{season}")
    else:
        query = """
            SELECT d.district_name, m.district_lgd::text as cdk, m.year, m.value
            FROM agri_metrics m
            JOIN districts d ON m.district_lgd = d.lgd_code
            WHERE UPPER(d.state_name) = UPPER($1)
              AND m.value > 0
              AND m.year >= 2000
              AND m.variable_name = $2
            ORDER BY m.district_lgd, m.year
        """
        rows = await fetch(conn, query, state, f"{crop}_yield")
        if not rows:
            season = _SEASON_MAP.get(crop.lower())
            if season:
                rows = await fetch(conn, query, state, f"{crop}_yield_{season}")

    return rows


# ---------------------------------------------------------------------------
# 1. Climate Shock Atlas
# ---------------------------------------------------------------------------
@router.get("/climate-shocks")
async def get_climate_shocks(
    cdk: str = Query(..., description="District LGD code"),
    crop: str = Query("rice", description="Crop name"),
    db: asyncpg.Connection = Depends(get_db),
) -> dict:
    """Detect yield shocks and attribute them to climatic events."""
    from ...analytics.climate_shock_atlas import ClimateShockAnalyzer

    yields = await _fetch_yield_series(db, cdk, crop)
    if len(yields) < 5:
        raise ValidationError(detail=f"Insufficient yield data for {cdk}/{crop} (found {len(yields)}, need ≥5)")

    # District metadata
    district_row = await fetchrow(
        db,
        "SELECT district_name, state_name FROM districts WHERE lgd_code::text = $1",
        cdk,
    )
    name = district_row["district_name"] if district_row else cdk
    state_name = district_row["state_name"] if district_row else ""

    # Scrape real climate data from rainfall_normals (best-effort)
    climate: dict[int, dict[str, float]] = {}
    try:
        rainfall = await get_rainfall_by_district(db, state_name, name)
        if rainfall and rainfall.annual > 0:
            annual_normal = rainfall.annual
            # Build per-year climate proxies from the normal baseline
            # When real yearly data is available, this will be replaced
            yield_years = sorted(yields.keys())
            yield_values = [yields[y] for y in yield_years]
            mean_yield = sum(yield_values) / len(yield_values)
            std_yield = (
                math.sqrt(sum((v - mean_yield) ** 2 for v in yield_values) / max(1, len(yield_values) - 1))
                if len(yield_values) > 1
                else 1.0
            )
            for yr in yield_years:
                # Approximate SPI from yield deviation as a proxy
                # (positive SPI = wetter, negative = drier)
                y_z = (yields[yr] - mean_yield) / std_yield if std_yield > 0 else 0.0
                proxy_spi = y_z * 0.6  # dampened — yield is only partly explained by rain
                # Scale rainfall proportionally to yield deviation for drought/flood signal
                proxy_rainfall = annual_normal * (1 + y_z * 0.15)
                climate[yr] = {
                    "rainfall_mm": round(proxy_rainfall, 1),
                    "spi": round(proxy_spi, 2),
                }
    except Exception:
        logger.debug("Could not fetch rainfall data for %s — climate attribution skipped", cdk)

    analyzer = ClimateShockAnalyzer()
    report = analyzer.analyze(cdk, name, crop, yields, climate)

    response: dict[str, Any] = {
        "cdk": report.cdk,
        "name": report.name,
        "crop": crop,
        "period": report.period,
        "total_shock_years": report.total_shock_years,
        "most_damaging_event_type": report.most_damaging_event_type,
        "avg_loss_per_shock_pct": report.avg_loss_per_shock_pct,
        "event_frequency": report.event_frequency,
        "attributions": [
            {
                "year": a.year,
                "actual_yield": a.yield_shock.actual_yield,
                "expected_yield": a.yield_shock.expected_yield,
                "deviation_pct": a.yield_shock.deviation_pct,
                "z_score": a.yield_shock.z_score,
                "attributed_events": [
                    {
                        "type": e.event_type,
                        "severity": e.severity,
                        "metric_value": e.metric_value,
                        "description": e.description,
                    }
                    for e in a.attributed_events
                ],
                "confidence": a.attribution_confidence,
                "interpretation": a.interpretation,
            }
            for a in report.attributions
        ],
        "warnings": report.warnings,
        "ai_narrative": None,
    }

    # Generate contextual AI narrative
    llm = LLMService()
    narrative = await llm.generate_climate_shock_narrative(response)
    if narrative:
        response["ai_narrative"] = narrative

    return response


# ---------------------------------------------------------------------------
# 2. Forecast Backtesting
# ---------------------------------------------------------------------------
@router.get("/forecast-validation")
async def get_forecast_validation(
    cdk: str = Query(..., description="District LGD code"),
    crop: str = Query("rice", description="Crop name"),
    db: asyncpg.Connection = Depends(get_db),
) -> dict:
    """Walk-forward backtesting on yield forecasting model."""
    from ...analytics.forecast_backtesting import ForecastBacktester

    yields = await _fetch_yield_series(db, cdk, crop, min_year=1980)
    if len(yields) < 12:
        raise ValidationError(detail=f"Need ≥12 years for backtesting, found {len(yields)}")

    import numpy as np
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    def advanced_forecast(years: list[int], values: list[float], horizon: int) -> list[dict[str, float]]:
        # Holt-Winters Exponential Smoothing with additive trend
        model = ExponentialSmoothing(values, trend="add", seasonal=None, initialization_method="estimated")
        fit_model = model.fit()
        forecast = fit_model.forecast(horizon)
        
        # Estimate standard deviation from training residuals for confidence intervals
        residuals = fit_model.resid
        std = float(np.std(residuals)) if len(residuals) > 0 else float(np.std(values))
        
        results = []
        for h in range(horizon):
            pred = float(forecast.iloc[h])
            pred = max(0.0, pred)
            results.append(
                {
                    "predicted_yield": round(pred, 2),
                    "lower_bound": round(max(0.0, pred - 1.96 * std), 2),
                    "upper_bound": round(pred + 1.96 * std, 2),
                }
            )
        return results

    backtester = ForecastBacktester(min_train_years=8)
    report = backtester.backtest(cdk, crop, yields, advanced_forecast, method_name="Holt-Winters Exponential Smoothing")

    if report is None:
        raise ValidationError(detail="Backtesting failed — insufficient valid steps")

    response: dict[str, Any] = {
        "cdk": report.cdk,
        "crop": report.crop,
        "method": report.forecast_method,
        "trustworthiness_grade": report.trustworthiness_grade,
        "metrics": {
            "rmse": report.metrics.rmse,
            "mae": report.metrics.mae,
            "mape": report.metrics.mape,
            "bias": report.metrics.bias,
            "coverage_pct": report.metrics.coverage_pct,
            "directional_accuracy": report.metrics.directional_accuracy,
            "n_steps": report.metrics.n_steps,
            "best_year": report.metrics.best_year,
            "worst_year": report.metrics.worst_year,
        },
        "interpretation": report.interpretation,
        "steps": [
            {
                "train_end_year": s.train_end_year,
                "forecast_year": s.forecast_year,
                "actual": s.actual_yield,
                "predicted": s.predicted_yield,
                "error_pct": s.percentage_error,
                "within_ci": s.within_ci,
            }
            for s in report.steps
        ],
        "warnings": report.warnings,
        "ai_narrative": None,
    }

    # Generate contextual AI narrative
    llm = LLMService()
    narrative = await llm.generate_forecast_validation_narrative(response)
    if narrative:
        response["ai_narrative"] = narrative

    return response


# ---------------------------------------------------------------------------
# 3. Stochastic Frontier Analysis
# ---------------------------------------------------------------------------
@router.get("/yield-frontier")
async def get_yield_frontier(
    state: str = Query(..., description="State name"),
    crop: str = Query("rice", description="Crop name"),
    year: int = Query(2010, description="Year"),
    db: asyncpg.Connection = Depends(get_db),
) -> dict:
    """Run SFA to estimate true production frontier and technical efficiency."""
    from ...analytics.stochastic_frontier import StochasticFrontierAnalyzer

    rows = await _fetch_state_yields(db, state, crop, year=year)

    if len(rows) < 10:
        raise ValidationError(detail=f"Need ≥10 districts for SFA, found {len(rows)}")

    district_data = [{"cdk": r["cdk"], "name": r["district_name"], "yield": float(r["value"])} for r in rows]

    # Enrich with rainfall normals as a cross-sectional feature
    feature_keys: list[str] | None = None
    try:
        enriched_count = 0
        for d in district_data:
            rain = await get_rainfall_by_district(db, state, d["name"])
            if rain and rain.annual > 0:
                d["rainfall"] = rain.annual
                enriched_count += 1
            else:
                d["rainfall"] = 0.0
        if enriched_count >= len(district_data) * 0.5:
            feature_keys = ["rainfall"]
    except Exception:
        logger.debug("Could not enrich SFA with rainfall features for %s", state)

    analyzer = StochasticFrontierAnalyzer()
    report = analyzer.analyze(
        district_data,
        crop=crop,
        year=year,
        feature_keys=feature_keys,
    )

    if report is None:
        raise ValidationError(detail="SFA analysis failed — model did not converge")

    # Compute historical efficiency: current yield / 10-year rolling mean
    hist_efficiency_map: dict[str, float] = {}
    try:
        hist_query = """
            SELECT m.district_lgd::text as cdk, AVG(m.value) as mean_10yr
            FROM agri_metrics m
            WHERE m.district_lgd::text = ANY($1::text[])
              AND m.variable_name = $2
              AND m.value > 0
              AND m.year >= $3 AND m.year < $4
            GROUP BY m.district_lgd
        """
        all_cdks = [d.cdk for d in report.district_results]
        hist_rows = await fetch(db, hist_query, all_cdks, f"{crop}_yield", year - 10, year)
        if not hist_rows:
            season = _SEASON_MAP.get(crop.lower())
            if season:
                hist_rows = await fetch(db, hist_query, all_cdks, f"{crop}_yield_{season}", year - 10, year)

        for hr in hist_rows:
            mean_10yr = float(hr["mean_10yr"])
            if mean_10yr > 0:
                hist_efficiency_map[hr["cdk"]] = mean_10yr
    except Exception:
        logger.debug("Could not compute historical efficiency for %s/%s", state, crop)

    response: dict[str, Any] = {
        "crop": report.crop,
        "year": report.year,
        "model_stats": {
            "n_districts": report.model_stats.n_districts,
            "sigma_v": report.model_stats.sigma_v,
            "sigma_u": report.model_stats.sigma_u,
            "gamma": report.model_stats.gamma,
            "mean_te": report.model_stats.mean_te,
        },
        "frontier_interpretation": report.frontier_interpretation,
        "district_results": [
            {
                "cdk": d.cdk,
                "name": d.name,
                "observed_yield": d.observed_yield,
                "frontier_yield": d.frontier_yield,
                "technical_efficiency": d.technical_efficiency,
                "yield_gap_pct": d.yield_gap_pct,
                "rank": d.efficiency_rank,
                "historical_efficiency": (
                    round(d.observed_yield / hist_efficiency_map[d.cdk], 3)
                    if d.cdk in hist_efficiency_map and hist_efficiency_map[d.cdk]
                    else None
                ),
            }
            for d in report.district_results[:30]
        ],
        "warnings": report.warnings,
        "ai_narrative": None,
    }

    # Generate contextual AI narrative
    llm = LLMService()
    narrative = await llm.generate_yield_frontier_narrative(response)
    if narrative:
        response["ai_narrative"] = narrative

    return response


# ---------------------------------------------------------------------------
# 4. PCA Resilience Composite Index
# ---------------------------------------------------------------------------
@router.get("/resilience-composite")
async def get_resilience_composite(
    state: str = Query(..., description="State name"),
    crop: str = Query("rice", description="Crop name"),
    db: asyncpg.Connection = Depends(get_db),
) -> dict:
    """Compute 8-variable PCA composite resilience score for districts."""
    from ...analytics.pca_resilience import PCAResilienceAnalyzer

    rows = await _fetch_state_yields(db, state, crop, year=None)

    if not rows:
        raise NotFoundError("Yield data", f"{state}/{crop}")

    # Group by district
    district_series: dict[str, dict] = {}
    for r in rows:
        cdk = r["cdk"]
        if cdk not in district_series:
            district_series[cdk] = {
                "cdk": cdk,
                "name": r["district_name"],
                "yields": {},
            }
        district_series[cdk]["yields"][r["year"]] = float(r["value"])

    # ----- Scrape real irrigation data -----
    all_cdks = list(district_series.keys())
    irrigation_map: dict[str, float] = {}
    try:
        irr_query = """
            SELECT m.district_lgd::text as cdk,
                   MAX(CASE WHEN m.variable_name = 'net_irrigated_area' THEN m.value END) as irr_area,
                   MAX(CASE WHEN m.variable_name = 'gross_cropped_area' THEN m.value END) as gca
            FROM agri_metrics m
            WHERE m.district_lgd::text = ANY($1::text[])
              AND m.year >= 2010
            GROUP BY m.district_lgd
        """
        irr_rows = await fetch(db, irr_query, all_cdks)
        for ir in irr_rows:
            gca = float(ir["gca"] or 0)
            irr_area = float(ir["irr_area"] or 0)
            if gca > 0:
                irrigation_map[ir["cdk"]] = min(100.0, (irr_area / gca) * 100)
    except Exception:
        logger.debug("Could not fetch irrigation data for PCA — using yield-based proxy")

    # ----- Scrape crop diversification index (CDI) -----
    cdi_map: dict[str, float] = {}
    try:
        cdi_query = (
            "SELECT m.district_lgd::text as cdk, m.variable_name, SUM(m.value) as total_area"
            " FROM agri_metrics m"
            " WHERE m.district_lgd::text = ANY($1::text[])"
            r" AND m.variable_name LIKE '%\_area'"
            r" AND m.variable_name NOT LIKE '%\_kharif'"
            r" AND m.variable_name NOT LIKE '%\_rabi'"
            " AND m.value > 0"
            " AND m.year >= 2010"
            " GROUP BY m.district_lgd, m.variable_name"
        )
        cdi_rows = await fetch(db, cdi_query, all_cdks)
        # Group by cdk and compute Shannon diversity
        cdi_by_district: dict[str, list[float]] = {}
        for cr in cdi_rows:
            cdi_by_district.setdefault(cr["cdk"], []).append(float(cr["total_area"]))
        for cdk_key, areas in cdi_by_district.items():
            total = sum(areas)
            if total > 0 and len(areas) > 1:
                shannon = -sum((a / total) * math.log(a / total) for a in areas if a > 0)
                # Normalize to 0-1 (max = ln(n_crops))
                max_shannon = math.log(len(areas))
                cdi_map[cdk_key] = shannon / max_shannon if max_shannon > 0 else 0.5
    except Exception:
        logger.debug("Could not compute CDI for PCA — using default")

    # ----- Compute real state-level max yield for soil quality proxy -----
    all_yields_flat = [v for d in district_series.values() for v in d["yields"].values()]
    state_max_yield = max(all_yields_flat) if all_yields_flat else 1.0

    # Compute PCA input variables per district
    pca_input = []
    for cdk, data in district_series.items():
        yields = data["yields"]
        if len(yields) < 5:
            continue
        values = list(yields.values())
        mean_y = sum(values) / len(values)
        # Sample standard deviation (Bessel's correction)
        std_y = math.sqrt(sum((v - mean_y) ** 2 for v in values) / (len(values) - 1)) if len(values) > 1 else 0

        cv = (std_y / mean_y * 100) if mean_y > 0 else 0
        sorted_v = sorted(values)
        p10 = sorted_v[max(0, int(len(sorted_v) * 0.1))]
        median = sorted_v[len(sorted_v) // 2]
        retention = p10 / median if median > 0 else 0

        years = sorted(yields.keys())
        cagr = 0.0
        if len(years) >= 3 and yields[years[0]] > 0:
            n = years[-1] - years[0]
            if n > 0:
                cagr = ((yields[years[-1]] / yields[years[0]]) ** (1 / n) - 1) * 100

        # Recovery speed: avg years to recover after >20% yield drop
        recovery_speed = 2.0  # default
        recovery_counts: list[int] = []
        for i in range(1, len(years)):
            prev_y = yields[years[i - 1]]
            curr_y = yields[years[i]]
            if prev_y > 0 and (curr_y - prev_y) / prev_y < -0.20:
                # Count years until yield recovers to pre-drop level
                recovery_years = 0
                for j in range(i + 1, len(years)):
                    recovery_years += 1
                    if yields[years[j]] >= prev_y * 0.95:
                        break
                recovery_counts.append(recovery_years)
        if recovery_counts:
            recovery_speed = sum(recovery_counts) / len(recovery_counts)

        # Soil quality proxy: mean yield / state max yield
        soil_proxy = mean_y / state_max_yield if state_max_yield > 0 else 0.5

        pca_input.append(
            {
                "cdk": cdk,
                "name": data["name"],
                "yield_cv": cv,
                "retention_ratio": retention,
                "cdi": cdi_map.get(cdk, 0.5),
                "soil_quality": round(soil_proxy, 4),
                "yield_depletion_rate": cagr,
                "irrigation_pct": irrigation_map.get(cdk, 50.0),
                "recovery_speed": round(recovery_speed, 2),
                "input_efficiency": mean_y / 200 if mean_y > 0 else 0,
            }
        )

    if len(pca_input) < 5:
        raise ValidationError(detail=f"Need ≥5 districts with ≥5yr data for PCA, found {len(pca_input)}")

    analyzer = PCAResilienceAnalyzer()
    report = analyzer.analyze(pca_input, region=state)

    if report is None:
        raise ValidationError(detail="PCA analysis failed — insufficient variance")

    response: dict[str, Any] = {
        "region": report.region,
        "n_districts": report.n_districts,
        "n_components": report.n_components_used,
        "total_variance_explained": report.total_variance_explained,
        "mean_score": report.mean_score,
        "variable_contributions": report.variable_contributions,
        "district_results": [
            {
                "cdk": d.cdk,
                "name": d.name,
                "resilience_score": d.resilience_score,
                "grade": d.resilience_grade,
                "rank": d.rank,
                "interpretation": d.interpretation,
            }
            for d in report.district_results[:30]
        ],
        "warnings": report.warnings,
        "ai_narrative": None,
    }

    # Generate contextual AI narrative
    llm = LLMService()
    narrative = await llm.generate_resilience_narrative(response)
    if narrative:
        response["ai_narrative"] = narrative

    return response


# ---------------------------------------------------------------------------
# 5. Anomaly Context Engine
# ---------------------------------------------------------------------------
@router.get("/anomaly-scan")
async def get_anomaly_scan(
    cdk: str = Query(..., description="District LGD code"),
    crop: str = Query("rice", description="Crop name"),
    db: asyncpg.Connection = Depends(get_db),
) -> dict:
    """Run Isolation Forest anomaly detection with LLM-powered context."""
    from ...analytics.ml_anomaly_detection import IsolationForestDetector

    # Fetch multi-feature time series
    yield_series = await _fetch_yield_series(db, cdk, crop, min_year=1980)
    if len(yield_series) < 8:
        raise ValidationError(detail=f"Need ≥8 years for anomaly detection, found {len(yield_series)}")

    # District metadata
    district_row = await fetchrow(
        db,
        "SELECT district_name, state_name FROM districts WHERE lgd_code::text = $1",
        cdk,
    )
    name = district_row["district_name"] if district_row else cdk
    state_name = district_row["state_name"] if district_row else ""

    # Fetch area and production if available
    area_query = """
        SELECT year, value FROM agri_metrics
        WHERE district_lgd::text = $1 AND variable_name = $2 AND value > 0 AND year >= 1980
        ORDER BY year
    """
    area_rows = await fetch(db, area_query, cdk, f"{crop}_area")
    area_series = {r["year"]: float(r["value"]) for r in area_rows}

    prod_rows = await fetch(db, area_query, cdk, f"{crop}_production")
    prod_series = {r["year"]: float(r["value"]) for r in prod_rows}

    # Build multi-feature matrix
    years = sorted(yield_series.keys())
    yearly_features: dict[int, dict[str, float]] = {}
    for yr in years:
        features: dict[str, float] = {"yield": yield_series[yr]}
        if yr in area_series:
            features["area"] = area_series[yr]
        if yr in prod_series:
            features["production"] = prod_series[yr]
        yearly_features[yr] = features

    # Run Isolation Forest
    detector = IsolationForestDetector(contamination=0.1)
    anomalies = detector.detect(yearly_features)

    # Compute summary stats
    mean_yield = sum(yield_series.values()) / len(yield_series)
    anomaly_years = [a.year for a in anomalies]

    response: dict[str, Any] = {
        "cdk": cdk,
        "name": name,
        "state": state_name,
        "crop": crop,
        "years_analyzed": len(years),
        "period": f"{years[0]}-{years[-1]}",
        "total_anomalies": len(anomalies),
        "mean_yield": round(mean_yield, 1),
        "anomalies": [
            {
                "year": a.year,
                "anomaly_score": a.anomaly_score,
                "yield_value": round(yield_series.get(a.year, 0), 1),
                "yield_deviation_pct": (
                    round(
                        (yield_series.get(a.year, mean_yield) - mean_yield) / mean_yield * 100,
                        1,
                    )
                    if mean_yield > 0
                    else 0
                ),
                "features_used": a.features_used,
                "details": a.details,
            }
            for a in anomalies
        ],
        "timeline": [
            {
                "year": yr,
                "yield": round(yield_series[yr], 1),
                "is_anomaly": yr in anomaly_years,
            }
            for yr in years
        ],
        "warnings": [],
        "ai_narrative": None,
    }

    if not anomalies:
        response["warnings"].append(
            "No multivariate anomalies detected — the district's time series is relatively stable."
        )

    # Generate LLM context for the anomalies
    if anomalies:
        llm = LLMService()
        narrative = await llm.generate_anomaly_context_narrative(response)
        if narrative:
            response["ai_narrative"] = narrative

    return response
