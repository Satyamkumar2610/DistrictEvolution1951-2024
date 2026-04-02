"""
Forecast and recommendation response schemas.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict


class ForecastPointResponse(BaseModel):
    year: int
    predicted_yield: float
    lower_bound: float
    upper_bound: float
    confidence: float


class YieldForecastResponse(BaseModel):
    cdk: str
    crop: str
    historical_years: int
    method: str
    trend_direction: str
    forecasts: list[ForecastPointResponse]
    model_stats: dict[str, Any]

    model_config = ConfigDict(protected_namespaces=())


class CropRecommendationItem(BaseModel):
    crop: str
    score: float
    efficiency: float
    current_yield: float
    state_average: float
    current_area: float
    trend_pct: float
    recommendation: str


class CropRecommendationsResponse(BaseModel):
    cdk: str
    district: str
    state: str
    recommendations: list[CropRecommendationItem]
