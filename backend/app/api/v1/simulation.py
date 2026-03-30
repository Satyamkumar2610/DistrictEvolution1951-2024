"""
Simulation API Endpoints.
Uses Spatial-for-Temporal substitution to estimate rainfall sensitivity.
"""

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.schemas.simulation import PredictionV2Response, SimulationResponse
from app.services import SimulationService
from app.validators import validate_crop, validate_state_name, validate_year

router = APIRouter()


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
    crop = validate_crop(crop)
    year = validate_year(year)
    state = validate_state_name(state)
    service = SimulationService(db)
    return await service.get_simulation_response(district, crop, year, state)


# ──────────────────────────────────────────────────────────────────────────────
# V2 — Multi-Factor Prediction Endpoint
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/v2", response_model=PredictionV2Response)
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
    crop = validate_crop(crop)
    year = validate_year(year)
    state = validate_state_name(state)
    service = SimulationService(db)
    return await service.get_prediction_v2_response(district, crop, year, state)
