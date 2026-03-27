"""
Lineage Schemas: Graph edges representing administrative changes.
"""
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class EventType(str, Enum):
    """Types of administrative boundary changes."""
    SPLIT = "split"
    MERGE = "merge"
    RENAME = "rename"
    BOUNDARY_ADJUST = "boundary_adjust"


class LineageEvent(BaseModel):
    """
    A single administrative change event (graph edge).
    Represents relationship between parent and children districts.
    """
    id: str = Field(..., description="Unique event identifier")
    parent_cdk: str = Field(..., description="Source district CDK")
    parent_name: str | None = Field(
        None, description="Human-readable parent name")
    children_cdks: list[str] = Field(
        default_factory=list,
        description="Resulting district CDKs")
    children_names: list[str] = Field(
        default_factory=list,
        description="Human-readable child names")
    children_count: int = Field(default=0, description="Number of children")
    event_year: int = Field(..., description="Year of administrative change")
    event_type: EventType = Field(
        default=EventType.SPLIT,
        description="Type of change")
    coverage_ratios: dict[str, float] = Field(
        default_factory=dict,
        description="Area proportion per child (should sum to ~1.0)"
    )
    legal_reference: str | None = Field(
        None, description="Gazette notification reference")
    confidence: float = Field(
        default=1.0,
        ge=0,
        le=1,
        description="Data quality score")

    model_config = ConfigDict(from_attributes=True)


class LineageGraph(BaseModel):
    """Complete lineage graph for a state or region."""
    total_events: int = Field(...,
                              description="Total number of lineage events")
    events: list[LineageEvent] = Field(default_factory=list)


class SplitEventSummary(BaseModel):
    """Summary of split events for dashboard display."""
    id: str
    parent_cdk: str
    parent_name: str
    split_year: int
    children_cdks: list[str]
    children_names: list[str]
    children_count: int
    coverage: str = Field(default="High", description="Data coverage quality")
