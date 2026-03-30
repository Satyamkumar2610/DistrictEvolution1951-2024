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
    unit: str | None = Field(default=None, description="Measurement unit")
    source: str | None = Field(default=None, description="Dataset source")
    method: str | None = Field(
        default=None, description="Harmonization method if derived")


class MetricTimeSeries(BaseModel):
    """Time series for a single district and variable."""
    cdk: str
    district_name: str | None = None
    variable: str
    unit: str | None = None
    data: list[dict] = Field(
        default_factory=list,
        description="List of {year, value} points")


class MetricHistoryPoint(BaseModel):
    """Pivoted metric history row for charts and tables."""
    year: int = Field(..., description="Observation year")
    area: float = Field(default=0, description="Area for the selected crop")
    production: float = Field(default=0, description="Production for the selected crop")
    yield_: float = Field(default=0, alias="yield", description="Yield for the selected crop")


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
    feature_id: str | None = Field(
        None,
        description="Stable map feature identifier resolved by the backend")
    geo_key: str | None = Field(
        None,
        description="Deprecated alias for the resolved map feature identifier")
