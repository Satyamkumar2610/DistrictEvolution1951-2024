"""
Health Check API Endpoints.
Provides liveness, readiness, and data quality metrics.
"""

from datetime import UTC, datetime
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends

from app.database import get_db
from app.metrics import metrics

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness() -> dict[str, Any]:
    """
    Basic liveness check.
    Returns 200 if the service is running.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "service": "i-ascap-backend"
    }


@router.get("/ready")
async def readiness(db: asyncpg.Connection = Depends(get_db)) -> dict[str, Any]:
    """
    Readiness check - verifies database connectivity.
    Returns 200 if all dependencies are ready.
    """
    try:
        # Test database connection
        db_result = await db.fetchval("SELECT 1")
        db_status = "connected" if db_result == 1 else "error"
    except Exception as e:
        db_status = f"error: {str(e)}"

    is_ready = db_status == "connected"

    return {
        "status": "ready" if is_ready else "not_ready",
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": {
            "database": db_status
        }
    }


@router.get("/metrics")
async def data_metrics(db: asyncpg.Connection = Depends(get_db)) -> dict[str, Any]:
    """
    Data quality and coverage metrics.
    Returns statistics about loaded data.
    """
    # Get table counts
    districts_count = await db.fetchval("SELECT COUNT(*) FROM districts")
    metrics_count = await db.fetchval("SELECT COUNT(*) FROM agri_metrics")
    lineage_count = await db.fetchval("SELECT COUNT(*) FROM lineage_events")

    # Check for rainfall table
    try:
        rainfall_count = await db.fetchval("SELECT COUNT(*) FROM rainfall_normals")
    except Exception:
        rainfall_count = 0

    # Get year coverage
    year_stats = await db.fetchrow("""
        SELECT MIN(year) as min_year, MAX(year) as max_year, COUNT(DISTINCT year) as year_count
        FROM agri_metrics
    """)

    # Get state coverage
    state_count = await db.fetchval("SELECT COUNT(DISTINCT state_name) FROM districts")

    # Data quality: check for missing CDKs in metrics
    orphan_metrics = await db.fetchval("""
        SELECT COUNT(DISTINCT district_lgd)
        FROM agri_metrics m
        WHERE NOT EXISTS (SELECT 1 FROM districts d WHERE d.lgd_code = m.district_lgd)
    """)

    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "data_coverage": {
            "districts": districts_count,
            "states": state_count,
            "metrics_rows": metrics_count,
            "lineage_events": lineage_count,
            "rainfall_records": rainfall_count,
            "year_range": {
                "min": year_stats["min_year"] if year_stats else None,
                "max": year_stats["max_year"] if year_stats else None,
                "count": year_stats["year_count"] if year_stats else 0
            }
        },
        "data_quality": {
            "orphan_metric_cdks": orphan_metrics,
            "integrity_status": "good" if orphan_metrics == 0 else "issues_detected"
        }
    }


@router.get("/app-metrics")
async def app_metrics() -> dict[str, Any]:
    """
    Application performance metrics.

    Returns latency percentiles, cache stats, database stats, and more.
    """
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        **metrics.get_all_metrics()
    }
