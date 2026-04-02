"""
Boundary Drift Detector — measures how district boundaries change over time.

Uses PostGIS functions:
  - ST_HausdorffDistance   : maximum of minimum distances (boundary shape change)
  - ST_Area + ST_Intersection : area overlap ratio (Jaccard-like)
  - ST_Centroid            : centroid shift in km

Compares snapshots of the same district across different years.
"""

import logging
from dataclasses import dataclass

import asyncpg

logger = logging.getLogger("app.services.drift_detector")


@dataclass
class DriftResult:
    """Boundary drift metrics between two snapshots of the same district."""

    district_cdk: str
    year_a: int
    year_b: int
    hausdorff_km: float  # Hausdorff distance in km
    area_a_sqkm: float
    area_b_sqkm: float
    area_change_pct: float  # (B - A) / A × 100
    overlap_area_sqkm: float  # ST_Intersection area
    jaccard_index: float  # intersection / union
    centroid_shift_km: float  # distance between centroids
    shape_similarity: float  # 0–1 composite score
    source_a: str
    source_b: str


class DriftDetector:
    """
    Detects boundary drift for a district between its geometry snapshots.
    All computations in PostGIS via EPSG:7755 (India).
    """

    def __init__(self, db: asyncpg.Connection):
        self.db = db

    async def detect_drift(
        self,
        district_cdk: str,
        year_a: int | None = None,
        year_b: int | None = None,
    ) -> DriftResult | None:
        """
        Compare two snapshots of the same district.

        If year_a/year_b not specified, uses the two most recent snapshots.
        """
        # Get available snapshots
        snapshots = await self.db.fetch(
            """
            SELECT snapshot_year, geometry_source::text,
                   ST_Area(ST_Transform(geometry, 7755)) / 1000000.0 AS area_sqkm
            FROM district_snapshots
            WHERE district_cdk = $1 AND geometry IS NOT NULL
            ORDER BY snapshot_year ASC
        """,
            district_cdk,
        )

        if len(snapshots) < 2:
            logger.info(f"Need 2+ snapshots for drift detection, {district_cdk} has {len(snapshots)}")
            return None

        # Pick comparison years
        if year_a is None:
            year_a = snapshots[0]["snapshot_year"]
        if year_b is None:
            year_b = snapshots[-1]["snapshot_year"]

        if year_a == year_b:
            return None

        # Ensure year_a < year_b
        if year_a > year_b:
            year_a, year_b = year_b, year_a

        # Run all metrics in a single PostGIS query
        result = await self.db.fetchrow(
            """
            WITH a AS (
                SELECT geometry, geometry_source::text AS source
                FROM district_snapshots
                WHERE district_cdk = $1 AND geometry IS NOT NULL
                ORDER BY ABS(snapshot_year - $2) LIMIT 1
            ),
            b AS (
                SELECT geometry, geometry_source::text AS source
                FROM district_snapshots
                WHERE district_cdk = $1 AND geometry IS NOT NULL
                ORDER BY ABS(snapshot_year - $3) LIMIT 1
            )
            SELECT
                -- Areas
                ST_Area(ST_Transform(a.geometry, 7755)) / 1000000.0 AS area_a,
                ST_Area(ST_Transform(b.geometry, 7755)) / 1000000.0 AS area_b,

                -- Intersection (overlap)
                ST_Area(ST_Transform(
                    ST_Intersection(a.geometry, b.geometry), 7755
                )) / 1000000.0 AS overlap_area,

                -- Union (for Jaccard)
                ST_Area(ST_Transform(
                    ST_Union(a.geometry, b.geometry), 7755
                )) / 1000000.0 AS union_area,

                -- Hausdorff distance (in meters, at 7755)
                ST_HausdorffDistance(
                    ST_Transform(a.geometry, 7755),
                    ST_Transform(b.geometry, 7755)
                ) / 1000.0 AS hausdorff_km,

                -- Centroid shift (in meters, at 7755)
                ST_Distance(
                    ST_Transform(ST_Centroid(a.geometry), 7755),
                    ST_Transform(ST_Centroid(b.geometry), 7755)
                ) / 1000.0 AS centroid_shift_km,

                -- Sources
                a.source AS source_a,
                b.source AS source_b

            FROM a, b
        """,
            district_cdk,
            year_a,
            year_b,
        )

        if not result:
            return None

        area_a = float(result["area_a"])
        area_b = float(result["area_b"])
        overlap = float(result["overlap_area"])
        union_area = float(result["union_area"])
        hausdorff = float(result["hausdorff_km"])
        centroid_shift = float(result["centroid_shift_km"])

        # Compute derived metrics
        area_change_pct = ((area_b - area_a) / area_a * 100) if area_a > 0 else 0
        jaccard = overlap / union_area if union_area > 0 else 0

        # Composite shape similarity (0–1, higher = more similar)
        # Weighted combination of Jaccard, area conservation, centroid stability
        area_conservation = 1 - min(abs(area_change_pct) / 100, 1)
        centroid_stability = max(0, 1 - centroid_shift / 50)  # 50km = fully drifted
        hausdorff_score = max(0, 1 - hausdorff / 100)  # 100km = max drift

        shape_similarity = jaccard * 0.4 + area_conservation * 0.25 + centroid_stability * 0.2 + hausdorff_score * 0.15

        return DriftResult(
            district_cdk=district_cdk,
            year_a=year_a,
            year_b=year_b,
            hausdorff_km=round(hausdorff, 3),
            area_a_sqkm=round(area_a, 2),
            area_b_sqkm=round(area_b, 2),
            area_change_pct=round(area_change_pct, 2),
            overlap_area_sqkm=round(overlap, 2),
            jaccard_index=round(jaccard, 4),
            centroid_shift_km=round(centroid_shift, 3),
            shape_similarity=round(shape_similarity, 4),
            source_a=result["source_a"],
            source_b=result["source_b"],
        )

    async def get_drift_timeline(
        self,
        district_cdk: str,
    ) -> list[DriftResult]:
        """
        Compute pairwise drift between consecutive snapshots.
        Returns a timeline of drift results.
        """
        snapshots = await self.db.fetch(
            """
            SELECT snapshot_year
            FROM district_snapshots
            WHERE district_cdk = $1 AND geometry IS NOT NULL
            ORDER BY snapshot_year ASC
        """,
            district_cdk,
        )

        if len(snapshots) < 2:
            return []

        results = []
        for i in range(len(snapshots) - 1):
            year_a = snapshots[i]["snapshot_year"]
            year_b = snapshots[i + 1]["snapshot_year"]
            drift = await self.detect_drift(district_cdk, year_a, year_b)
            if drift:
                results.append(drift)

        return results
