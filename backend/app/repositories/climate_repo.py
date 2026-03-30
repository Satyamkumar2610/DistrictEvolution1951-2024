"""
Climate Repository: Data access for climate-related analytical queries.
"""

from app.repositories.base import BaseRepository


class ClimateRepository(BaseRepository):
    """Repository for climate and rainfall correlation query support."""

    async def get_state_yield_rows(
        self,
        state: str,
        variable: str,
        year: int,
    ) -> list[dict[str, str | float]]:
        """Return district yield rows for a state, crop variable, and year."""
        rows = await self.fetch_all(
            """
            SELECT d.district_name, m.value as yield_val
            FROM agri_metrics m
            JOIN districts d ON m.district_lgd = d.lgd_code
            WHERE UPPER(d.state_name) = UPPER($1)
              AND m.variable_name = $2
              AND m.year = $3
              AND m.value IS NOT NULL
              AND m.value > 0
            """,
            state,
            variable,
            year,
        )

        return [
            {
                "district_name": str(row["district_name"]),
                "yield_val": float(row["yield_val"]),
            }
            for row in rows
        ]
