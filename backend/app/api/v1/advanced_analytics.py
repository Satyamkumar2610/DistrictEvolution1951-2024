"""
Advanced Analytics API Endpoints.

Provides data science-driven insights including:
- Crop Diversification Index
- Yield Trend Analysis
- Split Impact Comparison
- Crop Correlations
- District Rankings

Updated to use lgd_code/district_lgd schema.
"""


import asyncpg
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.schemas.advanced_analytics import (
    AnalyticsSummaryResponse,
    CropCorrelationMatrixResponse,
    CropDiversificationResponse,
    CropShiftResponse,
    DistrictRankingResponse,
    ResilienceIndexResponse,
    SeasonalComparisonResponse,
    SplitImpactAnalyticsResponse,
    SplitSpecializationResponse,
    YieldForecastResponse,
    YieldGapResponse,
    YieldTrendResponse,
    YoyGrowthResponse,
)
from app.services import AdvancedAnalyticsFacade
from app.validators import (
    validate_cdk,
    validate_cdk_list,
    validate_crop,
    validate_metric,
    validate_state_name,
    validate_year,
    validate_year_range,
)

router = APIRouter(prefix="/analytics", tags=["Advanced Analytics"])


@router.get("/diversification", response_model=CropDiversificationResponse)
async def get_crop_diversification(
    cdk: str = Query(..., description="District LGD code (as text)"),
    year: int = Query(2020, description="Year to analyze"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Get Crop Diversification Index for a district.

    Returns:
    - Herfindahl-Hirschman Index (0-1, lower = more diverse)
    - Simpson's Diversity Index (0-1, higher = more diverse)
    - Number of crops grown
    - Dominant crop and its share
    """
    cdk = validate_cdk(cdk)
    year = validate_year(year)
    service = AdvancedAnalyticsFacade(db)
    return await service.get_crop_diversification_response(cdk, year)


@router.get("/crop-shift", response_model=CropShiftResponse)
async def get_crop_shift_timeline(
    cdk: str = Query(..., description="District LGD code (as text)"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Get full timeline of crop mix shifts and diversity for a district.

    Returns array of yearly data with:
    - total_area
    - shannon_index
    - simpson_index
    - dominant_crop & share
    - crop_mix breakdown (top 5 + other)
    """
    cdk = validate_cdk(cdk)
    service = AdvancedAnalyticsFacade(db)
    return await service.get_crop_shift_response(cdk)


@router.get("/yield-trend", response_model=YieldTrendResponse)
async def get_yield_trend(
    cdk: str = Query(..., description="District LGD code (as text)"),
    crop: str = Query("rice", description="Crop name"),
    start_year: int = Query(1990, description="Start year"),
    end_year: int = Query(2020, description="End year"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Get yield trend analysis with CAGR and volatility.
    """
    cdk = validate_cdk(cdk)
    crop = validate_crop(crop)
    start_year, end_year = validate_year_range(start_year, end_year)
    service = AdvancedAnalyticsFacade(db)
    return await service.get_yield_trend_response(cdk, crop, start_year, end_year)


@router.get("/split-impact", response_model=SplitImpactAnalyticsResponse)
async def get_split_impact(
    parent_cdk: str = Query(..., description="Parent district CDK"),
    child_cdks: str = Query(..., description="Comma-separated child CDKs"),
    split_year: int = Query(..., description="Year of split"),
    crop: str = Query("rice", description="Crop to analyze"),
    years_before: int = Query(5, description="Years before split"),
    years_after: int = Query(5, description="Years after split"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Compare agricultural performance before/after district split.

    Calculates:
    - Average yield before split (parent district)
    - Average yield after split (children districts)
    - Impact assessment (positive/negative/neutral)
    """
    parent_cdk = validate_cdk(parent_cdk)
    children = validate_cdk_list(child_cdks)
    split_year = validate_year(split_year)
    crop = validate_crop(crop)
    service = AdvancedAnalyticsFacade(db)
    return await service.get_split_impact_response(
        parent_cdk,
        children,
        split_year,
        crop,
        years_before,
        years_after,
    )


@router.get("/crop-correlations", response_model=CropCorrelationMatrixResponse)
async def get_crop_correlations(
    state: str = Query(..., description="State name"),
    year: int = Query(2015, description="Year"),
    crops: str | None = Query(None, description="Comma-separated crop list"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Get correlation matrix between crop yields across districts.

    Helps identify:
    - Crop substitution patterns (negative correlation)
    - Complementary crops (positive correlation)
    """
    state = validate_state_name(state)
    year = validate_year(year)
    service = AdvancedAnalyticsFacade(db)

    crop_list = None
    if crops:
        crop_list = [c.strip() for c in crops.split(",")]

    return await service.get_crop_correlations_response(state, year, crop_list)


@router.get("/district-rankings", response_model=list[DistrictRankingResponse])
async def get_district_rankings(
    state: str = Query(..., description="State name"),
    crop: str = Query("rice", description="Crop to rank"),
    year: int = Query(2020, description="Year"),
    metric: str = Query("yield", description="Metric: yield, area, or production"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Get district rankings by crop performance.
    """
    state = validate_state_name(state)
    crop = validate_crop(crop)
    year = validate_year(year)
    metric = validate_metric(metric)
    service = AdvancedAnalyticsFacade(db)
    return await service.get_district_rankings_response(state, crop, year, metric)


@router.get("/yoy-growth", response_model=YoyGrowthResponse)
async def get_yoy_growth(
    cdk: str = Query(..., description="District LGD code (as text)"),
    crop: str = Query("rice", description="Crop name"),
    start_year: int = Query(2010, description="Start year"),
    end_year: int = Query(2020, description="End year"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Get year-over-year yield growth rates.
    """
    cdk = validate_cdk(cdk)
    crop = validate_crop(crop)
    start_year, end_year = validate_year_range(start_year, end_year)
    service = AdvancedAnalyticsFacade(db)
    return await service.get_yoy_growth_response(cdk, crop, start_year, end_year)


@router.get("/seasonal-comparison", response_model=SeasonalComparisonResponse)
async def get_seasonal_comparison(
    cdk: str = Query(..., description="District LGD code (as text)"),
    crop: str = Query("rice", description="Crop name"),
    year: int = Query(2015, description="Year"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Compare Kharif vs Rabi season yields.
    Only available for DES data (1998+).
    """
    cdk = validate_cdk(cdk)
    crop = validate_crop(crop)
    year = validate_year(year)
    service = AdvancedAnalyticsFacade(db)
    return await service.get_seasonal_comparison_response(cdk, crop, year)


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def get_analytics_summary(
    cdk: str = Query(..., description="District LGD code (as text)"),
    year: int = Query(2020, description="Year"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Get comprehensive analytics summary for a district.
    """
    cdk = validate_cdk(cdk)
    year = validate_year(year)
    service = AdvancedAnalyticsFacade(db)
    return await service.get_summary_response(cdk, year)


@router.get("/yield-forecast", response_model=YieldForecastResponse)
async def get_yield_forecast(
    cdk: str = Query(..., description="District LGD code (as text)"),
    crop: str = Query("rice", description="Crop name"),
    forecast_years: int = Query(5, description="Years to forecast"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Project future yields based on historical trends.
    """
    cdk = validate_cdk(cdk)
    crop = validate_crop(crop)
    service = AdvancedAnalyticsFacade(db)
    return await service.get_yield_forecast_response(cdk, crop, forecast_years)


@router.get("/resilience-index", response_model=ResilienceIndexResponse)
async def get_resilience_index(
    state: str = Query(..., description="State name"),
    crop: str = Query("rice", description="Crop name"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Rank districts in a state by lowest yield volatility (highest climate resilience).
    """
    state = validate_state_name(state)
    crop = validate_crop(crop)
    service = AdvancedAnalyticsFacade(db)
    return await service.get_resilience_index_response(state, crop)


@router.get("/yield-gap", response_model=YieldGapResponse)
async def get_yield_gap_analysis(
    state: str = Query(..., description="State name"),
    crop: str = Query(..., description="Crop name"),
    start_year: int = Query(2000, description="Start year"),
    end_year: int = Query(2020, description="End year"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Get the yield gap analysis for a state and crop, comparing districts against the 90th percentile frontier.
    Returns convergence timeline and district rankings.
    """
    state = validate_state_name(state)
    crop = validate_crop(crop)
    start_year, end_year = validate_year_range(start_year, end_year)
    service = AdvancedAnalyticsFacade(db)
    return await service.get_yield_gap_response(state, crop, start_year, end_year)


@router.get("/split-specialization", response_model=SplitSpecializationResponse)
async def get_split_specialization(
    parent_cdk: str = Query(..., description="Parent district LGD code"),
    child_cdks: str = Query(..., description="Comma-separated child CDKs"),
    split_year: int = Query(..., description="Year of the split"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Get post-split economic specialization radar chart data.
    """
    parent_cdk = validate_cdk(parent_cdk)
    children_list = validate_cdk_list(child_cdks)
    split_year = validate_year(split_year)
    service = AdvancedAnalyticsFacade(db)
    return await service.get_split_specialization_response(parent_cdk, children_list, split_year)
