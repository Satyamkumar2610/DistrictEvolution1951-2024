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
    cdk: str = Field(...,
                     description="Canonical District Key (immutable identifier)")
    name: str = Field(..., description="District display name")
    state: str = Field(..., description="Parent state name")
    valid_from: int | None = Field(
        None, description="Year boundary became effective")
    valid_to: int | None = Field(
        None, description="Year boundary ceased (null = current)")
    geometry: Any | None = Field(
        None, description="GeoJSON geometry (when requested)")

    model_config = ConfigDict(from_attributes=True)


class DistrictList(BaseModel):
    """List of districts with count."""
    total: int = Field(..., description="Total number of districts")
    items: list[District] = Field(default_factory=list)


class DistrictGeoJSON(BaseModel):
    """GeoJSON FeatureCollection for districts."""
    type: str = Field(default="FeatureCollection")
    features: list[Any] = Field(default_factory=list)
