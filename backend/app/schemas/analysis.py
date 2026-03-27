"""
Analysis Schemas: Split impact and advanced analytics responses.
"""
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ImpactStats, PeriodStats, ProvenanceMetadata


class AnalysisMode(str, Enum):
    """Analysis comparison modes."""
    BEFORE_AFTER = "before_after"
    ENTITY_COMPARISON = "entity_comparison"


class SeriesMeta(BaseModel):
    """Metadata for a chart series."""
    id: str
    label: str
    style: str = Field(
        default="solid",
        description="Line style: solid, dashed, dotted")


class TimelinePoint(BaseModel):
    """Single point in a timeline series."""
    year: int
    value: float | None = None
    # Additional series values stored as dict for multi-series
    series_values: dict[str, float] | None = None


class AdvancedStats(BaseModel):
    """Complete advanced statistics for split impact analysis."""
    pre: PeriodStats = Field(..., description="Pre-split period statistics")
    post: PeriodStats = Field(..., description="Post-split period statistics")
    impact: ImpactStats = Field(..., description="Comparative impact metrics")
    insights: Optional["SplitInsightsInfo"] = Field(
        None, description="Advanced split insights")


# ============================================================================
# NEW: Split Impact Insights Schemas
# ============================================================================

class FragmentationInfo(BaseModel):
    """Fragmentation analysis result."""
    index: float = Field(...,
                         description="1/child_count - lower means more fragmented")
    child_count: int
    interpretation: str


class DivergenceInfo(BaseModel):
    """Child divergence analysis result."""
    score: float = Field(..., description="CV across children's yields")
    interpretation: str
    best_performer: str | None = None
    best_yield: float = 0
    worst_performer: str | None = None
    worst_yield: float = 0
    spread: float = 0


class ConvergenceInfo(BaseModel):
    """Convergence trend analysis result."""
    trend: str = Field(...,
                       description="converging, diverging, stable, or insufficient_data")
    rate: float = Field(..., description="Rate of convergence/divergence")
    interpretation: str


class EffectSizeInfo(BaseModel):
    """Effect size (Cohen's d) result."""
    cohens_d: float
    interpretation: str = Field(...,
                                description="small, medium, large, very_large")
    confidence: float = Field(..., description="0-1 confidence level")


class CounterfactualInfo(BaseModel):
    """Counterfactual projection result."""
    projected_yield: float = Field(...,
                                   description="What yield would have been without split")
    method: str
    actual_yield: float
    attribution_pct: float = Field(...,
                                   description="% of change attributable to split")
    interpretation: str


class ChildPerformanceInfo(BaseModel):
    """Performance metrics for a child district."""
    cdk: str
    name: str | None = None
    mean_yield: float
    cv: float
    cagr: float
    observations: int
    rank: int


class SplitInsightsInfo(BaseModel):
    """Complete split impact insights."""
    fragmentation: FragmentationInfo
    divergence: DivergenceInfo
    convergence: ConvergenceInfo
    effect_size: EffectSizeInfo
    counterfactual: CounterfactualInfo
    children_performance: list[ChildPerformanceInfo] = Field(
        default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AnalysisMeta(BaseModel):
    """Metadata about the analysis performed."""
    split_year: int
    mode: AnalysisMode
    metric: str
    variable: str
    parent_cdk: str
    children_cdks: list[str]


class SplitImpactRequest(BaseModel):
    """Request parameters for split impact analysis."""
    parent_cdk: str = Field(
        ...,
        description="Parent district CDK",
        min_length=5,
        max_length=64,
        pattern=r"^[A-Za-z0-9_]+$"
    )
    children_cdks: list[str] = Field(
        ...,
        description="Children district CDKs",
        min_length=1,
        max_length=20
    )
    split_year: int = Field(
        ...,
        description="Year of split event",
        ge=1947,
        le=2025
    )
    domain: str = Field(
        default="agriculture",
        description="Metric domain",
        max_length=30
    )
    variable: str = Field(
        default="wheat_yield",
        description="Variable to analyze",
        max_length=50
    )
    mode: AnalysisMode = Field(default=AnalysisMode.BEFORE_AFTER)


class SplitImpactResponse(BaseModel):
    """
    Complete response for split impact analysis.
    Includes timeline data, series metadata, advanced statistics,
    and reproducibility provenance.
    """
    data: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Timeline data points"
    )
    series: list[SeriesMeta] = Field(
        default_factory=list,
        description="Series metadata for charting"
    )
    advanced_stats: AdvancedStats | None = Field(
        None,
        description="Statistical analysis (only for before_after mode)"
    )
    meta: AnalysisMeta = Field(..., description="Analysis metadata")
    provenance: ProvenanceMetadata = Field(...,
                                           description="Reproducibility metadata")


class StateSummary(BaseModel):
    """Summary statistics for a state."""
    state: str
    total_districts: int
    boundary_changes: int
    data_coverage: str = Field(default="High")


class SummaryResponse(BaseModel):
    """Response for summary endpoint."""
    states: list[str]
    stats: dict[str, StateSummary]
