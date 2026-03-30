"""
States API: Aggregate state-level endpoints.
Provides overview statistics for each state.
"""
import asyncpg
from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.schemas.district import StateCount, StateOverview
from app.services.state_service import StateService
from app.validators import validate_crop, validate_state_name, validate_year

router = APIRouter(prefix="/states", tags=["States"])


@router.get("/{state_name}/overview", response_model=StateOverview)
async def get_state_overview(
    state_name: str,
    crop: str = Query("wheat", description="Crop to analyze"),
    year: int | None = Query(None, description="Year (defaults to latest)"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get aggregate overview for a state.

    Returns total districts, data coverage, avg yield,
    top/bottom performers, and year range.
    """
    state_name = validate_state_name(state_name)
    crop = validate_crop(crop)
    year = validate_year(year) if year is not None else None

    service = StateService(db)
    return await service.get_overview(state_name, crop, year)


@router.get("/list", response_model=list[StateCount])
async def list_states(db: asyncpg.Connection = Depends(get_db)):
    """
    List all states with district counts.
    """
    service = StateService(db)
    return await service.list_states()
