"""
Metric Schemas: Domain-agnostic observation data.
"""
from enum import StrEnum

from pydantic import BaseModel, Field


class MetricDomain(StrEnum):
    """Supported metric domains."""
    AGRICULTURE = "agriculture"
    CLIMATE = "climate"
    HEALTH = "health"
    SOCIOECONOMIC = "socioeconomic"


class MetricPoint(BaseModel):
    """Single observation point."""
    cdk: str = Field(..., description="District CDK")
    year: int = Field(..., description="Observation year")
    variable: str = Field(..., description="Variable name (e.g., wheat_yield)")
    value: float = Field(..., description="Observed value")
    unit: str | None = Field(None, description="Measurement unit")
    source: str | None = Field(None, description="Dataset source")
    method: str | None = Field(
        None, description="Harmonization method if derived")


class MetricTimeSeries(BaseModel):
    """Time series for a single district and variable."""
    cdk: str
    district_name: str | None = None
    variable: str
    unit: str | None = None
    data: list[dict] = Field(
        default_factory=list,
        description="List of {year, value} points")


class MetricQueryResult(BaseModel):
    """Result of a metrics query."""
    total: int
    items: list[MetricPoint] = Field(default_factory=list)


class AggregatedMetric(BaseModel):
    """Metric value with district metadata for choropleth display."""
    cdk: str
    state: str
    district: str
    value: float
    metric: str
    method: str | None = Field(None, description="Backcast or Raw")
    geo_key: str | None = Field(
        None,
        description="Pre-computed GeoJSON key (DISTRICT|STATE) for map visualization")
