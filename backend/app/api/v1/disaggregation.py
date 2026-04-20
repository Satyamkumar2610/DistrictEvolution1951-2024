"""
API routes for counterfactual disaggregation packets and series.
"""

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.schemas.disaggregation import (
    DisaggregationEventDetail,
    DisaggregationEventListResponse,
    DisaggregationSeriesResponse,
)
from app.services.disaggregation_service import DisaggregationService
from app.validators import (
    validate_crop,
    validate_limit,
    validate_metric,
    validate_offset,
    validate_state_name,
    validate_year_range,
)

router = APIRouter(prefix="/disaggregation", tags=["Disaggregation"])


@router.get("/events", response_model=DisaggregationEventListResponse)
async def list_disaggregation_events(
    state: str | None = Query(None, description="Filter by state name"),
    readiness_tier: str | None = Query(None, description="Filter by readiness tier"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: asyncpg.Connection = Depends(get_db),
):
    validated_state = validate_state_name(state) if state else None
    validated_limit = validate_limit(limit, max_limit=500)
    validated_offset = validate_offset(offset)
    service = DisaggregationService(db)
    return await service.list_events(validated_state, readiness_tier, validated_limit, validated_offset)


@router.get("/events/{event_id}", response_model=DisaggregationEventDetail)
async def get_disaggregation_event(
    event_id: str,
    db: asyncpg.Connection = Depends(get_db),
):
    service = DisaggregationService(db)
    return await service.get_event_detail(event_id)


@router.get("/events/{event_id}/series", response_model=DisaggregationSeriesResponse)
async def get_disaggregation_series(
    event_id: str,
    crop: str = Query(..., description="Crop name"),
    metric: str = Query(..., description="Metric: area, production, or yield"),
    start_year: int = Query(1966, description="Start year"),
    end_year: int = Query(2017, description="End year"),
    db: asyncpg.Connection = Depends(get_db),
):
    crop = validate_crop(crop)
    metric = validate_metric(metric)
    start_year, end_year = validate_year_range(start_year, end_year)
    service = DisaggregationService(db)
    return await service.get_event_series(event_id, crop, metric, start_year, end_year)
