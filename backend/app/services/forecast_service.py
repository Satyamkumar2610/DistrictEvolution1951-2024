"""
Forecast application service for API-facing forecasting workflows.

Supports two forecasting strategies:
  1. Prophet + XGBoost ensemble (Phase 2) — when exogenous climate features exist.
  2. SARIMA / Linear fallback (Phase 1) — when only yield history is available.
"""

import logging

import asyncpg

from app.exceptions import NotFoundError, ValidationError
from app.ml.forecaster import CropRecommender, YieldForecaster
from app.repositories.forecast_repo import ForecastRepository
from app.schemas.forecast import CropRecommendationsResponse, YieldForecastResponse

logger = logging.getLogger(__name__)

# Lazy-load ensemble to avoid hard dependency on prophet/xgboost
try:
    from app.ml.ensemble_forecaster import EnsembleForecaster  # noqa: F401

    ENSEMBLE_OK = True
except ImportError:
    ENSEMBLE_OK = False
    logger.info("Ensemble forecaster unavailable — using SARIMA/linear only.")


class ForecastService:
    """Service layer for forecast and crop recommendation APIs."""

    RECOMMENDATION_CROPS = [
        "rice",
        "wheat",
        "maize",
        "sorghum",
        "pearl_millet",
        "chickpea",
        "pigeonpea",
        "groundnut",
        "soyabean",
        "cotton",
    ]

    def __init__(self, conn: asyncpg.Connection):
        self.repo = ForecastRepository(conn)
        self.recommender = CropRecommender()
        self.forecaster = YieldForecaster()

    async def get_crop_recommendations_response(
        self,
        cdk: str,
        top_n: int,
    ) -> CropRecommendationsResponse:
        district = await self.repo.get_district_context(cdk)
        if not district:
            raise NotFoundError("District", cdk)

        crop_performances: dict[str, dict[str, float]] = {}
        for crop in self.RECOMMENDATION_CROPS:
            latest = await self.repo.get_latest_crop_snapshot(cdk, crop)
            if not latest or latest["yield"] is None:
                continue

            trend = await self._calculate_trend(cdk, f"{crop}_yield")
            crop_performances[crop] = {
                "yield": float(latest["yield"]),
                "area": float(latest["area"] or 0),
                "trend": trend,
            }

        if not crop_performances:
            raise ValidationError(detail="No crop data available for this district")

        state = str(district["state_name"])
        state_benchmarks: dict[str, float] = {}
        for crop in self.RECOMMENDATION_CROPS:
            avg = await self.repo.get_state_average_yield(state, crop)
            if avg is not None:
                state_benchmarks[crop] = avg

        recommendations = self.recommender.recommend(
            crop_performances,
            state_benchmarks,
            top_n,
        )

        return CropRecommendationsResponse.model_validate(
            {
                "cdk": cdk,
                "district": str(district["district_name"]),
                "state": state,
                "recommendations": recommendations,
            }
        )

    async def get_yield_forecast_response(
        self,
        cdk: str,
        crop: str,
        horizon: int,
    ) -> YieldForecastResponse:
        district = await self.repo.get_district_context(cdk)
        if not district:
            raise NotFoundError("District", cdk)

        historical = await self.repo.get_historical_yields(cdk, crop)
        if len(historical) < YieldForecaster.LINEAR_MIN_POINTS:
            raise ValidationError(
                detail=(
                    "Insufficient data: need at least "
                    f"{YieldForecaster.LINEAR_MIN_POINTS} years, found {len(historical)}"
                )
            )

        result = self.forecaster.forecast(cdk, crop, historical, horizon)
        if result is None:
            raise ValidationError(detail="Failed to generate forecast")

        return YieldForecastResponse.model_validate(result.to_dict())

    async def _calculate_trend(self, cdk: str, variable: str) -> float:
        """Calculate 5-year CAGR for a variable."""
        rows = await self.repo.get_recent_variable_history(cdk, variable, limit=6)
        if len(rows) < 2:
            return 0.0

        recent = float(rows[0]["value"])
        older = float(rows[-1]["value"])
        years = int(rows[0]["year"]) - int(rows[-1]["year"])

        if older <= 0 or years <= 0:
            return 0.0

        try:
            cagr = ((recent / older) ** (1 / years) - 1) * 100
            return round(cagr, 2)
        except Exception:
            return 0.0
