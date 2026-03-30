"""
Climate API endpoints: Rainfall data and correlation analysis.
Data served from database (populated via ETL from IMD API).
"""

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.schemas.climate import (
    RainfallMapItem,
    RainfallResponse,
    RainfallStatsResponse,
    RainfallYieldCorrelationResponse,
    StateRainfallStatsResponse,
    WaterStressResponse,
)
from app.services.climate_service import ClimateService

router = APIRouter()


@router.get("/rainfall/stats", response_model=RainfallStatsResponse)
async def get_rainfall_db_stats(db: asyncpg.Connection = Depends(get_db)):
    """Get database statistics for rainfall data."""
    service = ClimateService(db)
    return await service.get_rainfall_stats()


@router.get("/rainfall", response_model=RainfallResponse)
async def get_rainfall(
    state: str = Query(..., description="State name", max_length=50),
    district: str = Query(..., description="District name", max_length=50),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get rainfall normals for a specific district.

    Returns monthly, seasonal, and annual rainfall data (1951-2000 normals).
    """
    service = ClimateService(db)
    return await service.get_rainfall(state, district)


@router.get("/rainfall/all", response_model=list[RainfallMapItem])
async def get_all_rainfall_data(
    state: str | None = Query(None, description="Filter by state", max_length=50),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get rainfall data for all districts (or filter by state).
    For map visualization.
    """
    service = ClimateService(db)
    return await service.get_all_rainfall_data(state)


@router.get("/rainfall/state-stats", response_model=StateRainfallStatsResponse)
async def get_state_stats(
    state: str = Query(..., description="State name", max_length=50),
    db: asyncpg.Connection = Depends(get_db),
):
    """Get aggregated rainfall statistics for a state."""
    service = ClimateService(db)
    return await service.get_state_stats(state)


@router.get("/water-stress", response_model=WaterStressResponse)
async def get_water_stress(
    state: str = Query(..., description="State name", max_length=50),
    year: int = Query(2020, description="Year to analyze (e.g., 2020)", ge=1950, le=2025),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get Water Stress Index (Mismatch Index) mapping water-intensive crops against annual rainfall.
    """
    service = ClimateService(db)
    return await service.get_water_stress(state, year)


@router.get("/correlation", response_model=RainfallYieldCorrelationResponse)
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
    service = ClimateService(db)
    return await service.get_rainfall_yield_correlation(state, crop, year)
