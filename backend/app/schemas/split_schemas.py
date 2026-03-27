"""
Pydantic schemas for the District Split Area Transfer API.
"""


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
