"""
API routes for Lineage Reconstructor Dashboard.
"""

import logging
from fastapi import APIRouter, Depends, Query
import asyncpg

from app.api.deps import get_db
from app.services.reconstructor_service import ReconstructorService
from app.validators import validate_crop, validate_year_range, validate_cdk

logger = logging.getLogger("app.api.lineage_reconstructor")

router = APIRouter(prefix="/reconstructor", tags=["Lineage Reconstructor"])

@router.get("/{cdk}")
async def reconstruct_district_lineage(
    cdk: str,
    crop: str = Query("rice", description="Crop name to analyze"),
    start_year: int = Query(1990, description="Start year of analysis window"),
    end_year: int = Query(2020, description="End year of analysis window"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Reconstruct historical district geometries and aggregate crop yields tracking descendants over time.
    """
    cdk = validate_cdk(cdk)
    crop = validate_crop(crop)
    start_year, end_year = validate_year_range(start_year, end_year)
    
    service = ReconstructorService(db)
    result = await service.reconstruct(cdk, crop, start_year, end_year)
    
    return result
