"""
Schemas for counterfactual district disaggregation.
"""

from pydantic import BaseModel, Field


class DisaggregationSource(BaseModel):
    """Provenance source attached to a packet."""

    source_url: str = Field(..., description="Source URL or identifier")
    source_label: str | None = Field(default=None, description="Human-readable source label")
    source_type: str | None = Field(default=None, description="Source category")
    is_primary: bool = Field(default=False, description="Whether this is the primary source")


class SplitEventWeight(BaseModel):
    """A single child allocation weight for an event."""

    child_cdk: str
    child_name: str | None = None
    metric_basis: str
    weight_value: float
    weight_method: str
    weight_confidence: float
    source_year: int | None = None
    basis: str
    is_fallback: bool = False


class DisaggregationEventSummary(BaseModel):
    """Compact event summary for list endpoints."""

    event_id: str
    parent_cdk: str
    parent_name: str | None = None
    child_cdks: list[str] = Field(default_factory=list)
    child_names: list[str] = Field(default_factory=list)
    state: str
    split_year: int
    effective_date: str | None = None
    event_type: str
    readiness_tier: str
    source_quality: str
    geometry_status: str
    weight_status: str
    warnings: list[str] = Field(default_factory=list)


class DisaggregationEventListResponse(BaseModel):
    """Paginated list response."""

    total: int
    items: list[DisaggregationEventSummary] = Field(default_factory=list)


class DisaggregationEventDetail(DisaggregationEventSummary):
    """Full packet detail response."""

    split_event_id: int | None = None
    source_urls: list[str] = Field(default_factory=list)
    source_text_path: str | None = None
    aliases: list[str] = Field(default_factory=list)
    notes: str | None = None
    sources: list[DisaggregationSource] = Field(default_factory=list)
    weights: list[SplitEventWeight] = Field(default_factory=list)
    methodology_note: str | None = None


class EstimatePoint(BaseModel):
    """Single estimated or observed point."""

    year: int
    value: float
    is_estimated: bool
    method: str
    confidence: float
    lower_bound: float
    upper_bound: float
    provenance_ref: str


class ParentSeries(BaseModel):
    """Parent timeline payload."""

    cdk: str
    name: str | None = None
    metric: str
    points: list[EstimatePoint] = Field(default_factory=list)


class ChildSeriesEstimate(BaseModel):
    """Child timeline payload."""

    child_cdk: str
    child_name: str | None = None
    metric: str
    weight_method: str | None = None
    weight_confidence: float | None = None
    points: list[EstimatePoint] = Field(default_factory=list)


class DisaggregationSeriesResponse(BaseModel):
    """Series response for the disaggregation API."""

    event_id: str
    crop: str
    metric: str
    readiness_tier: str
    readiness_status: str
    parent_series: ParentSeries
    child_series: list[ChildSeriesEstimate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    methodology_note: str | None = None
