"""
Anomaly application service for API-facing anomaly workflows.
"""

from typing import TypedDict

import asyncpg

from app.analytics.anomaly_detection import AnomalyDetector, scan_state_anomalies
from app.exceptions import NotFoundError
from app.repositories.anomaly_repo import AnomalyRepository
from app.schemas.anomalies import (
    DistrictAnomalyReportResponse,
    HighRiskResponse,
    StateAnomalySummaryResponse,
)


class HighRiskDistrictItem(TypedDict):
    cdk: str
    state: str
    district_name: str
    risk_score: float
    risk_level: str
    factors: list[str]


class AnomalyService:
    """Service layer for anomaly detection APIs."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn
        self.repo = AnomalyRepository(conn)
        self.detector = AnomalyDetector(conn)

    async def scan_district_response(self, cdk: str) -> DistrictAnomalyReportResponse:
        """Run a full anomaly scan for a district."""
        if not await self.repo.district_exists(cdk):
            raise NotFoundError("District", cdk)

        report = await self.detector.scan_district(cdk)
        return DistrictAnomalyReportResponse.model_validate(report.to_dict())

    async def scan_state_response(
        self,
        state_name: str,
        limit: int,
    ) -> StateAnomalySummaryResponse:
        """Run anomaly scanning across districts within a state."""
        result = await scan_state_anomalies(self.conn, state_name, limit)
        if "error" in result:
            raise NotFoundError("State anomaly scan", state_name, detail=str(result["error"]))

        return StateAnomalySummaryResponse.model_validate(result)

    async def get_high_risk_districts_response(self, limit: int) -> HighRiskResponse:
        """Scan a sample of active districts and return the highest-risk subset."""
        scan_limit = min(limit * 3, 30)
        districts = await self.repo.get_active_district_sample(scan_limit)

        high_risk: list[HighRiskDistrictItem] = []
        for district in districts:
            report = await self.detector.scan_district(district["cdk"])
            if report.risk_alert and report.risk_alert.risk_score >= 30:
                high_risk.append(
                    HighRiskDistrictItem(
                        cdk=district["cdk"],
                        state=district["state_name"],
                        district_name=report.risk_alert.district_name,
                        risk_score=report.risk_alert.risk_score,
                        risk_level=report.risk_alert.risk_level.value,
                        factors=report.risk_alert.factors,
                    )
                )

        high_risk.sort(key=lambda item: -item["risk_score"])

        return HighRiskResponse.model_validate(
            {
                "high_risk_districts": high_risk[:limit],
                "total_scanned": scan_limit,
            }
        )
