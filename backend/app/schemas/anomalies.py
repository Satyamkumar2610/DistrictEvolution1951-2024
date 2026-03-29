"""
Anomaly detection response schemas.
"""
from typing import Any

from pydantic import BaseModel


class AnomalyItem(BaseModel):
    anomaly_type: str
    cdk: str
    year: int | None
    variable: str | None
    value: float | None
    expected_range: Any | None
    severity: str
    description: str


class RiskAlertResponse(BaseModel):
    cdk: str
    district_name: str
    risk_level: str
    risk_score: float
    factors: list[str]
    recommendation: str


class DistrictAnomalyReportResponse(BaseModel):
    cdk: str
    total_anomalies: int
    anomalies_by_type: dict[str, int]
    critical_count: int
    high_count: int
    anomalies: list[AnomalyItem]
    risk_alert: RiskAlertResponse | None
    scan_timestamp: str


class StateAnomalyDistrictSummary(BaseModel):
    cdk: str
    district_name: str
    total_anomalies: int
    critical: int
    high: int
    risk_level: str
    risk_score: float


class StateAnomalySummaryResponse(BaseModel):
    state: str
    districts_scanned: int
    total_critical_anomalies: int
    total_high_anomalies: int
    high_risk_districts: list[StateAnomalyDistrictSummary]
    all_districts: list[StateAnomalyDistrictSummary]


class HighRiskDistrictResponse(BaseModel):
    cdk: str
    state: str
    district_name: str
    risk_score: float
    risk_level: str
    factors: list[str]


class HighRiskResponse(BaseModel):
    high_risk_districts: list[HighRiskDistrictResponse]
    total_scanned: int
