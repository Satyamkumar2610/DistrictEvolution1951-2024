"""
Common Schemas: Provenance, Uncertainty, and shared types.
These are included in every analytical response for reproducibility.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class UncertaintyBounds(BaseModel):
    """Confidence interval for a metric value."""

    lower: float = Field(..., description="Lower bound of confidence interval")
    upper: float = Field(..., description="Upper bound of confidence interval")
    method: str = Field(default="bootstrap_95", description="Method used to compute interval")
    confidence: float = Field(default=0.95, description="Confidence level (0-1)")


class ProvenanceMetadata(BaseModel):
    """
    Reproducibility metadata included in every analytical response.
    Enables research-grade traceability and auditability.
    """

    dataset_version: str = Field(..., description="Version of the source dataset")
    boundary_version: str = Field(..., description="Version of boundary definitions")
    query_hash: str = Field(..., description="SHA-256 hash of normalized query params")
    generated_at: datetime = Field(..., description="UTC timestamp of response generation")
    harmonization_method: str | None = Field(None, description="Method used for boundary harmonization")
    warnings: list[str] = Field(default_factory=list, description="Any data quality warnings")


class PeriodStats(BaseModel):
    """Statistical summary for a time period."""

    mean: float = Field(..., description="Arithmetic mean")
    variance: float = Field(default=0, description="Population variance")
    cv: float = Field(default=0, description="Coefficient of variation (%)")
    cagr: float = Field(default=0, description="Compound annual growth rate (%)")
    n_observations: int = Field(default=0, description="Number of data points")


class ImpactStats(BaseModel):
    """Impact analysis comparing pre/post periods."""

    absolute_change: float = Field(..., description="Absolute difference in means")
    pct_change: float = Field(..., description="Percentage change")
    uncertainty: UncertaintyBounds | None = Field(None, description="Confidence interval for impact")
