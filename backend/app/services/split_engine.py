"""
Split Engine — computes geometric diff between parent and child districts.

All heavy operations are done via PostGIS (ST_Intersection, ST_Difference,
ST_SymDifference). Hausdorff is used ONLY inside the confidence score formula.
"""

import logging
from dataclasses import dataclass, field

import asyncpg

from app.core.geometry_resolver import GeometryResolver, ResolvedGeometry

logger = logging.getLogger("app.services.split_engine")


@dataclass
class TransferResult:
    """A single classified sub-region from the diff."""

    from_district: str
    to_district: str
    transfer_type: str  # inherited | transferred_in | transferred_out | overlap | gap
    area_sqkm: float
    geojson: dict  # GeoJSON geometry
    confidence_score: float


@dataclass
class SplitDiffResult:
    """Complete result of a split diff computation."""

    parent_cdk: str
    child_cdks: list[str]
    split_year: int
    parent_area_sqkm: float
    total_child_area_sqkm: float
    area_conservation_error: float  # |parent - sum(children)| / parent
    composite_confidence: float
    geometry_status: str  # complete | partial | unknown
    transfers: list[TransferResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # GeoJSON FeatureCollection of all results
    geojson_fc: dict | None = None


class SplitEngine:
    """
    Computes spatial diff between a parent district and its child districts.
    Uses PostGIS via asyncpg for all geometric operations.
    """

    def __init__(self, db: asyncpg.Connection):
        self.db = db
        self.resolver = GeometryResolver(db)

    async def compute_split_diff(
        self,
        parent_cdk: str,
        child_cdks: list[str],
        split_year: int,
    ) -> SplitDiffResult:
        """
        Main entry point. Computes the full split diff.

        Raises HTTPException(422) if parent geometry is unknown.
        """
        warnings: list[str] = []

        # ── 1. Resolve geometries ──────────────────────────────────────────
        parent_geom = await self.resolver.resolve(parent_cdk, split_year)

        if not parent_geom.is_known:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=422,
                detail={
                    "error": "GEOMETRY_UNKNOWN",
                    "message": (
                        f"Parent district '{parent_cdk}' has no known geometry. "
                        f"Please upload a GeoJSON boundary via POST /api/v1/spatial/upload-geojson"
                    ),
                    "district_cdk": parent_cdk,
                    "geometry_source": "unknown",
                    "geometry_confidence": 0.0,
                },
            )

        # Resolve children
        child_geoms: list[ResolvedGeometry] = []
        unknown_children: list[str] = []
        known_children: list[str] = []

        for child_cdk in child_cdks:
            cg = await self.resolver.resolve(child_cdk, split_year)
            if cg.is_known:
                child_geoms.append(cg)
                known_children.append(child_cdk)
            else:
                unknown_children.append(child_cdk)

        # Try to infer unknown children from known parent + siblings
        for unk_cdk in unknown_children:
            if known_children:
                inferred = await self.resolver.infer_from_difference(
                    parent_cdk=parent_cdk,
                    known_sibling_cdks=known_children,
                    target_cdk=unk_cdk,
                    year=split_year,
                )
                if inferred.is_known:
                    child_geoms.append(inferred)
                    known_children.append(unk_cdk)
                    warnings.append(f"Geometry for '{unk_cdk}' was inferred via ST_Difference (confidence=0.6)")
                else:
                    warnings.append(f"Could not resolve geometry for child '{unk_cdk}'")
            else:
                warnings.append(
                    f"Could not resolve geometry for child '{unk_cdk}' — no siblings available for inference"
                )

        # Determine geometry status
        if len(child_geoms) == len(child_cdks):
            geometry_status = "complete"
        elif len(child_geoms) > 0:
            geometry_status = "partial"
        else:
            geometry_status = "unknown"

        if not child_geoms:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=422,
                detail={
                    "error": "GEOMETRY_UNKNOWN",
                    "message": (
                        "No child district geometries could be resolved. "
                        "Upload boundaries via POST /api/v1/spatial/upload-geojson"
                    ),
                    "unknown_children": unknown_children,
                },
            )

        # ── 2. Run PostGIS diff operations ────────────────────────────────
        transfers: list[TransferResult] = []
        child_areas: list[float] = []

        for cg in child_geoms:
            child_cdk = cg.district_cdk

            # 2a. Inherited area = ST_Intersection(parent, child)
            inherited = await self.db.fetchrow(
                """
                WITH p AS (
                    SELECT geometry FROM district_snapshots
                    WHERE district_cdk = $1 AND geometry IS NOT NULL
                    ORDER BY ABS(snapshot_year - $3) LIMIT 1
                ),
                c AS (
                    SELECT geometry FROM district_snapshots
                    WHERE district_cdk = $2 AND geometry IS NOT NULL
                    ORDER BY ABS(snapshot_year - $3) LIMIT 1
                )
                SELECT
                    ST_AsGeoJSON(ST_Intersection(p.geometry, c.geometry))::json AS geojson,
                    ST_Area(ST_Transform(
                        ST_Intersection(p.geometry, c.geometry), 7755
                    )) / 1000000.0 AS area_sqkm
                FROM p, c
                WHERE ST_Intersects(p.geometry, c.geometry)
            """,
                parent_cdk,
                child_cdk,
                split_year,
            )

            if inherited and inherited["area_sqkm"] and inherited["area_sqkm"] > 0.01:
                transfers.append(
                    TransferResult(
                        from_district=parent_cdk,
                        to_district=child_cdk,
                        transfer_type="inherited",
                        area_sqkm=float(inherited["area_sqkm"]),
                        geojson=inherited["geojson"],
                        confidence_score=min(parent_geom.geometry_confidence, cg.geometry_confidence),
                    )
                )

            # 2b. Externally acquired = ST_Difference(child, parent)
            acquired = await self.db.fetchrow(
                """
                WITH p AS (
                    SELECT geometry FROM district_snapshots
                    WHERE district_cdk = $1 AND geometry IS NOT NULL
                    ORDER BY ABS(snapshot_year - $3) LIMIT 1
                ),
                c AS (
                    SELECT geometry FROM district_snapshots
                    WHERE district_cdk = $2 AND geometry IS NOT NULL
                    ORDER BY ABS(snapshot_year - $3) LIMIT 1
                )
                SELECT
                    ST_AsGeoJSON(ST_Difference(c.geometry, p.geometry))::json AS geojson,
                    ST_Area(ST_Transform(
                        ST_Difference(c.geometry, p.geometry), 7755
                    )) / 1000000.0 AS area_sqkm
                FROM p, c
            """,
                parent_cdk,
                child_cdk,
                split_year,
            )

            if acquired and acquired["area_sqkm"] and acquired["area_sqkm"] > 0.01:
                transfers.append(
                    TransferResult(
                        from_district="neighbor",
                        to_district=child_cdk,
                        transfer_type="transferred_in",
                        area_sqkm=float(acquired["area_sqkm"]),
                        geojson=acquired["geojson"],
                        confidence_score=min(parent_geom.geometry_confidence, cg.geometry_confidence),
                    )
                )

            child_areas.append(cg.area_sqkm or 0.0)

        # 2c. Gap / transferred_out = ST_Difference(parent, ST_Union(all children))
        resolved_child_cdks = [cg.district_cdk for cg in child_geoms]
        gap = await self.db.fetchrow(
            """
            WITH p AS (
                SELECT geometry FROM district_snapshots
                WHERE district_cdk = $1 AND geometry IS NOT NULL
                ORDER BY ABS(snapshot_year - $3) LIMIT 1
            ),
            children AS (
                SELECT ST_Union(geometry) AS geom
                FROM district_snapshots
                WHERE district_cdk = ANY($2) AND geometry IS NOT NULL
            )
            SELECT
                ST_AsGeoJSON(ST_Difference(p.geometry, children.geom))::json AS geojson,
                ST_Area(ST_Transform(
                    ST_Difference(p.geometry, children.geom), 7755
                )) / 1000000.0 AS area_sqkm
            FROM p, children
        """,
            parent_cdk,
            resolved_child_cdks,
            split_year,
        )

        if gap and gap["area_sqkm"] and gap["area_sqkm"] > 0.01:
            transfers.append(
                TransferResult(
                    from_district=parent_cdk,
                    to_district="unallocated",
                    transfer_type="gap",
                    area_sqkm=float(gap["area_sqkm"]),
                    geojson=gap["geojson"],
                    confidence_score=parent_geom.geometry_confidence * 0.5,
                )
            )

        # 2d. Overlap between children = pairwise ST_Intersection
        for i in range(len(child_geoms)):
            for j in range(i + 1, len(child_geoms)):
                ci_cdk = child_geoms[i].district_cdk
                cj_cdk = child_geoms[j].district_cdk
                overlap = await self.db.fetchrow(
                    """
                    WITH ci AS (
                        SELECT geometry FROM district_snapshots
                        WHERE district_cdk = $1 AND geometry IS NOT NULL
                        ORDER BY snapshot_year DESC LIMIT 1
                    ),
                    cj AS (
                        SELECT geometry FROM district_snapshots
                        WHERE district_cdk = $2 AND geometry IS NOT NULL
                        ORDER BY snapshot_year DESC LIMIT 1
                    )
                    SELECT
                        ST_AsGeoJSON(ST_Intersection(ci.geometry, cj.geometry))::json AS geojson,
                        ST_Area(ST_Transform(
                            ST_Intersection(ci.geometry, cj.geometry), 7755
                        )) / 1000000.0 AS area_sqkm
                    FROM ci, cj
                    WHERE ST_Intersects(ci.geometry, cj.geometry)
                """,
                    ci_cdk,
                    cj_cdk,
                )

                if overlap and overlap["area_sqkm"] and overlap["area_sqkm"] > 0.01:
                    transfers.append(
                        TransferResult(
                            from_district=ci_cdk,
                            to_district=cj_cdk,
                            transfer_type="overlap",
                            area_sqkm=float(overlap["area_sqkm"]),
                            geojson=overlap["geojson"],
                            confidence_score=0.3,  # Overlap = low confidence
                        )
                    )
                    warnings.append(f"Overlap detected between {ci_cdk} and {cj_cdk}: {overlap['area_sqkm']:.2f} sq km")

        # ── 3. Compute metrics ────────────────────────────────────────────
        parent_area = parent_geom.area_sqkm or 0.0
        total_child_area = sum(child_areas)
        area_conservation_error = abs(parent_area - total_child_area) / parent_area if parent_area > 0 else 0.0

        # Overlap and gap percentages
        overlap_area = sum(t.area_sqkm for t in transfers if t.transfer_type == "overlap")
        gap_area = sum(t.area_sqkm for t in transfers if t.transfer_type == "gap")
        overlap_pct = overlap_area / parent_area if parent_area > 0 else 0.0
        gap_pct = gap_area / parent_area if parent_area > 0 else 0.0

        # Composite confidence formula
        avg_source_confidence = (
            sum(cg.geometry_confidence for cg in child_geoms) + parent_geom.geometry_confidence
        ) / (len(child_geoms) + 1)

        composite_confidence = (
            avg_source_confidence * 0.4
            + max(0, 1 - area_conservation_error) * 0.3
            + max(0, 1 - overlap_pct) * 0.15
            + max(0, 1 - gap_pct) * 0.15
        )

        if area_conservation_error > 0.05:
            warnings.append(
                f"Area conservation error is {area_conservation_error:.1%} — "
                f"parent={parent_area:.1f} sq km vs children total={total_child_area:.1f} sq km"
            )

        # ── 4. Build GeoJSON FeatureCollection ────────────────────────────
        features = []
        for t in transfers:
            features.append(
                {
                    "type": "Feature",
                    "geometry": t.geojson,
                    "properties": {
                        "from_district": t.from_district,
                        "to_district": t.to_district,
                        "transfer_type": t.transfer_type,
                        "area_sqkm": round(t.area_sqkm, 4),
                        "confidence_score": round(t.confidence_score, 3),
                    },
                }
            )

        geojson_fc = {
            "type": "FeatureCollection",
            "features": features,
        }

        # ── 5. Persist to split_events + area_transfers ───────────────────
        event_id = await self._persist_event(
            parent_cdk=parent_cdk,
            child_cdks=child_cdks,
            split_year=split_year,
            geometry_status=geometry_status,
            parent_area=parent_area,
            total_child_area=total_child_area,
            area_conservation_error=area_conservation_error,
            composite_confidence=composite_confidence,
        )

        for t in transfers:
            await self._persist_transfer(event_id, t)

        return SplitDiffResult(
            parent_cdk=parent_cdk,
            child_cdks=child_cdks,
            split_year=split_year,
            parent_area_sqkm=parent_area,
            total_child_area_sqkm=total_child_area,
            area_conservation_error=area_conservation_error,
            composite_confidence=composite_confidence,
            geometry_status=geometry_status,
            transfers=transfers,
            warnings=warnings,
            geojson_fc=geojson_fc,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Persistence helpers
    # ─────────────────────────────────────────────────────────────────────

    async def _persist_event(
        self,
        parent_cdk: str,
        child_cdks: list[str],
        split_year: int,
        geometry_status: str,
        parent_area: float,
        total_child_area: float,
        area_conservation_error: float,
        composite_confidence: float,
    ) -> int:
        """Insert or update split_events, return event_id."""
        event_id = await self.db.fetchval(
            """
            INSERT INTO split_events
                (parent_cdk, child_cdks, split_year, event_type,
                 geometry_status, parent_area_sqkm, total_child_area_sqkm,
                 area_conservation_error, composite_confidence)
            VALUES ($1, $2, $3, 'split', $4::geometry_status_type,
                    $5, $6, $7, $8)
            ON CONFLICT (parent_cdk, split_year) DO UPDATE SET
                child_cdks = EXCLUDED.child_cdks,
                geometry_status = EXCLUDED.geometry_status,
                parent_area_sqkm = EXCLUDED.parent_area_sqkm,
                total_child_area_sqkm = EXCLUDED.total_child_area_sqkm,
                area_conservation_error = EXCLUDED.area_conservation_error,
                composite_confidence = EXCLUDED.composite_confidence
            RETURNING id
        """,
            parent_cdk,
            child_cdks,
            split_year,
            geometry_status,
            parent_area,
            total_child_area,
            area_conservation_error,
            composite_confidence,
        )
        return event_id

    async def _persist_transfer(self, event_id: int, transfer: TransferResult) -> None:
        """Insert an area_transfers row."""
        import json

        geojson_str = json.dumps(transfer.geojson)
        await self.db.execute(
            """
            INSERT INTO area_transfers
                (event_id, from_district, to_district, geometry,
                 area_sqkm, transfer_type, confidence_score)
            VALUES (
                $1, $2, $3,
                ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON($4), 4326)),
                $5, $6::transfer_type, $7
            )
        """,
            event_id,
            transfer.from_district,
            transfer.to_district,
            geojson_str,
            transfer.area_sqkm,
            transfer.transfer_type,
            transfer.confidence_score,
        )
