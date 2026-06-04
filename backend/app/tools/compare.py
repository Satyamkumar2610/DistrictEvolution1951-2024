"""
Domain tool: compare_metrics

Compare a metric across multiple districts for specified years,
with harmonization disclosure for each data point.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ComparisonRow(BaseModel):
    """A single comparison data point."""

    unit_id: str
    district_name: str
    year: int
    value: float
    is_harmonized: bool
    confidence: float


async def compare_metrics(
    conn: Any,
    unit_ids: list[str],
    metric: str,
    years: list[int],
) -> list[ComparisonRow]:
    """
    Compare a metric across multiple districts for specified years.

    Args:
        conn: Database connection
        unit_ids: List of district UUIDs to compare
        metric: Metric name to compare
        years: List of years to include

    Returns:
        List of ComparisonRow sorted by year, then district name.
    """
    if not unit_ids or not years:
        return []

    # Build placeholders for the IN clauses
    unit_placeholders = ", ".join(f"${i + 1}" for i in range(len(unit_ids)))
    year_offset = len(unit_ids) + 1
    year_placeholders = ", ".join(f"${year_offset + i}" for i in range(len(years)))
    metric_param = f"${year_offset + len(years)}"

    query = f"""
        SELECT
            dm.unit_id::text,
            au.name as district_name,
            dm.year,
            dm.value,
            dm.is_harmonized,
            dm.cumulative_confidence as confidence
        FROM district_metrics dm
        JOIN admin_units au ON au.id = dm.unit_id
        WHERE dm.unit_id IN ({unit_placeholders})
          AND dm.year IN ({year_placeholders})
          AND dm.metric = {metric_param}
        ORDER BY dm.year, au.name
    """

    params = list(unit_ids) + list(years) + [metric]
    rows = await conn.fetch(query, *params)

    return [ComparisonRow(**dict(r)) for r in rows]
