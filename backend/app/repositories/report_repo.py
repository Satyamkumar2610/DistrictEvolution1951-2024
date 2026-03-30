"""
Report repository: query support for report generation workflows.
"""

from app.repositories.base import BaseRepository


class ReportRepository(BaseRepository):
    """Repository for district profile report queries."""

    async def get_district_context(self, cdk: str) -> dict[str, str] | None:
        """Get district name and state by LGD code."""
        row = await self.fetch_one(
            """
            SELECT lgd_code::text as cdk, district_name, state_name
            FROM districts
            WHERE lgd_code::text = $1
            """,
            cdk,
        )
        return dict(row) if row else None

    async def get_crop_metric_history(self, cdk: str, crop: str) -> list[dict[str, object]]:
        """Get yield, area, and production history for a district crop."""
        yield_var = f"{crop}_yield"
        area_var = f"{crop}_area"
        prod_var = f"{crop}_production"
        rows = await self.fetch_all(
            """
            SELECT year, variable_name, value
            FROM agri_metrics
            WHERE district_lgd::text = $1
            AND variable_name IN ($2, $3, $4)
            AND value > 0
            ORDER BY year
            """,
            cdk,
            yield_var,
            area_var,
            prod_var,
        )
        return [dict(row) for row in rows]

    async def get_state_average_yield(self, state_name: str, crop: str) -> float | None:
        """Get state-wide average yield for the crop."""
        value = await self.conn.fetchval(
            """
            SELECT ROUND(AVG(m.value)::numeric, 2)
            FROM agri_metrics m
            JOIN districts d ON m.district_lgd = d.lgd_code
            WHERE d.state_name = $1 AND m.variable_name = $2 AND m.value > 0
            """,
            state_name,
            f"{crop}_yield",
        )
        return float(value) if value is not None else None
