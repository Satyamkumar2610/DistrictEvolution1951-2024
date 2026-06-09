"""
Forecast repository: query support for forecasting and crop recommendations.
"""

import asyncpg

from app.repositories.base import BaseRepository


class ForecastRepository(BaseRepository):
    """Repository for forecast-related district and metric queries."""

    async def get_district_context(self, cdk: str) -> asyncpg.Record | None:
        """Get district name and state for a district LGD code."""
        query = """
            SELECT cdk::text as cdk, state_name, district_name
            FROM districts
            WHERE cdk::text = $1
        """
        return await self.fetch_one(query, cdk)

    async def get_latest_crop_snapshot(
        self,
        cdk: str,
        crop: str,
    ) -> asyncpg.Record | None:
        """Get the latest available yield and area snapshot for a crop."""
        query = """
            SELECT
                MAX(CASE WHEN variable_name = $2 THEN value END) as yield,
                MAX(CASE WHEN variable_name = $3 THEN value END) as area
            FROM agri_metrics
            WHERE cdk::text = $1
            AND year = (
                SELECT MAX(year)
                FROM agri_metrics
                WHERE cdk::text = $1
                AND variable_name = $2
                AND value > 0
            )
        """
        return await self.fetch_one(query, cdk, f"{crop}_yield", f"{crop}_area")

    async def get_state_average_yield(self, state: str, crop: str) -> float | None:
        """Get recent state-average yield benchmark for a crop."""
        query = """
            SELECT AVG(value)
            FROM agri_metrics m
            JOIN districts d ON m.cdk = d.cdk
            WHERE d.state_name = $1
            AND m.variable_name = $2
            AND m.value > 0
            AND m.year >= (SELECT MAX(year) - 5 FROM agri_metrics)
        """
        avg = await self.fetch_val(query, state, f"{crop}_yield")
        return float(avg) if avg is not None else None

    async def get_historical_yields(self, cdk: str, crop: str) -> dict[int, float]:
        """Get historical yield series for a district and crop."""
        query = """
            SELECT year, value
            FROM agri_metrics
            WHERE cdk::text = $1 AND variable_name = $2 AND value > 0
            ORDER BY year
        """
        rows = await self.fetch_all(query, cdk, f"{crop}_yield")
        return {int(row["year"]): float(row["value"]) for row in rows}

    async def get_recent_variable_history(
        self,
        cdk: str,
        variable: str,
        limit: int = 6,
    ) -> list[asyncpg.Record]:
        """Get the most recent non-zero observations for a variable."""
        query = """
            SELECT year, value
            FROM agri_metrics
            WHERE cdk::text = $1 AND variable_name = $2 AND value > 0
            ORDER BY year DESC
            LIMIT $3
        """
        return await self.fetch_all(query, cdk, variable, limit)
