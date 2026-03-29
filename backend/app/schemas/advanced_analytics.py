"""
Advanced analytics response schemas.
"""

from pydantic import BaseModel, ConfigDict, Field


class CropDiversificationResponse(BaseModel):
    cdk: str
    year: int
    cdi: float
    herfindahl_index: float
    simpson_diversity_index: float
    interpretation: str
    crop_count: int
    num_crops: int
    dominant_crop: str
    dominant_share: float
    dominant_share_percent: float
    breakdown: dict[str, float]


class CropShiftTimelineItem(BaseModel):
    year: int
    total_area: float
    shannon_index: float
    simpson_index: float
    dominant_crop: str
    dominant_share: float
    crop_mix: dict[str, float]


class CropShiftResponse(BaseModel):
    cdk: str
    timeline: list[CropShiftTimelineItem]


class YieldTrendResponse(BaseModel):
    cdk: str
    crop: str
    period: str
    start_yield_kg_ha: float
    end_yield_kg_ha: float
    cagr_percent: float | None
    volatility_percent: float
    trend: str
    risk_assessment: str


class SplitImpactBeforeWindow(BaseModel):
    years: list[int] = Field(default_factory=list)
    yields: list[float] = Field(default_factory=list)
    average: float


class SplitImpactChildWindow(BaseModel):
    yields: list[float] = Field(default_factory=list)
    avg: float


class SplitImpactAfterWindow(BaseModel):
    by_child: dict[str, SplitImpactChildWindow]
    combined_average: float


class SplitImpactAssessment(BaseModel):
    absolute_change: float
    percent_change: float
    assessment: str


class SplitImpactAnalyticsResponse(BaseModel):
    parent_cdk: str
    child_cdks: list[str]
    split_year: int
    crop: str
    before: SplitImpactBeforeWindow
    after: SplitImpactAfterWindow
    impact: SplitImpactAssessment


class CropCorrelationMatrixResponse(BaseModel):
    state: str
    year: int
    crops: list[str]
    correlations: dict[str, dict[str, float | None]]


class DistrictRankingResponse(BaseModel):
    rank: int
    cdk: str
    district: str
    value: float


class YoyGrowthPoint(BaseModel):
    year: int
    yield_: float = Field(alias="yield")
    yoy_growth: float | None


class YoyGrowthSummary(BaseModel):
    average_yoy_growth_percent: float
    positive_growth_years: int
    negative_growth_years: int


class YoyGrowthResponse(BaseModel):
    cdk: str
    crop: str
    period: str
    data: list[YoyGrowthPoint]
    summary: YoyGrowthSummary


class SeasonalComparisonResponse(BaseModel):
    cdk: str
    crop: str
    year: int
    kharif_yield: float | None
    rabi_yield: float | None
    dominant_season: str


class AnalyticsSummaryDiversification(BaseModel):
    index: float | None
    num_crops: int
    dominant_crop: str | None


class AnalyticsSummaryTrend(BaseModel):
    cagr: float | None
    trend: str | None


class AnalyticsSummaryTrends(BaseModel):
    rice: AnalyticsSummaryTrend | None = None
    wheat: AnalyticsSummaryTrend | None = None


class AnalyticsSummaryResponse(BaseModel):
    cdk: str
    year: int
    diversification: AnalyticsSummaryDiversification | None = None
    trends: AnalyticsSummaryTrends
    data_source: str


class YieldForecastPoint(BaseModel):
    year: int
    projected_yield: float
    confidence_interval_lower: float
    confidence_interval_upper: float


class YieldForecastResponse(BaseModel):
    cdk: str
    crop: str
    historical_trend: str
    slope: float
    forecast: list[YieldForecastPoint]


class ResilienceRankingItem(BaseModel):
    cdk: str
    district_name: str
    data_points: int
    avg_yield: float
    avg_shock_drop_pct: float
    avg_recovery_years: float
    resilience_score: float
    rank: int


class ResilienceIndexResponse(BaseModel):
    state: str
    crop: str
    total_districts: int
    rankings: list[ResilienceRankingItem]


class YieldGapTimelinePoint(BaseModel):
    year: int
    frontier_yield: float
    state_avg_yield: float
    avg_gap: float


class YieldGapDistrictRanking(BaseModel):
    cdk: str
    district_name: str
    avg_gap: float
    latest_gap: float
    avg_yield: float
    gap_trend: float
    status: str
    rank: int


class YieldGapResponse(BaseModel):
    state: str
    crop: str
    period: str
    convergence_timeline: list[YieldGapTimelinePoint]
    district_rankings: list[YieldGapDistrictRanking]


class SplitSpecializationParent(BaseModel):
    name: str
    cdk: str
    pre_mix: dict[str, float]


class SplitSpecializationChild(BaseModel):
    cdk: str
    mix: dict[str, float]


class SplitSpecializationResponse(BaseModel):
    split_year: int
    crops: list[str]
    parent: SplitSpecializationParent
    children: dict[str, SplitSpecializationChild]
    divergence_scores: dict[str, float]

    model_config = ConfigDict(extra="allow")
