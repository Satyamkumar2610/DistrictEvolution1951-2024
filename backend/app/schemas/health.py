"""
Health and operational response schemas.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LivenessResponse(BaseModel):
    status: str
    timestamp: datetime
    service: str


class HealthChecks(BaseModel):
    database: str


class ReadinessResponse(BaseModel):
    status: str
    timestamp: datetime
    checks: HealthChecks


class YearRangeResponse(BaseModel):
    min: int | None
    max: int | None
    count: int


class DataCoverageMetrics(BaseModel):
    districts: int
    states: int
    metrics_rows: int
    lineage_events: int
    rainfall_records: int
    year_range: YearRangeResponse


class DataQualityMetricsResponse(BaseModel):
    orphan_metric_cdks: int
    integrity_status: str


class HealthMetricsResponse(BaseModel):
    status: str
    timestamp: datetime
    data_coverage: DataCoverageMetrics
    data_quality: DataQualityMetricsResponse


class AppMetricsResponse(BaseModel):
    timestamp: datetime

    model_config = ConfigDict(extra="allow")
