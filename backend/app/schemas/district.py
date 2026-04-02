"""
District Schemas: Temporal entities with validity periods.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class District(BaseModel):
    """
    District as a temporal entity in the lineage graph.
    Tracks validity period for historical boundary awareness.
    """

    cdk: str = Field(..., description="Canonical District Key (immutable identifier)")
    name: str = Field(..., description="District display name")
    state: str = Field(..., description="Parent state name")
    valid_from: int | None = Field(default=None, description="Year boundary became effective")
    valid_to: int | None = Field(default=None, description="Year boundary ceased (null = current)")
    geometry: Any | None = Field(default=None, description="GeoJSON geometry (when requested)")

    model_config = ConfigDict(from_attributes=True)


class DistrictList(BaseModel):
    """List of districts with count."""

    total: int = Field(..., description="Total number of districts")
    items: list[District] = Field(default_factory=list)


class DistrictGeoJSON(BaseModel):
    """GeoJSON FeatureCollection for districts."""

    type: str = Field(default="FeatureCollection")
    features: list[Any] = Field(default_factory=list)


class StateNameList(BaseModel):
    """Simple state-name list response."""

    states: list[str] = Field(default_factory=list)


class StateCount(BaseModel):
    """State and district count."""

    state: str = Field(..., description="Name of the state")
    district_count: int = Field(..., description="Number of districts in the state")


class YearRange(BaseModel):
    min: int | None
    max: int | None


class Performer(BaseModel):
    district_name: str
    cdk: str
    yield_value: float


class StateOverview(BaseModel):
    state: str
    year: int
    crop: str
    total_districts: int
    districts_with_data: int
    year_range: YearRange
    avg_yield: float
    total_area: float
    total_production: float
    top_performers: list[Performer]
    bottom_performers: list[Performer]
    available_crops: list[str]
