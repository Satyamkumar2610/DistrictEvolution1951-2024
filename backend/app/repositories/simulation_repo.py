"""
Simulation repository: query support for simulation and prediction workflows.
"""

from typing import Any

from app.repositories.base import BaseRepository


class SimulationRepository(BaseRepository):
    """Repository for state-level simulation and prediction queries."""

    async def get_state_yield_rows(
        self,
        state: str,
        variable_name: str,
        year: int,
    ) -> list[dict[str, Any]]:
        """Get yield rows for all districts in a state for a given variable/year."""
        rows = await self.fetch_all(
            """
            SELECT d.district_name, m.value as yield
            FROM agri_metrics m
            JOIN districts d ON m.district_lgd = d.lgd_code
            WHERE UPPER(d.state_name) = UPPER($1)
            AND m.variable_name = $2
            AND m.year = $3
            AND m.value IS NOT NULL AND m.value > 0
            """,
            state,
            variable_name,
            year,
        )
        return [dict(row) for row in rows]

    async def get_state_rainfall_rows(
        self,
        state: str,
        include_jjas: bool = False,
    ) -> list[dict[str, Any]]:
        """Get rainfall normals for a state."""
        if include_jjas:
            query = """
                SELECT district, annual, jjas
                FROM rainfall_normals
                WHERE UPPER(state_ut) = UPPER($1)
            """
        else:
            query = """
                SELECT district, annual
                FROM rainfall_normals
                WHERE UPPER(state_ut) = UPPER($1)
            """
        rows = await self.fetch_all(query, state)
        return [dict(row) for row in rows]

    async def get_state_historical_yields(
        self,
        state: str,
        variable_name: str,
    ) -> list[dict[str, Any]]:
        """Get historical yield rows for all districts in a state."""
        rows = await self.fetch_all(
            """
            SELECT d.district_name, m.year, m.value
            FROM agri_metrics m
            JOIN districts d ON m.district_lgd = d.lgd_code
            WHERE UPPER(d.state_name) = UPPER($1)
            AND m.variable_name = $2
            AND m.value IS NOT NULL AND m.value > 0
            ORDER BY d.district_name, m.year
            """,
            state,
            variable_name,
        )
        return [dict(row) for row in rows]

    async def get_state_area_rows(
        self,
        state: str,
        area_variable: str,
        year: int,
    ) -> list[dict[str, Any]]:
        """Get crop area rows for all districts in a state."""
        rows = await self.fetch_all(
            """
            SELECT d.district_name, m.value as area
            FROM agri_metrics m
            JOIN districts d ON m.district_lgd = d.lgd_code
            WHERE UPPER(d.state_name) = UPPER($1)
            AND m.variable_name = $2
            AND m.year = $3
            AND m.value IS NOT NULL AND m.value > 0
            """,
            state,
            area_variable,
            year,
        )
        return [dict(row) for row in rows]
