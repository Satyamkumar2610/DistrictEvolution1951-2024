"""
Spatial repository: query support for spatial analytics and lineage workflows.
"""

from typing import Any

from app.repositories.base import BaseRepository


class SpatialRepository(BaseRepository):
    """Repository for spatial and lineage-related queries."""

    async def district_exists(self, cdk: str) -> bool:
        """Check whether a district exists by LGD code."""
        exists = await self.conn.fetchval(
            "SELECT lgd_code FROM districts WHERE lgd_code::text = $1",
            cdk,
        )
        return bool(exists)

    async def get_target_meta(self, cdk: str) -> dict[str, Any] | None:
        """Get district metadata for a target district."""
        row = await self.fetch_one(
            """
            SELECT district_name, state_name
            FROM districts
            WHERE lgd_code::text = $1
            """,
            cdk,
        )
        return dict(row) if row else None

    async def get_neighbors(self, cdk: str) -> list[dict[str, Any]]:
        """Find spatially adjacent neighboring districts using PostGIS."""
        try:
            lgd_val = float(cdk)
        except ValueError:
            return []

        rows = await self.fetch_all(
            """
            WITH target AS (
                SELECT geometry, lgd_code, "DISTRICT" as district_name, "ST_NM" as state_name
                FROM districts_geo
                WHERE lgd_code = $1
            )
            SELECT
                n.lgd_code as neighbor_cdk,
                n."DISTRICT" as neighbor_name,
                n."ST_NM" as neighbor_state
            FROM districts_geo n
            JOIN target t ON ST_Touches(t.geometry, n.geometry)
            WHERE n.lgd_code != $1
            ORDER BY n."DISTRICT"
            """,
            lgd_val,
        )
        return [dict(row) for row in rows]

    async def get_crop_yield_series(
        self,
        cdk: str,
        crop: str,
        start_year: int,
        end_year: int,
    ) -> list[dict[str, Any]]:
        """Get yield series for CAGR calculation."""
        rows = await self.fetch_all(
            """
            SELECT year, value
            FROM agri_metrics
            WHERE district_lgd::text = $1
              AND variable_name = $2
              AND year BETWEEN $3 AND $4
              AND value > 0
            ORDER BY year
            """,
            cdk,
            f"{crop}_yield",
            start_year,
            end_year,
        )
        return [dict(row) for row in rows]

    async def get_split_events_for_district(self, district_id: str) -> list[dict[str, Any]]:
        """Get split events associated with a district."""
        rows = await self.fetch_all(
            "SELECT * FROM split_events WHERE parent_cdk = $1 OR $1 = ANY(child_cdks)",
            district_id,
        )
        return [dict(row) for row in rows]

    async def get_area_transfers_for_district(self, district_id: str) -> list[dict[str, Any]]:
        """Get area transfer records associated with a district."""
        rows = await self.fetch_all(
            "SELECT * FROM area_transfers WHERE source_cdk = $1 OR dest_cdk = $1",
            district_id,
        )
        return [
            {key: value for key, value in dict(row).items() if key != "geometry"}
            for row in rows
        ]

    async def get_district_name(self, district_id: str) -> str | None:
        """Get district name for a district LGD code."""
        name = await self.conn.fetchval(
            "SELECT district_name FROM districts WHERE lgd_code::text = $1 LIMIT 1",
            district_id,
        )
        return str(name) if name else None

    async def upsert_manual_geojson(
        self,
        district_id: str,
        snapshot_year: int,
        district_name: str,
        geometry_geojson: str,
    ) -> None:
        """Insert or update a manual GeoJSON snapshot for a district/year."""
        await self.execute(
            """
            INSERT INTO district_snapshots
                (district_cdk, snapshot_year, district_name, geometry_source, geometry_confidence, geometry)
            VALUES
                ($1, $2, $3, 'manual_upload', 0.8, ST_SetSRID(ST_GeomFromGeoJSON($4), 4326))
            ON CONFLICT (district_cdk, snapshot_year) DO UPDATE SET
                geometry = EXCLUDED.geometry,
                geometry_source = EXCLUDED.geometry_source,
                geometry_confidence = EXCLUDED.geometry_confidence
            """,
            district_id,
            snapshot_year,
            district_name,
            geometry_geojson,
        )
