"""
Advanced analytics facade for API routes.

This keeps HTTP handlers thin while preserving the existing lower-level
analytics package structure.
"""

import asyncpg

from app.exceptions import NotFoundError, ValidationError
from app.schemas.advanced_analytics import (
    AnalyticsSummaryDiversification,
    AnalyticsSummaryResponse,
    AnalyticsSummaryTrend,
    AnalyticsSummaryTrends,
    CropCorrelationMatrixResponse,
    CropDiversificationResponse,
    CropShiftResponse,
    CropShiftTimelineItem,
    DistrictRankingResponse,
    ResilienceIndexResponse,
    ResilienceRankingItem,
    SeasonalComparisonResponse,
    SplitImpactAnalyticsResponse,
    SplitSpecializationResponse,
    YieldForecastResponse,
    YieldGapDistrictRanking,
    YieldGapResponse,
    YieldGapTimelinePoint,
    YieldTrendResponse,
    YoyGrowthPoint,
    YoyGrowthResponse,
    YoyGrowthSummary,
)
from app.schemas.backcast import BackcastResponse
from app.services.analytics import AdvancedAnalyticsService
from app.ml.yield_backcaster import YieldBackcaster


class AdvancedAnalyticsFacade:
    """API-facing facade over the lower-level analytics service modules."""

    def __init__(self, conn: asyncpg.Connection):
        self.analytics = AdvancedAnalyticsService(conn)

    async def get_crop_diversification_response(
        self,
        cdk: str,
        year: int,
    ) -> CropDiversificationResponse:
        result = await self.analytics.get_crop_diversification(cdk, year)
        if not result:
            raise NotFoundError("Diversification data", f"{cdk} in {year}")

        simpson_index = result.simpson_index
        if simpson_index > 0.7:
            interpretation = "diverse"
        elif simpson_index > 0.4:
            interpretation = "moderately diverse"
        else:
            interpretation = "concentrated"

        return CropDiversificationResponse(
            cdk=result.cdk,
            year=result.year,
            cdi=simpson_index,
            herfindahl_index=result.herfindahl_index,
            simpson_diversity_index=simpson_index,
            interpretation=interpretation,
            crop_count=result.num_crops,
            num_crops=result.num_crops,
            dominant_crop=result.dominant_crop,
            dominant_share=result.dominant_share / 100,
            dominant_share_percent=result.dominant_share,
            breakdown=result.breakdown,
        )

    async def get_crop_shift_response(self, cdk: str) -> CropShiftResponse:
        result = await self.analytics.get_crop_shift(cdk)
        if not result:
            raise NotFoundError("Crop shift data", cdk)

        return CropShiftResponse(
            cdk=cdk,
            timeline=[CropShiftTimelineItem.model_validate(item) for item in result],
        )

    async def get_yield_trend_response(
        self,
        cdk: str,
        crop: str,
        start_year: int,
        end_year: int,
    ) -> YieldTrendResponse:
        result = await self.analytics.get_yield_trend(cdk, crop, start_year, end_year)
        if not result:
            raise NotFoundError("Yield trend data", f"{crop} in {cdk}")

        if result.volatility < 10:
            risk_assessment = "low"
        elif result.volatility < 25:
            risk_assessment = "medium"
        else:
            risk_assessment = "high"

        return YieldTrendResponse(
            cdk=cdk,
            crop=result.crop,
            period=f"{result.start_year}-{result.end_year}",
            start_yield_kg_ha=result.start_yield,
            end_yield_kg_ha=result.end_yield,
            cagr_percent=result.cagr,
            volatility_percent=result.volatility,
            trend=result.trend,
            risk_assessment=risk_assessment,
        )

    async def get_split_impact_response(
        self,
        parent_cdk: str,
        child_cdks: list[str],
        split_year: int,
        crop: str,
        years_before: int,
        years_after: int,
    ) -> SplitImpactAnalyticsResponse:
        result = await self.analytics.get_split_impact(
            parent_cdk,
            child_cdks,
            split_year,
            crop,
            years_before,
            years_after,
        )
        return SplitImpactAnalyticsResponse.model_validate(result)

    async def get_crop_correlations_response(
        self,
        state: str,
        year: int,
        crops: list[str] | None,
    ) -> CropCorrelationMatrixResponse:
        result = await self.analytics.get_crop_correlations(state, year, crops)
        return CropCorrelationMatrixResponse.model_validate(result)

    async def get_district_rankings_response(
        self,
        state: str,
        crop: str,
        year: int,
        metric: str,
    ) -> list[DistrictRankingResponse]:
        result = await self.analytics.get_district_rankings(state, crop, year, metric)
        return [DistrictRankingResponse.model_validate(item) for item in result]

    async def get_yoy_growth_response(
        self,
        cdk: str,
        crop: str,
        start_year: int,
        end_year: int,
    ) -> YoyGrowthResponse:
        growth_data = await self.analytics.get_yoy_growth(cdk, crop, start_year, end_year)
        yoy_values = [
            point["yoy_growth"]
            for point in growth_data
            if point["yoy_growth"] is not None
        ]
        avg_growth = float(sum(yoy_values) / len(yoy_values)) if yoy_values else 0.0
        positive_years = sum(1 for value in yoy_values if value > 0)

        return YoyGrowthResponse(
            cdk=cdk,
            crop=crop,
            period=f"{start_year}-{end_year}",
            data=[YoyGrowthPoint.model_validate(item) for item in growth_data],
            summary=YoyGrowthSummary(
                average_yoy_growth_percent=float(f"{avg_growth:.2f}"),
                positive_growth_years=positive_years,
                negative_growth_years=len(yoy_values) - positive_years,
            ),
        )

    async def get_seasonal_comparison_response(
        self,
        cdk: str,
        crop: str,
        year: int,
    ) -> SeasonalComparisonResponse:
        result = await self.analytics.get_seasonal_comparison(cdk, crop, year)
        return SeasonalComparisonResponse.model_validate(result)

    async def get_summary_response(
        self,
        cdk: str,
        year: int,
    ) -> AnalyticsSummaryResponse:
        diversification = await self.analytics.get_crop_diversification(cdk, year)
        rice_trend = await self.analytics.get_yield_trend(cdk, "rice", year - 10, year)
        wheat_trend = await self.analytics.get_yield_trend(cdk, "wheat", year - 10, year)

        return AnalyticsSummaryResponse(
            cdk=cdk,
            year=year,
            diversification=(
                AnalyticsSummaryDiversification(
                    index=diversification.simpson_index,
                    num_crops=diversification.num_crops,
                    dominant_crop=diversification.dominant_crop,
                )
                if diversification
                else None
            ),
            trends=AnalyticsSummaryTrends(
                rice=(
                    AnalyticsSummaryTrend(
                        cagr=rice_trend.cagr,
                        trend=rice_trend.trend,
                    )
                    if rice_trend
                    else None
                ),
                wheat=(
                    AnalyticsSummaryTrend(
                        cagr=wheat_trend.cagr,
                        trend=wheat_trend.trend,
                    )
                    if wheat_trend
                    else None
                ),
            ),
            data_source="Hybrid (ICRISAT 1966-1997 + DES 1998-2021)",
        )

    async def get_yield_forecast_response(
        self,
        cdk: str,
        crop: str,
        forecast_years: int,
    ) -> YieldForecastResponse:
        result = await self.analytics.get_yield_forecast(cdk, crop, forecast_years)
        if "error" in result:
            raise ValidationError(detail=result["error"])
        return YieldForecastResponse.model_validate(result)

    async def get_resilience_index_response(
        self,
        state: str,
        crop: str,
    ) -> ResilienceIndexResponse:
        result = await self.analytics.get_resilience_index(state, crop)
        if not result:
            raise NotFoundError("Resilience data", state)

        return ResilienceIndexResponse(
            state=state,
            crop=crop,
            total_districts=len(result),
            rankings=[ResilienceRankingItem.model_validate(item) for item in result],
        )

    async def get_yield_gap_response(
        self,
        state: str,
        crop: str,
        start_year: int,
        end_year: int,
    ) -> YieldGapResponse:
        result = await self.analytics.get_yield_gap(state, crop, start_year, end_year)
        if "error" in result:
            raise NotFoundError("Yield gap data", result.get("error", "unknown"))

        return YieldGapResponse(
            state=str(result["state"]),
            crop=str(result["crop"]),
            period=str(result["period"]),
            convergence_timeline=[
                YieldGapTimelinePoint.model_validate(item)
                for item in result["convergence_timeline"]
            ],
            district_rankings=[
                YieldGapDistrictRanking.model_validate(item)
                for item in result["district_rankings"]
            ],
        )

    async def get_split_specialization_response(
        self,
        parent_cdk: str,
        child_cdks: list[str],
        split_year: int,
    ) -> SplitSpecializationResponse:
        result = await self.analytics.get_split_specialization(parent_cdk, child_cdks, split_year)
        if not result or "error" in result:
            raise NotFoundError("Specialization data", parent_cdk)
            
        return SplitSpecializationResponse(**result)

    async def get_backcast_response(
        self,
        parent_cdk: str,
        child_cdks: list[str],
        split_year: int,
        crop: str,
        start_year: int
    ) -> BackcastResponse:
        backcaster = YieldBackcaster()
        result = await backcaster.backcast_all_children(
            parent_cdk=parent_cdk,
            child_cdks=child_cdks,
            split_year=split_year,
            crop=crop,
            start_year=start_year
        )
        return result
