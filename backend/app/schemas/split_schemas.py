"""
Pydantic schemas for the District Split Area Transfer API.
"""

from typing import Any

from pydantic import BaseModel, Field

# ── Request Models ─────────────────────────────────────────────────────────

class SplitDiffRequest(BaseModel):
    """Request body for POST /api/v1/spatial/diff"""
    parent_cdk: str = Field(
        ...,
        description="CDK of the parent district (before split)",
        examples=["TG_adilab_2011"],
    )
    child_cdks: list[str] = Field(
        ...,
        min_length=1,
        description="List of CDKs for child districts (after split)",
        examples=[["TG_kumura_2024", "TG_manche_2024", "TG_nirmal_2024"]],
    )
    split_year: int = Field(
        ...,
        ge=1950,
        le=2030,
        description="Year of the split event",
        examples=[2024],
    )


class GeoJsonUploadRequest(BaseModel):
    """Request body for POST /api/v1/spatial/upload-geojson"""
    district_cdk: str = Field(
        ...,
        description="CDK of the district this geometry belongs to",
    )
    snapshot_year: int = Field(
        ...,
        ge=1950,
        le=2030,
        description="Year this boundary represents",
    )
    geojson: dict = Field(
        ...,
        description=(
            "GeoJSON geometry or Feature or FeatureCollection. "
            "Must contain valid Polygon or MultiPolygon geometry."
        ),
    )


# ── Response Models ────────────────────────────────────────────────────────

class TransferDetail(BaseModel):
    """A single classified sub-region from the diff."""
    from_district: str
    to_district: str
    transfer_type: str
    area_sqkm: float
    confidence_score: float


class SplitDiffResponse(BaseModel):
    """Response for POST /api/v1/spatial/diff"""
    success: bool = True
    event_id: int | None = Field(None, description="ID of the created split_events row")
    parent_cdk: str
    child_cdks: list[str]
    split_year: int
    parent_area_sqkm: float
    total_child_area_sqkm: float
    area_conservation_error: float
    composite_confidence: float
    geometry_status: str
    transfers: list[TransferDetail]
    warnings: list[str]
    geojson: dict = Field(
        description="GeoJSON FeatureCollection of all transfer polygons"
    )


class LineageNode(BaseModel):
    """A node in the lineage tree."""
    district_cdk: str
    district_name: str
    year_created: int | None = None
    year_dissolved: int | None = None
    area_sqkm: float | None = None
    geometry_source: str | None = None
    geometry_confidence: float | None = None
    children: list["LineageNode"] = Field(default_factory=list)


class LineageResponse(BaseModel):
    """Response for GET /api/v1/spatial/lineage/{district_cdk}"""
    success: bool = True
    root: LineageNode
    total_nodes: int
    total_split_events: int


class UploadResponse(BaseModel):
    """Response for POST /api/v1/spatial/upload-geojson"""
    success: bool = True
    district_cdk: str
    snapshot_year: int
    geometry_source: str
    geometry_confidence: float
    area_sqkm: float | None = None
    message: str


class EnrichmentMetric(BaseModel):
    """Single enrichment metric attached to an area transfer."""

    dataset: str
    metric: str
    value: float | None = None
    unit: str | None = None
    reference_year: int | None = None
    source_url: str | None = None


class EnrichmentTransfer(BaseModel):
    """Grouped enrichment payload for a transfer."""

    transfer_id: int
    from_district: str
    to_district: str
    transfer_type: str
    transfer_area_sqkm: float
    metrics: list[EnrichmentMetric]


class EnrichmentResponse(BaseModel):
    """Response for GET /api/v1/spatial/enrichment/{event_id}."""

    success: bool = True
    event_id: int
    parent_cdk: str
    split_year: int
    total_enrichment_rows: int
    transfers: list[EnrichmentTransfer]


class EnrichmentTriggerResponse(BaseModel):
    """Response for POST /api/v1/spatial/enrichment/trigger."""

    success: bool = True
    message: str | None = None
    result: dict[str, Any] | None = None


class GazetteParsedEvent(BaseModel):
    """Structured split event extracted from gazette text."""

    parent_district: str
    child_districts: list[str]
    year: int
    state: str | None = None
    confidence: float
    raw_text: str


class GazetteParseResponse(BaseModel):
    """Response for POST /api/v1/spatial/gazette/parse."""

    success: bool = True
    parsed_events: list[GazetteParsedEvent]
    total: int


class BatchImportSampleEvent(BaseModel):
    """Dry-run preview sample event."""

    parent: str
    year: int
    children: list[str]
    state: str | None = None


class BatchImportResponse(BaseModel):
    """Response for POST /api/v1/spatial/lineage/batch-import."""

    success: bool = True
    dry_run: bool | None = None
    source: str | None = None
    total_csv_rows: int | None = None
    unique_events: int | None = None
    inserted: int | None = None
    skipped: int | None = None
    unresolved_parents: int | None = None
    loaded: int | None = None
    error: str | None = None
    sample_events: list[BatchImportSampleEvent] | None = None


class DriftTimelineItem(BaseModel):
    """Pairwise drift metrics between two snapshots."""

    year_a: int
    year_b: int
    hausdorff_km: float
    area_a_sqkm: float
    area_b_sqkm: float
    area_change_pct: float
    jaccard_index: float
    centroid_shift_km: float
    shape_similarity: float


class DriftResponse(BaseModel):
    """Response for GET /api/v1/spatial/drift/{district_cdk}."""

    success: bool = True
    district_cdk: str
    timeline: list[DriftTimelineItem] | None = None
    total_comparisons: int | None = None
    year_a: int | None = None
    year_b: int | None = None
    hausdorff_km: float | None = None
    area_a_sqkm: float | None = None
    area_b_sqkm: float | None = None
    area_change_pct: float | None = None
    overlap_area_sqkm: float | None = None
    jaccard_index: float | None = None
    centroid_shift_km: float | None = None
    shape_similarity: float | None = None
    source_a: str | None = None
    source_b: str | None = None


class TransferTypeSummary(BaseModel):
    """Aggregate transfer-type count/area breakdown."""

    type: str
    count: int
    total_area_sqkm: float


class DistrictQualityOverview(BaseModel):
    """District geometry coverage summary."""

    total: int
    with_geometry: int
    geometry_coverage_pct: float


class SplitEventQualityOverview(BaseModel):
    """Split-event status and confidence summary."""

    total: int
    by_status: dict[str, int]
    confidence_distribution: dict[str, int]


class TransferQualityOverview(BaseModel):
    """Area transfer summary."""

    total: int
    by_type: list[TransferTypeSummary]


class EnrichmentQualityOverview(BaseModel):
    """Enrichment table summary."""

    total_rows: int
    events_enriched: int


class QualityOverviewResponse(BaseModel):
    """Response for GET /api/v1/spatial/quality/overview."""

    success: bool = True
    districts: DistrictQualityOverview
    split_events: SplitEventQualityOverview
    transfers: TransferQualityOverview
    enrichment: EnrichmentQualityOverview
    geometry_sources: dict[str, int]
