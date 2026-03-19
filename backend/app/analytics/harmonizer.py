"""
Boundary Harmonizer: Reconstruct historical series across administrative changes.

RULES (Non-Negotiable):
- Never fabricate values
- Only apportion using area ratios, population weights, or equal split
- Always annotate method on derived values
- Reject if coverage ratios don't sum to ~1.0
"""
from typing import List, Dict, Optional, Literal
from dataclasses import dataclass
import json
import logging
import asyncpg  # type: ignore

from app.config import get_settings  # type: ignore

settings = get_settings()


@dataclass
class HarmonizedPoint:
    """A single harmonized data point with method annotation."""
    year: int
    value: float
    method: str  # 'raw', 'area_weighted', 'equal_split', etc.
    source_cdks: List[str]
    coverage: float  # Coverage ratio (0-1)


class BoundaryHarmonizer:
    """
    Reconstructs boundary-adjusted time series for longitudinal analysis.

    Supports two primary use cases:
    1. Before/After: Combine children post-split to compare with parent pre-split
    2. Entity Comparison: Track individual entities across time
    """

    def __init__(self, tolerance: Optional[float] = None):
        self.tolerance = tolerance or settings.coverage_ratio_tolerance

    def validate_coverage_ratios(
        self,
        coverage_ratios: Dict[str, float]
    ) -> bool:
        """
        Validate that coverage ratios sum to ~1.0 (within tolerance).

        Args:
            coverage_ratios: Dict mapping child CDK to area proportion

        Returns:
            True if valid, False otherwise
        """
        if not coverage_ratios:
            return False

        total = sum(coverage_ratios.values())
        return abs(total - 1.0) <= self.tolerance

    def reconstruct_parent_from_children(
        self,
        children_data: Dict[int, Dict[str, Dict[str, float]]],
        child_cdks: List[str],
        metric: Literal["area", "production", "yield"],
        coverage_ratios: Optional[Dict[str, float]] = None,
        method: Literal["area_weighted", "equal_split"] = "area_weighted"
    ) -> List[HarmonizedPoint]:
        """
        Reconstruct parent district values from children's data.

        For yield: weighted average by area
        For area/production: simple sum

        Args:
            children_data: Dict[year][cdk] -> {area, prod, yld}
            child_cdks: List of child district CDKs
            metric: Which metric to reconstruct
            coverage_ratios: Optional area proportions (if known)
            method: Harmonization method

        Returns:
            List of HarmonizedPoint for post-split years
        """
        results = []

        for year in sorted(children_data.keys()):
            year_data = children_data[year]

            # Collect values from all children that have data
            child_values = []
            child_areas = []
            active_cdks = []

            for cdk in child_cdks:
                if cdk in year_data:
                    data = year_data[cdk]
                    area = data.get("area", 0)

                    if area > 0:
                        child_areas.append(area)
                        active_cdks.append(cdk)

                        if metric == "area":
                            child_values.append(area)
                        elif metric == "production":
                            child_values.append(data.get("prod", 0))
                        elif metric == "yield":
                            child_values.append(data.get("yld", 0))

            if not child_values:
                continue

            # Calculate reconstructed value based on metric type
            if metric in ("area", "production"):
                # Simple sum for extensive properties
                value = sum(child_values)
                used_method = "sum"
            elif metric == "yield":
                # Area-weighted average for intensive properties
                if method == "area_weighted" and sum(child_areas) > 0:
                    weighted_sum = sum(
                        v * a for v,
                        a in zip(
                            child_values,
                            child_areas))
                    value = weighted_sum / sum(child_areas)
                    used_method = "area_weighted"
                else:
                    # Equal weight fallback
                    value = sum(child_values) / len(child_values)
                    used_method = "equal_split"
            else:
                continue

            # Calculate coverage (how many children contributed)
            coverage = len(active_cdks) / len(child_cdks) if child_cdks else 0

            results.append(HarmonizedPoint(
                year=year,
                value=value,
                method=used_method,
                source_cdks=active_cdks,
                coverage=coverage,
            ))

        return results

    def get_parent_series(
        self,
        data_map: Dict[int, Dict[str, Dict[str, float]]],
        parent_cdk: str,
        metric: Literal["area", "production", "yield"],
    ) -> List[HarmonizedPoint]:
        """
        Extract parent series for pre-split years.

        Args:
            data_map: Dict[year][cdk] -> {area, prod, yld}
            parent_cdk: Parent district CDK
            metric: Which metric to extract

        Returns:
            List of HarmonizedPoint for pre-split years
        """
        results = []

        for year in sorted(data_map.keys()):
            year_data = data_map[year]

            if parent_cdk not in year_data:
                continue

            data = year_data[parent_cdk]

            if metric == "area":
                value = data.get("area", 0)
            elif metric == "production":
                value = data.get("prod", 0)
            elif metric == "yield":
                value = data.get("yld", 0)
            else:
                continue

            if value is None or value == 0:
                continue

            results.append(HarmonizedPoint(
                year=year,
                value=value,
                method="raw",
                source_cdks=[parent_cdk],
                coverage=1.0,
            ))

        return results

    def merge_series(
        self,
        pre_split: List[HarmonizedPoint],
        post_split: List[HarmonizedPoint],
        split_year: int,
    ) -> List[HarmonizedPoint]:
        """
        Merge pre-split and post-split series into continuous timeline.

        Args:
            pre_split: Parent data points (year < split_year)
            post_split: Reconstructed child data (year >= split_year)
            split_year: Year of administrative change

        Returns:
            Merged timeline with clear method annotations
        """
        result = []

        # Add pre-split data
        for point in pre_split:
            if point.year < split_year:
                result.append(point)

        # Add post-split data
        for point in post_split:
            if point.year >= split_year:
                result.append(point)

        # Sort by year
        result.sort(key=lambda p: p.year)

        return result

    async def compute_split_diff(self, db: asyncpg.Connection, split_event_id: int):
        from app.core.geometry_resolver import GeometryResolver  # type: ignore
        logger = logging.getLogger(__name__)
        
        # 1. Fetch event
        event = await db.fetchrow("SELECT parent_cdk, child_cdks, split_year FROM split_events WHERE id = $1", split_event_id)
        if not event:
            raise ValueError(f"Split event {split_event_id} not found")
            
        parent_cdk = event["parent_cdk"]
        child_cdks = event["child_cdks"]
        split_year = event["split_year"]
        
        # 2. Get Geometries
        parent_geom = await GeometryResolver.get_geometry(db, parent_cdk, split_year)
        if not parent_geom:
            logger.warning(f"No parent geometry resolved for {parent_cdk}")
            return
            
        parent_geojson = json.dumps(parent_geom)
        
        for child_cdk in child_cdks:
            child_geom = await GeometryResolver.get_geometry(db, child_cdk, split_year)
            if not child_geom:
                logger.warning(f"No child geometry resolved for {child_cdk}")
                continue
                
            child_geojson = json.dumps(child_geom)
            
            # ST_Intersection for Transferred Area
            intersect_query = """
                SELECT 
                    ST_Area(ST_Intersection(ST_SetSRID(ST_GeomFromGeoJSON($1), 4326), ST_SetSRID(ST_GeomFromGeoJSON($2), 4326))::geography) / 1000000.0 as area_sqkm,
                    ST_AsGeoJSON(ST_Multi(ST_CollectionExtract(ST_Intersection(ST_SetSRID(ST_GeomFromGeoJSON($1), 4326), ST_SetSRID(ST_GeomFromGeoJSON($2), 4326)), 3))) as geomj
            """
            intersect_res = await db.fetchrow(intersect_query, parent_geojson, child_geojson)
            
            if intersect_res and intersect_res["area_sqkm"] is not None:
                area = intersect_res["area_sqkm"]
                if area > 0:
                    await db.execute("""
                        INSERT INTO area_transfers
                            (split_event_id, source_cdk, dest_cdk, transfer_type, area_sqkm, confidence_score, geometry)
                        VALUES
                            ($1, $2, $3, 'inherited', $4, 0.8, ST_SetSRID(ST_GeomFromGeoJSON($5), 4326))
                    """, split_event_id, parent_cdk, child_cdk, area, intersect_res["geomj"])
                    logger.info(f"Recorded area transfer {parent_cdk} -> {child_cdk}: {area:.2f} sqkm")

