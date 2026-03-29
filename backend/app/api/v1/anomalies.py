"""
Anomaly Detection API Endpoints.
Provides anomaly scanning and risk assessment for districts.
"""

import asyncpg
from fastapi import APIRouter, Depends

from app.analytics.anomaly_detection import AnomalyDetector, scan_state_anomalies
from app.database import get_db
from app.exceptions import NotFoundError
from app.schemas.anomalies import (
    DistrictAnomalyReportResponse,
    HighRiskResponse,
    StateAnomalySummaryResponse,
)

router = APIRouter(prefix="/anomalies", tags=["Anomaly Detection"])


@router.get("/district/{cdk}", response_model=DistrictAnomalyReportResponse)
async def scan_district_anomalies(
    cdk: str,
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Run full anomaly scan for a specific district.

    Detects:
    - Yield outliers (> 3 std from state mean)
    - Year-over-year spikes (> 50% change)
    - Missing data sequences (> 3 consecutive years)
    - Consistency errors (production ≠ area × yield)
    - Invalid values (negative/zero where unexpected)

    Also generates a risk alert with severity assessment.
    """
    # Verify district exists
    exists = await db.fetchval("SELECT 1 FROM districts WHERE lgd_code::text = $1", cdk)
    if not exists:
        raise NotFoundError(detail=f"District not found: {cdk}")

    detector = AnomalyDetector(db)
    report = await detector.scan_district(cdk)

    return report.to_dict()


@router.get("/state/{state_name}", response_model=StateAnomalySummaryResponse)
async def scan_state(
    state_name: str,
    limit: int = 20,
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Scan all districts in a state for anomalies.

    Returns aggregated anomaly counts and identifies high-risk districts.
    Limited to 20 districts by default for performance.
    """
    result = await scan_state_anomalies(db, state_name, limit)

    if "error" in result:
        raise NotFoundError(detail=result["error"])

    return result


@router.get("/high-risk", response_model=HighRiskResponse)
async def get_high_risk_districts(
    limit: int = 10,
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Get districts with highest risk scores across all states.

    Scans a sample of districts and returns those with highest risk.
    """
    # Sample random districts to avoid Vercel 10s timeout from N+1 queries
    # Scan twice the requested limit to find enough anomalies
    scan_limit = min(limit * 3, 30)
    districts = await db.fetch("""
        SELECT lgd_code::text as cdk, state_name, district_name
        FROM districts
        WHERE end_year IS NULL
        ORDER BY RANDOM()
        LIMIT $1
    """, scan_limit)

    all_high_risk = []
    detector = AnomalyDetector(db)

    for dist in districts:
        report = await detector.scan_district(dist['cdk'])
        if report.risk_alert and report.risk_alert.risk_score >= 30:
            all_high_risk.append({
                "cdk": dist['cdk'],
                "state": dist['state_name'],
                "district_name": report.risk_alert.district_name,
                "risk_score": report.risk_alert.risk_score,
                "risk_level": report.risk_alert.risk_level.value,
                "factors": report.risk_alert.factors
            })

    # Sort by risk score and return top N
    all_high_risk.sort(key=lambda x: -x['risk_score'])

    return {
        "high_risk_districts": all_high_risk[:limit],
        "total_scanned": scan_limit
    }
