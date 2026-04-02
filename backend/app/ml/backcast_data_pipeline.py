"""
Data pipeline for ML Yield Backcaster.
Fetches yield, area, and climate data for child and parent districts.
"""
import logging
from dataclasses import dataclass
from typing import Any

from app.database import get_pool

logger = logging.getLogger("app.ml.backcast_data_pipeline")


@dataclass
class BackcastTrainingData:
    child_yields: dict[int, float]
    parent_yields: dict[int, float]
    sibling_yields: dict[str, dict[int, float]]
    parent_areas: dict[int, float]
    climate: dict[str, float]
    area_ratio: float


class BackcastDataPipeline:
    """Fetches and shapes data for the YieldBackcaster."""

    async def fetch_training_data(
        self,
        child_cdk: str,
        parent_cdk: str,
        sibling_cdks: list[str],
        split_year: int,
        crop: str,
    ) -> BackcastTrainingData:
        """Fetch all required historical and target data for ML modeling."""
        pool = await get_pool()
        
        async with pool.acquire() as conn:
            # 1. Fetch Yields
            yield_query = """
                SELECT cdk, year, value
                FROM agri_metrics
                WHERE variable_name = $1
                  AND cdk = ANY($2::text[])
            """
            all_cdks = [parent_cdk, child_cdk] + sibling_cdks
            yield_rows = await conn.fetch(yield_query, f"{crop}_yield", all_cdks)
            
            if not yield_rows:
                yield_rows = await conn.fetch(yield_query, "yield", all_cdks)
            
            child_yields: dict[int, float] = {}
            parent_yields: dict[int, float] = {}
            sibling_yields: dict[str, dict[int, float]] = {s: {} for s in sibling_cdks}
            
            for r in yield_rows:
                cdk = r['cdk']
                yr = r['year']
                val = r['value']
                if not val or val <= 0:
                    continue
                    
                if cdk == child_cdk:
                    child_yields[yr] = val
                elif cdk == parent_cdk:
                    parent_yields[yr] = val
                elif cdk in sibling_yields:
                    sibling_yields[cdk][yr] = val
                    
            # 2. Fetch Parent Area
            area_query = """
                SELECT year, value 
                FROM agri_metrics
                WHERE cdk = $1 AND variable_name IN ($2, 'area')
            """
            area_rows = await conn.fetch(area_query, parent_cdk, f"{crop}_area")
            parent_areas = {r['year']: r['value'] for r in area_rows if r['value'] and r['value'] > 0}
            
            # 3. Fetch Climate (placeholder for actual climate queries)
            # Currently falling back to safe defaults that the engine will recognize as missing
            climate: dict[str, float] = {
                "annual_rainfall": 0.0,
                "monsoon_ratio": 0.0
            }
            
            # 4. Area Ratio fallback
            # In a full implementation, this comes from DataApportioner or spatial_analytics.
            # We'll use equal split as default fallback if geometry isn't queried.
            n_children = 1 + len(sibling_cdks)
            area_ratio = 1.0 / n_children if n_children > 0 else 1.0
            
            # Attempt to gather post-split area for this child vs total post-split area
            child_area_query = """
                SELECT cdk, year, value 
                FROM agri_metrics
                WHERE cdk = ANY($1::text[]) AND variable_name IN ($2, 'area') AND year >= $3
            """
            post_split_area_rows = await conn.fetch(child_area_query, all_cdks, f"{crop}_area", split_year)
            
            child_post_area_sum = 0.0
            child_post_area_count = 0
            total_children_post_area_sum = 0.0
            
            for r in post_split_area_rows:
                if r['value'] and r['value'] > 0:
                    if r['cdk'] == child_cdk:
                        child_post_area_sum += r['value']
                        child_post_area_count += 1
                    if r['cdk'] in sibling_cdks or r['cdk'] == child_cdk:
                        total_children_post_area_sum += r['value']
            
            if total_children_post_area_sum > 0 and child_post_area_count > 0:
                # Estimate ratio over all years post-split
                area_ratio = child_post_area_sum / total_children_post_area_sum
                
            return BackcastTrainingData(
                child_yields=child_yields,
                parent_yields=parent_yields,
                sibling_yields=sibling_yields,
                parent_areas=parent_areas,
                climate=climate,
                area_ratio=round(area_ratio, 4)
            )
