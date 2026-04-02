"""
Forecast API Endpoints.
Provides yield forecasting and crop recommendations.
"""

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.schemas.forecast import CropRecommendationsResponse, YieldForecastResponse
from app.services import ForecastService
from app.validators import validate_cdk, validate_crop

router = APIRouter(prefix="/forecast", tags=["Forecasting"])


@router.get("/{cdk}/recommend", response_model=CropRecommendationsResponse)
async def get_crop_recommendations(
    cdk: str,
    top_n: int = Query(5, ge=1, le=10, description="Number of recommendations"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get crop recommendations for a district based on performance and efficiency.
    """
    cdk = validate_cdk(cdk)
    service = ForecastService(db)
    return await service.get_crop_recommendations_response(cdk, top_n)


@router.get("/{cdk}/{crop}", response_model=YieldForecastResponse)
async def get_yield_forecast(
    cdk: str,
    crop: str,
    horizon: int = Query(3, ge=1, le=10, description="Years to forecast"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get yield forecast for a specific district and crop.

    Uses SARIMA(1,1,1) when sufficient data (>=10 years) is available,
    with automatic fallback to linear trend extrapolation.
    Returns predictions with confidence intervals.
    """
    cdk = validate_cdk(cdk)
    crop = validate_crop(crop)
    service = ForecastService(db)
    return await service.get_yield_forecast_response(cdk, crop, horizon)
