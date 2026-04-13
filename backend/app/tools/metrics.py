"""
Domain tool: query_metric

Retrieves time-series agricultural metrics for a single district
from the district_metrics table, including harmonization metadata.
"""

from __future__ import annotations

import asyncpg
from pydantic import BaseModel


class MetricRow(BaseModel):
    """A single metric data point with harmonization disclosure."""

    year: int
    value: float
    is_harmonized: bool
    confidence: float
    parent_district_name: str | None


async def query_metric(
    conn: asyncpg.Connection,
    unit_id: str,
    metric: str,
    year_start: int,
    year_end: int,
) -> list[MetricRow]:
    """
    Retrieve a time series of an agricultural metric for one district.

    Joins district_metrics with admin_units to resolve the parent district
    name from the first edge in the provenance_path (for AI citations).

    Args:
        conn: Database connection
        unit_id: District UUID (admin_units.id)
        metric: Metric name (e.g., 'wheat_yield_kg_ha')
        year_start: Start year (inclusive)
        year_end: End year (inclusive)

    Returns:
        List of MetricRow with value, harmonization status, and confidence.
    """
    rows = await conn.fetch(
        """
        SELECT dm.year, dm.value, dm.is_harmonized,
               dm.cumulative_confidence as confidence,
               au.name as parent_district_name
        FROM district_metrics dm
        LEFT JOIN LATERAL (
            SELECT u.name FROM admin_units u
            WHERE u.id = (dm.provenance_path[1])::uuid
        ) au ON true
        WHERE dm.unit_id = $1
          AND dm.metric = $2
          AND dm.year BETWEEN $3 AND $4
        ORDER BY dm.year
        """,
        unit_id,
        metric,
        year_start,
        year_end,
    )
    return [MetricRow(**dict(r)) for r in rows]
