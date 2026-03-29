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
from app.exceptions import NotFoundError, ValidationError
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
from app.services.analytics import AdvancedAnalyticsService
from app.validators import validate_cdk, validate_crop, validate_state_name, validate_year, validate_year_range

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
    service = AdvancedAnalyticsService(db)
    result = await service.get_crop_diversification(cdk, year)

    if not result:
        raise NotFoundError("Diversification data", f"{cdk} in {year}")

    return {
        "cdk": result.cdk,
        "year": result.year,
        "cdi": result.simpson_index,
        "herfindahl_index": result.herfindahl_index,
        "simpson_diversity_index": result.simpson_index,
        "interpretation": "diverse" if result.simpson_index > 0.7 else "moderately diverse" if result.simpson_index > 0.4 else "concentrated",
        "crop_count": result.num_crops,
        "num_crops": result.num_crops,
        "dominant_crop": result.dominant_crop,
        "dominant_share": result.dominant_share / 100,
        "dominant_share_percent": result.dominant_share,
        "breakdown": result.breakdown}


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
    service = AdvancedAnalyticsService(db)
    result = await service.get_crop_shift(cdk)

    if not result:
        raise NotFoundError("Crop shift data", cdk)

    return {
        "cdk": cdk,
        "timeline": result
    }


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
    service = AdvancedAnalyticsService(db)
    result = await service.get_yield_trend(cdk, crop, start_year, end_year)

    if not result:
        raise NotFoundError("Yield trend data", f"{crop} in {cdk}")

    return {
        "cdk": cdk,
        "crop": result.crop,
        "period": f"{result.start_year}-{result.end_year}",
        "start_yield_kg_ha": result.start_yield,
        "end_yield_kg_ha": result.end_yield,
        "cagr_percent": result.cagr,
        "volatility_percent": result.volatility,
        "trend": result.trend,
        "risk_assessment": "low" if result.volatility < 10 else "medium" if result.volatility < 25 else "high"
    }


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
    service = AdvancedAnalyticsService(db)
    children = [c.strip() for c in child_cdks.split(",")]

    result = await service.get_split_impact(
        parent_cdk, children, split_year, crop, years_before, years_after
    )

    return result


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
    service = AdvancedAnalyticsService(db)

    crop_list = None
    if crops:
        crop_list = [c.strip() for c in crops.split(",")]

    result = await service.get_crop_correlations(state, year, crop_list)

    return result


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
    service = AdvancedAnalyticsService(db)
    rankings = await service.get_district_rankings(state, crop, year, metric)

    return rankings


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
    service = AdvancedAnalyticsService(db)
    growth_data = await service.get_yoy_growth(cdk, crop, start_year, end_year)

    # Calculate summary stats
    yoy_values = [d['yoy_growth']
                  for d in growth_data if d['yoy_growth'] is not None]
    avg_growth = float(sum(yoy_values) / len(yoy_values)) if yoy_values else 0.0
    positive_years = sum(1 for y in yoy_values if y > 0)

    return {
        "cdk": cdk,
        "crop": crop,
        "period": f"{start_year}-{end_year}",
        "data": growth_data,
        "summary": {
            "average_yoy_growth_percent": float(f"{avg_growth:.2f}"),
            "positive_growth_years": positive_years,
            "negative_growth_years": len(yoy_values) - positive_years
        }
    }


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
    service = AdvancedAnalyticsService(db)
    result = await service.get_seasonal_comparison(cdk, crop, year)

    return result


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def get_analytics_summary(
    cdk: str = Query(..., description="District LGD code (as text)"),
    year: int = Query(2020, description="Year"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Get comprehensive analytics summary for a district.
    """
    service = AdvancedAnalyticsService(db)

    # Gather multiple analytics
    diversification = await service.get_crop_diversification(cdk, year)
    rice_trend = await service.get_yield_trend(cdk, "rice", year - 10, year)
    wheat_trend = await service.get_yield_trend(cdk, "wheat", year - 10, year)

    return {
        "cdk": cdk,
        "year": year,
        "diversification": {
            "index": diversification.simpson_index if diversification else None,
            "num_crops": diversification.num_crops if diversification else 0,
            "dominant_crop": diversification.dominant_crop if diversification else None
        } if diversification else None,
        "trends": {
            "rice": {
                "cagr": rice_trend.cagr if rice_trend else None,
                "trend": rice_trend.trend if rice_trend else None
            } if rice_trend else None,
            "wheat": {
                "cagr": wheat_trend.cagr if wheat_trend else None,
                "trend": wheat_trend.trend if wheat_trend else None
            } if wheat_trend else None
        },
        "data_source": "Hybrid (ICRISAT 1966-1997 + DES 1998-2021)"
    }


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
    service = AdvancedAnalyticsService(db)
    result = await service.get_yield_forecast(cdk, crop, forecast_years)

    if "error" in result:
        raise ValidationError(detail=result["error"])

    return result


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
    service = AdvancedAnalyticsService(db)
    result = await service.get_resilience_index(state, crop)

    if not result:
        raise NotFoundError("Resilience data", state)

    return {
        "state": state,
        "crop": crop,
        "total_districts": len(result),
        "rankings": result
    }


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
    service = AdvancedAnalyticsService(db)
    result = await service.get_yield_gap(state, crop, start_year, end_year)
    if "error" in result:
        raise NotFoundError("Yield gap data", result.get("error", "unknown"))
    return result


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
    children_list = [c.strip() for c in child_cdks.split(",") if c.strip()]
    service = AdvancedAnalyticsService(db)
    return await service.get_post_split_specialization(parent_cdk, children_list, split_year)
