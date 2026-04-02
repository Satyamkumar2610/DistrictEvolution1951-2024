"""
Metrics API: Endpoints for agricultural/domain metrics.
"""

import logging

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.exceptions import NotFoundError
from app.repositories.district_repo import DistrictRepository
from app.repositories.metric_repo import MetricRepository
from app.schemas.metric import AggregatedMetric, MetricHistoryPoint

router = APIRouter()


@router.get("", response_model=list[AggregatedMetric])
async def get_metrics(
    year: int = Query(2020, description="Year to fetch"),
    crop: str = Query("wheat", description="Crop name"),
    metric: str = Query("yield", description="Metric type: yield, area, production"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get metric values for all districts for a given year/crop/metric.

    Used for choropleth map visualization.
    """
    repo = MetricRepository(db)
    variable = f"{crop.lower()}_{metric.lower()}"
    return await repo.get_by_year_and_variable(year, variable)


@router.get("/history", response_model=list[MetricHistoryPoint])
async def get_time_series(
    cdk: str | None = Query(None, description="District CDK"),
    district: str | None = Query(None, description="District name (if CDK not provided)"),
    state: str | None = Query(None, description="State name (helps resolve district name)"),
    crop: str = Query("wheat", description="Crop name"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get time series for a single district.

    Returns {year, area, production, yield} for the specified crop.
    """
    district_repo = DistrictRepository(db)
    metric_repo = MetricRepository(db)

    target_cdk = cdk

    # Resolve CDK from name if needed
    if not target_cdk and district:
        # Tring resolving name first
        from app.core.name_matching import resolve_district_name

        resolved_name = resolve_district_name(district)

        # 1. Try search with resolved name
        results = await district_repo.search(resolved_name, state)
        if results:
            target_cdk = results[0].cdk

        # 2. If valid state provided, try to find by exact match in that state
        # (fallback)
        if not target_cdk and state:
            # Try simple normalization locally if repository search failed
            # (repo uses ILIKE, so fuzzy logic already there)
            logging.getLogger(__name__).debug("District '%s' not found in state '%s' via repo search", district, state)

    if not target_cdk:
        raise NotFoundError(detail=f"District not found: {district}")

    timeline = await metric_repo.get_time_series_pivoted(target_cdk, crop.lower())

    return timeline


@router.get("/history/state", response_model=list[MetricHistoryPoint])
async def get_state_time_series(
    state: str = Query(..., description="State name, e.g. 'Andhra Pradesh'"),
    crop: str = Query("wheat", description="Crop name"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get aggregated time series for a whole state.

    Uses pre-aggregated Census data if available (inserted as S_STATE_NAME).
    """
    metric_repo = MetricRepository(db)

    # Construct State CDK
    # Must match ingestion logic: UPPER, space->_, &->AND
    normalized_state = state.upper().replace(" ", "_").replace("&", "AND")
    state_cdk = f"S_{normalized_state}"

    timeline = await metric_repo.get_time_series_pivoted(state_cdk, crop.lower())

    if not timeline:
        # Fallback to dynamic aggregation if S_STATE_NAME data is not in DB
        timeline = await metric_repo.get_state_time_series_aggregated(state, crop.lower())

    return timeline
