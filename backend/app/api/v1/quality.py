"""
Data Quality API Endpoints.
Provides quality scoring for districts and states.
"""

import asyncpg
from fastapi import APIRouter, Depends

from app.analytics.data_quality import DataQualityScorer, get_state_quality_summary
from app.database import get_db
from app.db_compat import fetchval
from app.exceptions import NotFoundError
from app.schemas.quality import DataQualityDistrictResponse, StateQualitySummaryResponse

router = APIRouter(prefix="/quality", tags=["Data Quality"])


@router.get("/district/{cdk}", response_model=DataQualityDistrictResponse)
async def get_district_quality(cdk: str, db: asyncpg.Connection = Depends(get_db)):
    """
    Get data quality report for a specific district.

    Returns completeness, consistency, timeliness, and accuracy scores.
    """
    # Verify district exists
    exists = await fetchval(db, "SELECT 1 FROM districts WHERE lgd_code::text = $1", cdk)
    if not exists:
        raise NotFoundError("District", cdk)

    scorer = DataQualityScorer(db)
    report = await scorer.score_district(cdk)

    return report.to_dict()


@router.get("/state/{state_name}", response_model=StateQualitySummaryResponse)
async def get_state_quality(state_name: str, db: asyncpg.Connection = Depends(get_db)):
    """
    Get aggregated data quality summary for a state.

    Analyzes up to 20 districts and provides quality distribution.
    """
    result = await get_state_quality_summary(db, state_name)

    if "error" in result:
        raise NotFoundError("State", state_name)

    return result
