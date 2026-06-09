"""
Geometry Resolver Core Component
Bridges district shapefiles from SHRUG (2011), Modern (2024 via Bhuvan/GeoJSON) and manual uploads.
Provides high confidence MultiPolygons for spatial diff calculation.

Used by:
  - app.services.split_engine.SplitEngine
  - app.analytics.harmonizer.BoundaryHarmonizer
"""

import json
import logging
from dataclasses import dataclass

import asyncpg

logger = logging.getLogger(__name__)


@dataclass
class ResolvedGeometry:
    """Result of geometry resolution for a single district."""

    district_cdk: str
    snapshot_year: int
    is_known: bool
    geometry_source: str  # shrug_union | bhuvan_wfs | manual_upload | inferred | unknown
    geometry_confidence: float  # 0.0 – 1.0
    area_sqkm: float | None = None


class GeometryResolver:
    """Resolves and loads PostGIS geometries by district ID and year."""

    def __init__(self, db: asyncpg.Connection):
        self.db = db

    async def resolve(self, cdk: str, year: int) -> ResolvedGeometry:
        """
        Resolves the exact spatial boundary for a given district string CDK
        at a specific year from district_snapshots.

        Falls back through:
          1. Direct (cdk, year) match
          2. Fuzzy name-based LGD lookup
          3. Any snapshot for the cdk (ignoring year)
        """
        # 1. Direct fetch from district_snapshots
        row = await self.db.fetchrow(
            """
            SELECT geometry_source::text, geometry_confidence, area_sqkm,
                   (geometry IS NOT NULL) as has_geom
            FROM district_snapshots
            WHERE district_cdk = $1 AND snapshot_year = $2
            LIMIT 1
        """,
            cdk,
            year,
        )

        if row and row["has_geom"]:
            return ResolvedGeometry(
                district_cdk=cdk,
                snapshot_year=year,
                is_known=True,
                geometry_source=row["geometry_source"],
                geometry_confidence=row["geometry_confidence"],
                area_sqkm=row["area_sqkm"],
            )

        # 2. Heuristic fallback: parse string CDK (e.g. WB_barddh_1951)
        # Handle cases like TG_adilab_2011 or WB_24parg_1961
        parts = cdk.split("_")
        name_search = None
        if len(parts) >= 2:
            name_search = parts[1]
        elif len(parts) == 1 and not parts[0].isdigit():
            name_search = parts[0]

        if name_search:
            # Try exact then multiple fuzzy variants
            cdk_str = await self.db.fetchval(
                """
                SELECT cdk::text FROM districts
                WHERE district_name ILIKE $1
                   OR district_name ILIKE $2
                   OR district_name ILIKE $3
                ORDER BY start_year DESC LIMIT 1
            """,
                f"{name_search}%",
                f"%{name_search}%",
                f"%{name_search.replace('kumura', 'asifabad')}%",
            )

            # If still not found and we have a 3rd part (e.g. TG_kumura_asif_2024)
            if not cdk_str and len(parts) >= 3:
                name_search_2 = parts[2]
                cdk_str = await self.db.fetchval(
                    """
                    SELECT cdk::text FROM districts
                    WHERE district_name ILIKE $1 OR district_name ILIKE $2
                    ORDER BY start_year DESC LIMIT 1
                """,
                    f"{name_search_2}%",
                    f"%{name_search_2}%",
                )

            if cdk_str:
                mapped_row = await self.db.fetchrow(
                    """
                    SELECT geometry_source::text, geometry_confidence, area_sqkm,
                           snapshot_year, (geometry IS NOT NULL) as has_geom
                    FROM district_snapshots
                    WHERE district_cdk = $1 AND geometry IS NOT NULL
                    ORDER BY ABS(snapshot_year - $2) ASC
                    LIMIT 1
                """,
                    cdk_str,
                    year,
                )

                if mapped_row and mapped_row["has_geom"]:
                    return ResolvedGeometry(
                        district_cdk=cdk,
                        snapshot_year=mapped_row["snapshot_year"],
                        is_known=True,
                        geometry_source=mapped_row["geometry_source"],
                        geometry_confidence=mapped_row["geometry_confidence"],
                        area_sqkm=mapped_row["area_sqkm"],
                    )

        # 3. Fallback: any snapshot for this cdk, closest year
        row_any = await self.db.fetchrow(
            """
            SELECT geometry_source::text, geometry_confidence, area_sqkm,
                   snapshot_year, (geometry IS NOT NULL) as has_geom
            FROM district_snapshots
            WHERE district_cdk = $1 AND geometry IS NOT NULL
            ORDER BY ABS(snapshot_year - $2) ASC
            LIMIT 1
        """,
            cdk,
            year,
        )
        if row_any and row_any["has_geom"]:
            logger.warning(f"Geometry year fallback used for {cdk} (Requested: {year})")
            return ResolvedGeometry(
                district_cdk=cdk,
                snapshot_year=row_any["snapshot_year"],
                is_known=True,
                geometry_source=row_any["geometry_source"],
                geometry_confidence=row_any["geometry_confidence"],
                area_sqkm=row_any["area_sqkm"],
            )

        # Not found
        return ResolvedGeometry(
            district_cdk=cdk,
            snapshot_year=year,
            is_known=False,
            geometry_source="unknown",
            geometry_confidence=0.0,
        )

    async def infer_from_difference(
        self,
        parent_cdk: str,
        known_sibling_cdks: list[str],
        target_cdk: str,
        year: int,
    ) -> ResolvedGeometry:
        """
        Infer unknown child geometry via ST_Difference(parent, union_of_siblings).
        This is the "inferred" source with confidence 0.6.
        """
        try:
            # Build the union of known siblings
            sibling_placeholders = ", ".join(f"${i + 3}" for i in range(len(known_sibling_cdks)))
            query = f"""
                WITH parent AS (
                    SELECT geometry FROM district_snapshots
                    WHERE district_cdk = $1 AND geometry IS NOT NULL
                    ORDER BY ABS(snapshot_year - $2) LIMIT 1
                ),
                siblings AS (
                    SELECT ST_Union(geometry) as geom FROM district_snapshots
                    WHERE district_cdk IN ({sibling_placeholders}) AND geometry IS NOT NULL
                )
                SELECT
                    ST_Area(ST_Transform(ST_Difference(p.geometry, s.geom), 7755)) / 1000000.0 AS area_sqkm
                FROM parent p, siblings s
                WHERE NOT ST_IsEmpty(ST_Difference(p.geometry, s.geom))
            """
            params = [parent_cdk, year] + known_sibling_cdks
            row = await self.db.fetchrow(query, *params)

            if row and row["area_sqkm"] and row["area_sqkm"] > 0.01:
                # Save the inferred geometry
                save_query = f"""
                    WITH parent AS (
                        SELECT geometry FROM district_snapshots
                        WHERE district_cdk = $1 AND geometry IS NOT NULL
                        ORDER BY ABS(snapshot_year - $2) LIMIT 1
                    ),
                    siblings AS (
                        SELECT ST_Union(geometry) as geom FROM district_snapshots
                        WHERE district_cdk IN ({sibling_placeholders}) AND geometry IS NOT NULL
                    )
                    INSERT INTO district_snapshots
                        (district_cdk, snapshot_year, district_name, geometry_source,
                         geometry_confidence, geometry, area_sqkm)
                    SELECT ${len(params) + 1}, $2, ${len(params) + 1}, 'inferred', 0.6,
                           ST_Difference(p.geometry, s.geom),
                           ST_Area(ST_Transform(ST_Difference(p.geometry, s.geom), 7755)) / 1000000.0
                    FROM parent p, siblings s
                    WHERE NOT ST_IsEmpty(ST_Difference(p.geometry, s.geom))
                    ON CONFLICT (district_cdk, snapshot_year) DO UPDATE SET
                        geometry = EXCLUDED.geometry,
                        geometry_source = 'inferred',
                        geometry_confidence = 0.6,
                        area_sqkm = EXCLUDED.area_sqkm
                """
                save_params = params + [target_cdk]
                await self.db.execute(save_query, *save_params)

                return ResolvedGeometry(
                    district_cdk=target_cdk,
                    snapshot_year=year,
                    is_known=True,
                    geometry_source="inferred",
                    geometry_confidence=0.6,
                    area_sqkm=float(row["area_sqkm"]),
                )
        except Exception as e:
            logger.error(f"Failed to infer geometry for {target_cdk}: {e}")

        return ResolvedGeometry(
            district_cdk=target_cdk,
            snapshot_year=year,
            is_known=False,
            geometry_source="unknown",
            geometry_confidence=0.0,
        )

    @staticmethod
    async def get_geometry(db: asyncpg.Connection, cdk: str, year: int) -> dict | None:
        """
        Static method for backward compatibility with harmonizer.compute_split_diff.
        Returns GeoJSON dictionary if found, else None.
        """
        resolver = GeometryResolver(db)
        resolved = await resolver.resolve(cdk, year)
        if not resolved.is_known:
            return None

        row = await db.fetchrow(
            """
            SELECT ST_AsGeoJSON(geometry) as geomj
            FROM district_snapshots
            WHERE district_cdk = $1 AND geometry IS NOT NULL
            ORDER BY ABS(snapshot_year - $2) ASC
            LIMIT 1
        """,
            cdk,
            year,
        )

        # Also try fuzzy match
        if not row:
            parts = cdk.split("_")
            if len(parts) >= 2:
                name_part = parts[1]
                lgd_str = await db.fetchval(
                    "SELECT cdk::text FROM districts WHERE district_name ILIKE $1 LIMIT 1", f"{name_part}%"
                )
                if lgd_str:
                    row = await db.fetchrow(
                        """
                        SELECT ST_AsGeoJSON(geometry) as geomj
                        FROM district_snapshots
                        WHERE district_cdk = $1 AND geometry IS NOT NULL
                        ORDER BY ABS(snapshot_year - $2) ASC LIMIT 1
                    """,
                        lgd_str,
                        year,
                    )

        if row and row["geomj"]:
            return json.loads(row["geomj"])
        return None
