"""
Forecast API Endpoints.
Provides yield forecasting and crop recommendations.
"""

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.exceptions import NotFoundError, ValidationError
from app.ml.forecaster import CropRecommender, YieldForecaster
from app.schemas.forecast import CropRecommendationsResponse, YieldForecastResponse

router = APIRouter(prefix="/forecast", tags=["Forecasting"])


@router.get("/{cdk}/recommend", response_model=CropRecommendationsResponse)
async def get_crop_recommendations(
    cdk: str,
    top_n: int = Query(5, ge=1, le=10, description="Number of recommendations"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Get crop recommendations for a district based on performance and efficiency.
    """
    # Get district info
    district = await db.fetchrow("""
        SELECT lgd_code::text as cdk, state_name, district_name FROM districts WHERE lgd_code::text = $1
    """, cdk)

    if not district:
        raise NotFoundError(detail=f"District not found: {cdk}")

    state = district['state_name']

    # Get major crops for this district
    crops = [
        "rice", "wheat", "maize", "sorghum", "pearl_millet",
        "chickpea", "pigeonpea", "groundnut", "soyabean", "cotton"
    ]

    # Get latest data for each crop
    crop_performances = {}
    for crop in crops:
        # Get latest yield and area
        latest = await db.fetchrow("""
            SELECT
                MAX(CASE WHEN variable_name = $2 THEN value END) as yield,
                MAX(CASE WHEN variable_name = $3 THEN value END) as area
            FROM agri_metrics
            WHERE district_lgd::text = $1 AND year = (
                SELECT MAX(year) FROM agri_metrics
                WHERE district_lgd::text = $1 AND variable_name = $2 AND value > 0
            )
        """, cdk, f"{crop}_yield", f"{crop}_area")

        if latest and latest['yield']:
            # Calculate trend (5-year CAGR)
            trend = await _calculate_trend(db, cdk, f"{crop}_yield")
            crop_performances[crop] = {
                "yield": latest['yield'],
                "area": latest['area'] or 0,
                "trend": trend
            }

    if not crop_performances:
        raise ValidationError(
            detail="No crop data available for this district")

    # Get state benchmarks
    state_benchmarks = {}
    for crop in crops:
        avg = await db.fetchval("""
            SELECT AVG(value)
            FROM agri_metrics m
            JOIN districts d ON m.district_lgd = d.lgd_code
            WHERE d.state_name = $1
            AND m.variable_name = $2
            AND m.value > 0
            AND m.year >= (SELECT MAX(year) - 5 FROM agri_metrics)
        """, state, f"{crop}_yield")
        if avg:
            state_benchmarks[crop] = avg

    recommender = CropRecommender()
    recommendations = recommender.recommend(
        crop_performances, state_benchmarks, top_n)

    return {
        "cdk": cdk,
        "district": district['district_name'],
        "state": state,
        "recommendations": recommendations
    }


@router.get("/{cdk}/{crop}", response_model=YieldForecastResponse)
async def get_yield_forecast(
    cdk: str,
    crop: str,
    horizon: int = Query(3, ge=1, le=10, description="Years to forecast"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Get yield forecast for a specific district and crop.

    Uses SARIMA(1,1,1) when sufficient data (>=10 years) is available,
    with automatic fallback to linear trend extrapolation.
    Returns predictions with confidence intervals.
    """
    # Verify district exists
    exists = await db.fetchval("SELECT 1 FROM districts WHERE lgd_code::text = $1", cdk)
    if not exists:
        raise NotFoundError(detail=f"District not found: {cdk}")

    # Get historical yield data
    yield_var = f"{crop}_yield"
    rows = await db.fetch("""
        SELECT year, value
        FROM agri_metrics
        WHERE district_lgd::text = $1 AND variable_name = $2 AND value > 0
        ORDER BY year
    """, cdk, yield_var)

    if len(rows) < 5:
        raise ValidationError(detail=f"Insufficient data: need at least 5 years, found {len(rows)}")

    historical = {row['year']: row['value'] for row in rows}

    forecaster = YieldForecaster()
    result = forecaster.forecast(cdk, crop, historical, horizon)

    if result is None:
        raise ValidationError(detail="Failed to generate forecast")

    return result.to_dict()


async def _calculate_trend(db: asyncpg.Connection, cdk: str, variable: str) -> float:
    """Calculate 5-year CAGR for a variable."""
    rows = await db.fetch("""
        SELECT year, value
        FROM agri_metrics
        WHERE district_lgd::text = $1 AND variable_name = $2 AND value > 0
        ORDER BY year DESC
        LIMIT 6
    """, cdk, variable)

    if len(rows) < 2:
        return 0.0

    recent = rows[0]['value']
    older = rows[-1]['value']
    years = rows[0]['year'] - rows[-1]['year']

    if older <= 0 or years <= 0:
        return 0.0

    # CAGR = (recent/older)^(1/years) - 1
    try:
        cagr = ((recent / older) ** (1 / years) - 1) * 100
        return round(cagr, 2)
    except Exception:
        return 0.0
