"""
Data quality response schemas.
"""

from pydantic import BaseModel


class DataQualityDistrictResponse(BaseModel):
    cdk: str
    completeness_score: float
    consistency_score: float
    timeliness_score: float
    accuracy_score: float
    overall_score: float
    quality_level: str
    issues: list[str]
    recommendations: list[str]


class StateQualitySummaryResponse(BaseModel):
    state: str
    districts_analyzed: int
    average_quality_score: float
    quality_distribution: dict[str, int]
    top_issues: list[str]
