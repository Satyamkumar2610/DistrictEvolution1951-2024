"""
Split Repository: Data access for district split summary and resolution flows.
"""

from app.repositories.base import BaseRepository


class SplitRepository(BaseRepository):
    """Repository for district_splits and related split-impact queries."""

    async def get_state_district_counts(self) -> list[dict[str, int | str]]:
        """Return total district counts grouped by state."""
        rows = await self.fetch_all(
            """
            SELECT state_name, COUNT(*) as total_districts
            FROM districts
            GROUP BY state_name
            ORDER BY state_name
            """
        )
        return [
            {
                "state_name": row["state_name"],
                "total_districts": row["total_districts"],
            }
            for row in rows
        ]

    async def get_boundary_change_counts(self) -> dict[str, int]:
        """Return distinct split-event counts per state."""
        rows = await self.fetch_all(
            """
            SELECT state_name, COUNT(DISTINCT parent_district || '_' || split_year::text) as boundary_changes
            FROM district_splits
            GROUP BY state_name
            """
        )
        return {
            row["state_name"].strip().upper(): row["boundary_changes"]
            for row in rows
        }

    async def get_split_rows_for_state(self, state: str) -> list[dict[str, int | str | None]]:
        """Return split-event rows for a state using pre-resolved LGD columns when available."""
        rows = await self.fetch_all(
            """
            SELECT
                ds.parent_district,
                ds.child_district,
                ds.split_year,
                ds.state_name,
                ds.parent_lgd,
                ds.child_lgd
            FROM district_splits ds
            WHERE UPPER(ds.state_name) = UPPER($1)
            ORDER BY ds.split_year, ds.parent_district
            """,
            state,
        )
        return [dict(row) for row in rows]

    async def get_agri_lgds(self, lgds: list[int]) -> set[int]:
        """Return the subset of LGDs that have agricultural metrics."""
        if not lgds:
            return set()

        rows = await self.fetch_all(
            """
            SELECT DISTINCT district_lgd
            FROM agri_metrics
            WHERE district_lgd = ANY($1::int[])
            """,
            lgds,
        )
        return {row["district_lgd"] for row in rows}
