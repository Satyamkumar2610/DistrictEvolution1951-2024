"""
Anomaly repository: query support for anomaly scanning workflows.
"""

from app.repositories.base import BaseRepository


class AnomalyRepository(BaseRepository):
    """Repository for anomaly-related district lookups and sampling."""

    async def district_exists(self, cdk: str) -> bool:
        """Check whether a district exists by LGD code."""
        exists = await self.fetch_val(
            "SELECT 1 FROM districts WHERE lgd_code::text = $1",
            cdk,
        )
        return bool(exists)

    async def get_active_district_sample(self, limit: int) -> list[dict[str, str]]:
        """Get a random sample of active districts for cross-state risk scanning."""
        query = """
            SELECT lgd_code::text as cdk, state_name, district_name
            FROM districts
            ORDER BY RANDOM()
            LIMIT $1
        """
        rows = await self.fetch_all(query, limit)
        return [
            {
                "cdk": str(row["cdk"]),
                "state_name": str(row["state_name"]),
                "district_name": str(row["district_name"]),
            }
            for row in rows
        ]
