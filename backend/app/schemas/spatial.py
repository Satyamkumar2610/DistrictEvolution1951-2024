"""
Spatial endpoint response schemas.
"""

from typing import Any

from pydantic import BaseModel


class SpatialContagionTarget(BaseModel):
    cdk: str
    name: str
    cagr: float


class SpatialContagionNeighbor(BaseModel):
    cdk: str
    name: str
    state: str
    cagr: float


class SpatialContagionResponse(BaseModel):
    target: SpatialContagionTarget
    regional_avg_cagr: float
    spillover_category: str
    period: str
    crop: str
    neighbors: list[SpatialContagionNeighbor]


class GenericStatusResponse(BaseModel):
    status: str
    message: str


class SplitAreaCalculationResponse(BaseModel):
    transferred_area_sqkm: float
    remaining_area_sqkm: float


class DistrictLineageResponse(BaseModel):
    district_id: str
    split_events: list[dict[str, Any]]
    area_transfers: list[dict[str, Any]]
