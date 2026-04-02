"""
Simulation and prediction response schemas.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.analytics.advanced import SimulationResult


class SimulationResponse(BaseModel):
    district: str
    state: str
    crop: str
    result: SimulationResult
    note: str
    validity: dict[str, Any] | None = None


class PredictionFactorResponse(BaseModel):
    name: str
    key: str
    importance: float
    coefficient: float
    contribution: float
    direction: str
    description: str


class PredictionPointResponse(BaseModel):
    rain: float
    yield_: float = Field(alias="yield")
    district: str


class RegressionLinePoint(BaseModel):
    x: float
    y: float


class PredictionPayloadResponse(BaseModel):
    predicted_yield: float
    baseline_yield: float
    confidence_lower: float
    confidence_upper: float
    slope_rain: float
    mean_rain: float
    r_squared: float
    adjusted_r_squared: float
    rmse: float
    sample_size: int
    feature_count: int
    method: str
    factors: list[PredictionFactorResponse]
    model_equation: str
    methodology: str
    data_quality_notes: list[str]
    data_points: list[PredictionPointResponse]
    regression_line: list[RegressionLinePoint]

    model_config = ConfigDict(protected_namespaces=())


class PredictionV2Response(BaseModel):
    district: str
    state: str
    crop: str
    year: int
    prediction: PredictionPayloadResponse
    validity: dict[str, Any]
