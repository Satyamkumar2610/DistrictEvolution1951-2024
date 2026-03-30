"""
Base Analytics Service.
Provides database access and common helper methods.
"""
import asyncpg

from app.db_compat import execute_with_schema_fallback


class BaseAnalyticsService:
    """Base generic analytics engine for agricultural data."""

    def __init__(self, db: asyncpg.Connection):
        self.db = db

    async def _fetch(self, query: str, *args):
        return await execute_with_schema_fallback(self.db, "fetch", query, *args)

    async def _fetchrow(self, query: str, *args):
        return await execute_with_schema_fallback(self.db, "fetchrow", query, *args)

    async def _fetchval(self, query: str, *args):
        return await execute_with_schema_fallback(self.db, "fetchval", query, *args)

    async def _fetch_with_fallback(
        self,
        query_template: str,
        crop: str,
        metric: str,
        *args
    ) -> list[asyncpg.Record]:
        """
        Executes a query by substituting the variable_name parameter (always the last arg).
        If the primary crop_metric (e.g. 'wheat_yield') returns no data, it falls back
        to 'wheat_yield_rabi', etc.
        """
        # 1. Try standard aggregated metric
        primary_var = f"{crop}_{metric}"
        all_args = list(args) + [primary_var]
        rows = await self._fetch(query_template, *all_args)

        # 2. Try seasonal fallback if no data
        if not rows or len(rows) == 0:
            season_map = {
                "rice": "kharif",
                "wheat": "rabi",
                "maize": "kharif",
                "soyabean": "kharif",
                "groundnut": "kharif",
                "cotton": "kharif",
                "pearl_millet": "kharif",
                "sorghum": "kharif",
                "chickpea": "rabi"
            }
            season = season_map.get(crop.lower())
            if season:
                fallback_var = f"{crop}_{metric}_{season}"
                all_args[-1] = fallback_var
                rows = await self._fetch(query_template, *all_args)

        return rows  # type: ignore[return-value]
