"""
Anomaly Detection API Endpoints.
Provides anomaly scanning and risk assessment for districts.
"""

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.schemas.anomalies import (
    DistrictAnomalyReportResponse,
    HighRiskResponse,
    StateAnomalySummaryResponse,
)
from app.services import AnomalyService
from app.validators import validate_cdk, validate_state_name

router = APIRouter(prefix="/anomalies", tags=["Anomaly Detection"])


@router.get("/district/{cdk}", response_model=DistrictAnomalyReportResponse)
async def scan_district_anomalies(
    cdk: str,
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Run full anomaly scan for a specific district.

    Detects:
    - Yield outliers (> 3 std from state mean)
    - Year-over-year spikes (> 50% change)
    - Missing data sequences (> 3 consecutive years)
    - Consistency errors (production ≠ area × yield)
    - Invalid values (negative/zero where unexpected)

    Also generates a risk alert with severity assessment.
    """
    cdk = validate_cdk(cdk)
    service = AnomalyService(db)
    return await service.scan_district_response(cdk)


@router.get("/state/{state_name}", response_model=StateAnomalySummaryResponse)
async def scan_state(
    state_name: str,
    limit: int = Query(20, ge=1, le=100),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Scan all districts in a state for anomalies.

    Returns aggregated anomaly counts and identifies high-risk districts.
    Limited to 20 districts by default for performance.
    """
    state_name = validate_state_name(state_name)
    service = AnomalyService(db)
    return await service.scan_state_response(state_name, limit)


@router.get("/high-risk", response_model=HighRiskResponse)
async def get_high_risk_districts(
    limit: int = Query(10, ge=1, le=30),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Get districts with highest risk scores across all states.

    Scans a sample of districts and returns those with highest risk.
    """
    service = AnomalyService(db)
    return await service.get_high_risk_districts_response(limit)
