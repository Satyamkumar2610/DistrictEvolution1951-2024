"""
Lineage API: Endpoints for lineage graph and split events.
Updated to use cdk/cdk schema where applicable.
Note: lineage_events uses CDK text keys that cannot join to districts.cdk.
"""

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.schemas.lineage import (
    DistrictHistoryItem,
    LineageGraph,
    ProvenanceTrackingResponse,
    SplitEventSummary,
    StateCoverageResponse,
    UnmappedSplitItem,
)
from app.services import AnalysisService, LineageService
from app.validators import validate_cdk, validate_state_name

router = APIRouter()


@router.get("/history", response_model=list[DistrictHistoryItem])
async def get_district_history(
    state: str | None = Query(None, description="Filter by state name"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get comprehensive district split history from detailed records (1951-2024).
    """
    validated_state = validate_state_name(state) if state else None
    service = LineageService(db)
    return await service.get_district_history_response(validated_state)


@router.get("/events", response_model=LineageGraph)
async def get_lineage_events(
    state: str | None = Query(None, description="Filter by state"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get lineage events (administrative boundary changes).

    Returns split/merge/rename events optionally filtered by state.
    """
    validated_state = validate_state_name(state) if state else None
    service = LineageService(db)
    return await service.get_lineage_events_response(validated_state)


@router.get("/splits", response_model=list[SplitEventSummary])
async def get_split_events(
    state: str = Query(..., description="State name (required)"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get grouped split events for a state.

    Returns parent districts with their children, sorted by year.
    """
    state = validate_state_name(state)
    service = AnalysisService(db)
    return await service.get_split_events_for_state(state)


@router.get("/tracking", response_model=ProvenanceTrackingResponse)
async def get_data_tracking(
    cdk: str = Query(..., description="District LGD code (as text)"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get data lineage tracking for a district.

    Returns:
    - Data sources used
    - Year coverage
    - Related lineage events (splits/merges)
    - Data provenance chain
    """
    cdk = validate_cdk(cdk)
    service = LineageService(db)
    return await service.get_data_tracking_response(cdk)


@router.get("/coverage", response_model=StateCoverageResponse)
async def get_state_coverage(
    state: str = Query(..., description="State name"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get data coverage summary for all districts in a state.

    Shows years with data, record counts, and lineage status per district.
    """
    state = validate_state_name(state)
    service = LineageService(db)
    return await service.get_state_coverage_response(state)


@router.get("/unmapped", response_model=list[UnmappedSplitItem])
async def get_unmapped_splits(
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get all districts involved in splits that cannot be mapped to an LGD code.
    """
    service = LineageService(db)
    return await service.get_unmapped_splits_response()
