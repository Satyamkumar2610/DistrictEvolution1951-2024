"""
Pydantic schemas for ML Yield Backcasting.
"""

from typing import Any

from pydantic import BaseModel, Field


class BackcastYearPoint(BaseModel):
    """A single predicted yield point for a pre-split year."""

    year: int = Field(..., description="The pre-split year being predicted")
    predicted_yield: float = Field(..., description="The predicted yield value")
    confidence: float = Field(..., description="Confidence score (0.0 to 1.0) of the prediction")
    lower_bound: float = Field(..., description="Lower bound of prediction interval")
    upper_bound: float = Field(..., description="Upper bound of prediction interval")
    method: str = Field(..., description="Method used: 'ml', 'ridge', 'ratio', or 'apportioned'")


class BackcastChildResult(BaseModel):
    """Backcasting results for a single child district."""

    child_cdk: str = Field(..., description="CDK of the child district")
    backcasted_yields: list[BackcastYearPoint] = Field(..., description="List of predicted pre-split yields")
    model_stats: dict[str, Any] = Field(..., description="Evaluation metrics (e.g., r_squared, rmse) for the model")
    features_used: list[str] = Field(..., description="List of features used in the prediction")
    feature_importances: dict[str, float] = Field(
        default_factory=dict, description="Relative importance of each feature"
    )


class ConservationCheck(BaseModel):
    """Validation of extensive property conservation (mass balance)."""

    is_valid: bool = Field(..., description="Whether the conservation constraint is met within tolerance")
    relative_error: float = Field(..., description="Relative error in production matching")
    parent_total_production: float = Field(..., description="Total production of the parent district")
    children_sum_production: float = Field(..., description="Sum of backcasted production for all children")


class BackcastResponse(BaseModel):
    """Complete response for backcasting a parent district's yield to its children."""

    parent_cdk: str = Field(..., description="CDK of the parent district")
    split_year: int = Field(..., description="Year the split occurred")
    crop: str = Field(..., description="Crop being analyzed")
    method: str = Field(..., description="Primary prediction method used across children")
    children: dict[str, BackcastChildResult] = Field(..., description="Mapping of child CDK to its backcast results")
    conservation_check: ConservationCheck = Field(
        ..., description="Validation that sum of children approximates parent"
    )
