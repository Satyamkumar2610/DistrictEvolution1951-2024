"""
State Repository: Data access for state-level overview and listing flows.
"""

from app.repositories.base import BaseRepository


class StateRepository(BaseRepository):
    """Repository for state-level aggregate queries."""

    async def state_exists(self, state_name: str) -> bool:
        """Return whether the state exists in the districts table."""
        count = await self.fetch_val(
            "SELECT COUNT(*) FROM districts WHERE state_name = $1",
            state_name,
        )
        return bool(count)

    async def get_total_districts(self, state_name: str) -> int:
        """Return total districts for a state."""
        count = await self.fetch_val(
            "SELECT COUNT(*) FROM districts WHERE state_name = $1",
            state_name,
        )
        return int(count or 0)

    async def get_year_range(self, state_name: str) -> dict[str, int | None]:
        """Return the min and max metric year for a state."""
        row = await self.fetch_one(
            """
            SELECT MIN(m.year) as min_year, MAX(m.year) as max_year
            FROM agri_metrics m
            JOIN districts d ON m.cdk = d.cdk
            WHERE d.state_name = $1
            """,
            state_name,
        )
        return {
            "min_year": row["min_year"] if row else None,
            "max_year": row["max_year"] if row else None,
        }

    async def get_avg_yield(self, state_name: str, yield_var: str, year: int) -> float | None:
        """Return average yield for a state/crop/year."""
        value = await self.fetch_val(
            """
            SELECT ROUND(AVG(m.value)::numeric, 2)
            FROM agri_metrics m
            JOIN districts d ON m.cdk = d.cdk
            WHERE d.state_name = $1 AND m.variable_name = $2 AND m.year = $3 AND m.value > 0
            """,
            state_name,
            yield_var,
            year,
        )
        return float(value) if value is not None else None

    async def get_performers(
        self,
        state_name: str,
        yield_var: str,
        year: int,
        *,
        descending: bool,
    ) -> list[dict[str, float | str]]:
        """Return top or bottom performers for a state/crop/year."""
        ordering = "DESC" if descending else "ASC"
        rows = await self.fetch_all(
            f"""
            SELECT d.district_name, d.cdk::text as cdk, ROUND(m.value::numeric, 2) as yield_value
            FROM agri_metrics m
            JOIN districts d ON m.cdk = d.cdk
            WHERE d.state_name = $1 AND m.variable_name = $2 AND m.year = $3 AND m.value > 0
            ORDER BY m.value {ordering}
            LIMIT 5
            """,
            state_name,
            yield_var,
            year,
        )
        return [dict(row) for row in rows]

    async def get_metric_totals(
        self,
        state_name: str,
        area_var: str,
        production_var: str,
        year: int,
    ) -> dict[str, float | None]:
        """Return aggregate area and production totals for a state/crop/year."""
        row = await self.fetch_one(
            """
            SELECT
                ROUND(SUM(CASE WHEN m.variable_name = $2 THEN m.value END)::numeric, 2) as total_area,
                ROUND(SUM(CASE WHEN m.variable_name = $3 THEN m.value END)::numeric, 2) as total_production
            FROM agri_metrics m
            JOIN districts d ON m.cdk = d.cdk
            WHERE d.state_name = $1 AND m.year = $4 AND m.value > 0
            """,
            state_name,
            area_var,
            production_var,
            year,
        )
        return {
            "total_area": float(row["total_area"]) if row and row["total_area"] is not None else None,
            "total_production": float(row["total_production"]) if row and row["total_production"] is not None else None,
        }

    async def count_districts_with_data(self, state_name: str, yield_var: str, year: int) -> int:
        """Return number of districts with non-zero yield data for the state/crop/year."""
        count = await self.fetch_val(
            """
            SELECT COUNT(DISTINCT d.cdk)
            FROM agri_metrics m
            JOIN districts d ON m.cdk = d.cdk
            WHERE d.state_name = $1 AND m.variable_name = $2 AND m.year = $3 AND m.value > 0
            """,
            state_name,
            yield_var,
            year,
        )
        return int(count or 0)

    async def get_available_crops(self, state_name: str) -> list[str]:
        """Return crops with yield data available for the state."""
        rows = await self.fetch_all(
            """
            SELECT DISTINCT REPLACE(m.variable_name, '_yield', '') as crop_name
            FROM agri_metrics m
            JOIN districts d ON m.cdk = d.cdk
            WHERE d.state_name = $1 AND m.variable_name LIKE '%_yield' AND m.value > 0
            ORDER BY crop_name
            """,
            state_name,
        )
        return [row["crop_name"] for row in rows]

    async def list_state_counts(self) -> list[dict[str, int | str]]:
        """Return all states with district counts."""
        rows = await self.fetch_all(
            """
            SELECT state_name, COUNT(*) as district_count
            FROM districts
            GROUP BY state_name
            ORDER BY state_name
            """
        )
        return [{"state": row["state_name"], "district_count": row["district_count"]} for row in rows]
