"""
Analysis API: Split impact and advanced analytics endpoints.
Updated to use lgd_code/district_lgd schema.
"""
import hashlib
import logging

import asyncpg
from fastapi import APIRouter, Depends, Query, Request

from app.analytics import get_advanced_analyzer
from app.api.deps import get_db
from app.exceptions import NotFoundError, ValidationError
from app.schemas.analysis import (
    DistrictRiskProfileResponse,
    SplitImpactDistrictSummary,
    SplitImpactResponse,
    StateDiversificationResponse,
    SummaryResponse,
    YieldEfficiencyResponse,
)
from app.services.analysis_service import AnalysisService
from app.validators import (
    validate_cdk,
    validate_cdk_list,
    validate_crop,
    validate_metric,
    validate_mode,
    validate_state_name,
    validate_year,
)

router = APIRouter()


def _generate_query_hash(request: Request) -> str:
    """Generate hash of query params for provenance."""
    query_string = str(sorted(request.query_params.items()))
    return f"sha256:{hashlib.sha256(query_string.encode()).hexdigest()[:16]}"


@router.get("/split-impact/summary", response_model=SummaryResponse)
async def get_summary(db: asyncpg.Connection = Depends(get_db)):
    """
    Get summary statistics for all states.

    Returns list of states with district counts and boundary change counts.
    Uses district_splits table for split event counts.
    """
    service = AnalysisService(db)
    return await service.get_split_summary()


@router.get("/split-impact/districts", response_model=list[SplitImpactDistrictSummary])
async def get_districts_for_state(
    state: str = Query(..., description="State name"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get split events for a specific state.

    Uses pre-resolved LGD codes from district_splits (populated by ETL).
    Falls back to shared name_resolver for any remaining unresolved entries.
    """
    state = validate_state_name(state)
    service = AnalysisService(db)
    return await service.get_resolved_split_events_for_state(state)


@router.get("/split-impact/analysis", response_model=SplitImpactResponse)
async def analyze_split_impact(
    request: Request,
    parent: str = Query(..., description="Parent district CDK"),
    children: str = Query(..., description="Comma-separated child CDKs"),
    splitYear: int = Query(..., alias="splitYear", description="Year of split"),
    crop: str = Query("wheat", description="Crop name"),
    metric: str = Query("yield", description="Metric: yield, area, production"),
    mode: str = Query("before_after", description="Mode: before_after or entity_comparison"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Perform split impact analysis.
    """
    parent = validate_cdk(parent)
    children_list = validate_cdk_list(children)
    splitYear = validate_year(splitYear)
    crop = validate_crop(crop)
    metric = validate_metric(metric)
    mode = validate_mode(mode)

    variable = f"{crop}_{metric}"
    query_hash = _generate_query_hash(request)

    # Check Cache
    from app.cache import CacheTTL, get_cache
    cache = get_cache()
    try:
        cached_result = await cache.get(query_hash)
        if cached_result:
            return cached_result
    except Exception:
        logging.getLogger(__name__).debug(
            "Cache get failed for %s", query_hash)

    service = AnalysisService(db)
    result = await service.analyze_split_impact(
        parent_cdk=parent,
        children_cdks=children_list,
        split_year=splitYear,
        domain="agriculture",
        variable=variable,
        mode=mode,
        query_hash=query_hash,
    )

    # Set Cache
    try:
        await cache.set(query_hash, result, CacheTTL.ANALYSIS)
    except Exception:
        logging.getLogger(__name__).debug(
            "Cache set failed for %s", query_hash)
    return result


# Advanced Analytics Endpoints
# -----------------------------------------------------------------------------


@router.get("/diversification", response_model=StateDiversificationResponse)
async def get_crop_diversification(
    state: str = Query(..., description="State name"),
    year: int = Query(..., description="Year to analyze"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Calculate Crop Diversification Index (CDI) for a state.

    Uses Simpson's Diversity Index: 1 - Σ(pi²)
    Higher values indicate more diverse cropping patterns.
    """
    state = validate_state_name(state)
    year = validate_year(year)

    # Get crop area data aggregated by crop for the state/year
    query = """
        SELECT variable_name, value
        FROM agri_metrics m
        JOIN districts d ON m.district_lgd = d.lgd_code
        WHERE d.state_name = $1
          AND m.year = $2
          AND (m.variable_name LIKE '%_area' OR m.variable_name LIKE '%_area_%')
          AND m.value IS NOT NULL AND m.value > 0
    """
    rows = await db.fetch(query, state, year)

    if not rows:
        raise NotFoundError(
            detail="No data found for specified state and year")

    crop_areas: dict[str, float] = {}
    for row in rows:
        var = row["variable_name"]
        val = float(row["value"])

        # Extract crop name: "rice_area" -> "rice", "rice_area_kharif" ->
        # "rice"
        crop = var.split("_area_")[0] if "_area_" in var else var.replace("_area", "")

        crop_areas[crop] = crop_areas.get(crop, 0) + val

    analyzer = get_advanced_analyzer()
    result = analyzer.calculate_diversification(crop_areas)

    return {
        "state": state,
        "year": year,
        **result.__dict__,
    }


@router.get("/efficiency", response_model=YieldEfficiencyResponse)
async def get_yield_efficiency(
    cdk: str = Query(..., description="District LGD code (as text)"),
    crop: str = Query(..., description="Crop name"),
    year: int = Query(..., description="Year to analyze"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Calculate yield efficiency for a district compared to state potential.
    """
    cdk = validate_cdk(cdk)
    crop = validate_crop(crop)
    year = validate_year(year)

    # 1. Try Base Variable
    variable = f"{crop}_yield"

    # Check if base variable exists for this district/year
    check_query = "SELECT 1 FROM agri_metrics WHERE district_lgd::text=$1 AND variable_name=$2 AND year=$3"
    exists = await db.fetchval(check_query, cdk, variable, year)

    if not exists:
        # Fallback to seasonal
        season_map = {
            "rice": "kharif", "wheat": "rabi", "maize": "kharif",
            "soyabean": "kharif", "groundnut": "kharif", "cotton": "kharif",
            "pearl_millet": "kharif", "sorghum": "kharif", "chickpea": "rabi"
        }
        season = season_map.get(crop.lower())
        if season:
            variable = f"{crop.lower()}_yield_{season}"

    # Get district info
    district_query = """
        SELECT d.state_name, m.value as yield_val
        FROM agri_metrics m
        JOIN districts d ON m.district_lgd = d.lgd_code
        WHERE m.district_lgd::text = $1 AND m.variable_name = $2 AND m.year = $3
    """
    district_row = await db.fetchrow(district_query, cdk, variable, year)

    if not district_row:
        raise NotFoundError(
            detail="No data found for specified district, crop, and year")

    state_name = district_row["state_name"]
    district_yield = float(
        district_row["yield_val"]) if district_row["yield_val"] else 0

    # Get all state yields for this crop/year
    state_query = """
        SELECT m.value as yield_val
        FROM agri_metrics m
        JOIN districts d ON m.district_lgd = d.lgd_code
        WHERE d.state_name = $1 AND m.variable_name = $2 AND m.year = $3
        AND m.value IS NOT NULL AND m.value > 0
    """
    state_rows = await db.fetch(state_query, state_name, variable, year)
    state_yields = [float(r["yield_val"]) for r in state_rows]

    # Get historical yields for this district (last 10 years)
    history_query = """
        SELECT year, value as yield_val
        FROM agri_metrics
        WHERE district_lgd::text = $1 AND variable_name = $2
        AND year < $3 AND year >= $3 - 10
        AND value IS NOT NULL AND value > 0
        ORDER BY year
    """
    history_rows = await db.fetch(history_query, cdk, variable, year)
    historical_yields = [float(r["yield_val"]) for r in history_rows]

    analyzer = get_advanced_analyzer()
    relative_result = analyzer.calculate_efficiency(
        district_yield, state_yields)
    historical_result = analyzer.calculate_historical_efficiency(
        district_yield, historical_yields)

    # Determine units based on metric
    YIELD_UNIT = "kg/ha"

    return {
        "cdk": cdk,
        "crop": crop,
        "year": year,
        "state": state_name,
        "relative_efficiency": relative_result.__dict__,
        "historical_efficiency": historical_result.__dict__,
        "units": {
            "district_yield": YIELD_UNIT,
            "potential_yield": YIELD_UNIT,
            "yield_gap": YIELD_UNIT,
            "historical_mean": YIELD_UNIT,
            "yield_diff": YIELD_UNIT,
            "efficiency_score": "ratio (0-1, 1 = at state potential)",
            "efficiency_ratio": "ratio (1.0 = at 10y mean)",
            "yield_gap_pct": "%",
            "percentile_rank": "percentile (0-100)"
        }
    }


@router.get("/risk-profile", response_model=DistrictRiskProfileResponse)
async def get_risk_profile(
    cdk: str = Query(..., description="District LGD code (as text)"),
    crop: str = Query(..., description="Crop name"),
    metric: str = Query("yield", description="Metric: yield, area, production"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Calculate risk profile based on historical volatility.
    """
    cdk = validate_cdk(cdk)
    crop = validate_crop(crop)
    metric = validate_metric(metric)

    variable = f"{crop}_{metric}"

    # Check if base variable exists
    check_query = "SELECT 1 FROM agri_metrics WHERE district_lgd::text=$1 AND variable_name=$2 LIMIT 1"
    exists = await db.fetchval(check_query, cdk, variable)

    if not exists:
        season_map = {
            "rice": "kharif", "wheat": "rabi", "maize": "kharif",
            "soyabean": "kharif", "groundnut": "kharif", "cotton": "kharif",
            "pearl_millet": "kharif", "sorghum": "kharif", "chickpea": "rabi"
        }
        season = season_map.get(crop.lower())
        if season:
            variable = f"{variable}_{season}"

    query = """
        SELECT year, value
        FROM agri_metrics
        WHERE district_lgd::text = $1 AND variable_name = $2
        AND value IS NOT NULL AND value > 0
        ORDER BY year
    """
    rows = await db.fetch(query, cdk, variable)

    if not rows or len(rows) < 3:
        raise ValidationError(
            detail="Insufficient historical data (need at least 3 years)")

    yearly_values = {row["year"]: float(row["value"]) for row in rows}

    analyzer = get_advanced_analyzer()
    result = analyzer.calculate_risk_profile(yearly_values)
    resilience = analyzer.calculate_resilience(yearly_values)
    growth = analyzer.calculate_growth_matrix(yearly_values)

    # Determine units based on metric type
    METRIC_UNITS = {
        "yield": "kg/ha",
        "area": "1000 ha",
        "production": "1000 tonnes"
    }
    unit = METRIC_UNITS.get(metric, "unit")

    return {
        "cdk": cdk,
        "crop": crop,
        "metric": metric,
        "metric_unit": unit,
        "years_analyzed": len(yearly_values),
        "risk_profile": {
            "risk_category": result.risk_category.value,
            "volatility_score": result.volatility_score,
            "volatility_score_unit": "CV (%)",
            "reliability_rating": result.reliability_rating,
            "trend_stability": result.trend_stability,
            "worst_year": result.worst_year,
            "best_year": result.best_year,
        },
        "resilience_index": resilience.__dict__,
        "growth_matrix": growth.__dict__,
    }
