"""
Pydantic schemas for the lineage reconstructor API.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

DataQuality = Literal["direct", "partial", "ancestor_fallback", "no_data"]
ResolutionStatus = Literal["direct", "ancestor", "missing"]


class ReconstructorSearchResult(BaseModel):
    """Search result for a district in the split graph."""

    cdk: str
    display_name: str
    state: str
    era: int | None = None
    is_root: bool


class ReconstructorLineageNode(BaseModel):
    """Recursive lineage tree node returned by the reconstructor UI endpoint."""

    cdk: str
    split_year: int | None = None
    children: list["ReconstructorLineageNode"] = Field(default_factory=list)


class ReconstructorAncestorsResponse(BaseModel):
    """Canonical ancestor query result."""

    cdk: str
    target_year: int | None = None
    ancestors: list[str]
    count: int


class ReconstructorDescendantsResponse(BaseModel):
    """Canonical descendant query result."""

    cdk: str
    from_year: int | None = None
    all_descendants: list[str]
    leaf_descendants: list[str]
    count: int


class ReconstructorGraphSummaryResponse(BaseModel):
    """Summary statistics for the lineage DAG."""

    total_nodes: int
    total_events: int
    root_nodes: int
    leaf_nodes: int
    event_types: dict[str, int]


class ReconstructionCdkResolution(BaseModel):
    """Per-active-CDK data resolution transparency payload."""

    data_cdk: str | None = None
    status: ResolutionStatus


class ReconstructionMetric(BaseModel):
    """Per-year reconstructed metric point."""

    year: int
    data_coverage: float
    collective_yield: float | None = None
    collective_production: float | None = None
    collective_area: float | None = None
    is_fallback: bool
    data_quality: DataQuality


class ReconstructionEpoch(BaseModel):
    """Single reconstructed epoch."""

    epoch_num: int
    year_start: int
    year_end: int | None = None
    event_label: str
    active_cdks: list[str]
    active_names: list[str]
    data_cdks: list[str]
    is_fallback: bool
    data_quality: DataQuality
    confidence_score: float
    cdk_resolution: dict[str, ReconstructionCdkResolution]
    leaf_cdks: list[str]
    is_virtual: bool
    reconstructed_geojson: dict[str, Any] | None = None
    is_contiguous: bool
    metrics: list[ReconstructionMetric]


class ReconstructionResponse(BaseModel):
    """Full lineage reconstruction response."""

    root_cdk: str
    root_name: str | None = None
    crop: str
    epochs: list[ReconstructionEpoch]


ReconstructorLineageNode.model_rebuild()
