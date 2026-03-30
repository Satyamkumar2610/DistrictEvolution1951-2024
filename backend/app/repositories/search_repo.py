"""
Search repository: query support for cross-entity search.
"""

from app.repositories.base import BaseRepository


class SearchRepository(BaseRepository):
    """Repository for district and state search queries."""

    async def search_districts(self, query: str, limit: int) -> list[dict[str, object]]:
        """Search districts by name or LGD code."""
        search_pattern = f"%{query}%"
        rows = await self.fetch_all(
            """
            SELECT
                lgd_code::text as cdk,
                district_name as name,
                state_name as state,
                NULL::int as start_year,
                NULL::int as end_year,
                'district' as result_type,
                CASE WHEN district_name ILIKE $2 THEN 0 ELSE 1 END as sort_order
            FROM districts
            WHERE district_name ILIKE $1 OR lgd_code::text ILIKE $1
            ORDER BY sort_order, district_name
            LIMIT $3
            """,
            search_pattern,
            f"{query}%",
            limit,
        )

        return [
            {key: value for key, value in dict(row).items() if key != "sort_order"}
            for row in rows
        ]

    async def search_states(self, query: str, limit: int) -> list[dict[str, object]]:
        """Search states by name."""
        search_pattern = f"%{query}%"
        rows = await self.fetch_all(
            """
            SELECT
                state_name as name,
                state_name as state,
                COUNT(*) as district_count,
                'state' as result_type
            FROM districts
            WHERE state_name ILIKE $1
            GROUP BY state_name
            ORDER BY
                CASE WHEN state_name ILIKE $2 THEN 0 ELSE 1 END,
                state_name
            LIMIT $3
            """,
            search_pattern,
            f"{query}%",
            limit,
        )
        return [dict(row) for row in rows]
