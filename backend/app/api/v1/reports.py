"""
Reports API: Generate downloadable reports combining multiple analytics.
"""

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.schemas.report import DistrictProfileReportResponse
from app.services import ReportService
from app.validators import validate_cdk, validate_crop

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/district-profile", response_model=DistrictProfileReportResponse)
async def get_district_profile_report(
    cdk: str = Query(..., description="District LGD code"),
    crop: str = Query("wheat", description="Crop to analyze"),
    format: str = Query("json", description="Output format: json or csv"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Generate a comprehensive district profile report.

    Combines metrics, risk profile, efficiency, and forecast data
    into a single downloadable report.
    """
    cdk = validate_cdk(cdk)
    crop = validate_crop(crop)
    output_format = format.lower().strip()
    if output_format not in {"json", "csv"}:
        output_format = "json"

    service = ReportService(db)
    return await service.get_district_profile_report(cdk, crop, output_format)
