"""
Reconstructor Service
Handles reverse-engineering of district splits into original map coverage and aggregate yields.
"""
import logging
import json
from typing import List, Dict, Any, Optional
import asyncpg

logger = logging.getLogger("app.services.reconstructor")

class ReconstructorService:
    def __init__(self, db: asyncpg.Connection):
        self.db = db

    async def _get_timeline(self, base_cdk: str) -> Dict[int, List[str]]:
        """Returns a mapping of year -> active descendant cdks."""
        events = await self.db.fetch("SELECT parent_cdk, child_cdks, split_year FROM split_events")
        
        split_map: Dict[str, list] = {}
        for event in events:
            p = event["parent_cdk"]
            if p not in split_map:
                split_map[p] = []
            split_map[p].append((event["child_cdks"], event["split_year"]))

        timeline: Dict[int, List[str]] = {}
        active_cdks = {base_cdk}
        
        for year in range(1950, 2025):
            splits_happened = True
            while splits_happened:
                splits_happened = False
                for active_c in list(active_cdks):
                    splits = [s for s in split_map.get(active_c, []) if s[1] == year]
                    if splits:
                        try:
                            active_cdks.remove(active_c)
                        except KeyError:
                            pass
                        for children, s_year in splits:
                            active_cdks.update([str(c) for c in children])
                        splits_happened = True
            
            timeline[year] = sorted(list(active_cdks))
            
        return timeline

    async def reconstruct(self, base_cdk: str, crop: str = "rice", start_year: int = 1990, end_year: int = 2020) -> Dict[str, Any]:
        """
        Reconstruct the timeline of a district splitting into descendants, aggregating yields.
        """
        timeline = await self._get_timeline(base_cdk)
        
        all_descendants = set()
        for cdks in timeline.values():
            all_descendants.update(cdks)
            
        metrics = await self.db.fetch("""
            SELECT cdk, year, variable_name, value
            FROM agri_metrics
            WHERE cdk = ANY($1) 
              AND year >= $2 AND year <= $3
              AND variable_name IN ($4, $5)
        """, list(all_descendants), start_year, end_year, f"{crop}_production", f"{crop}_area")

        metric_dict: Dict[int, Dict[str, Dict[str, float]]] = {}
        for row in metrics:
            yr = row['year']
            c = row['cdk']
            var = row['variable_name']
            val = float(row['value'])
            
            if yr not in metric_dict:
                metric_dict[yr] = {}
            if c not in metric_dict[yr]:
                metric_dict[yr][c] = {}
            metric_dict[yr][c][var] = val
            
        result_timeline = []
        for year in range(start_year, end_year + 1):
            active = timeline.get(year, [base_cdk])
            
            total_prod = 0.0
            total_area = 0.0
            data_found = False
            
            for cdk in active:
                cdk_data = metric_dict.get(year, {}).get(cdk, {})
                p = cdk_data.get(f"{crop}_production")
                a = cdk_data.get(f"{crop}_area")
                if p is not None and a is not None:
                    total_prod += p
                    total_area += a
                    data_found = True
                    
            yield_val = (total_prod / total_area) * 1000 if total_area > 0 else None
            
            prev_year_active = timeline.get(year - 1, []) if year > 1950 else []
            is_split_year = (year > 1950 and active != prev_year_active)
            
            result_timeline.append({
                "year": year,
                "active_cdks": active,
                "total_production": round(total_prod, 2) if data_found else None,
                "total_area": round(total_area, 2) if data_found else None,
                "yield_kg_ha": round(yield_val, 2) if yield_val is not None else None,
                "is_split_year": is_split_year
            })

        leaf_cdks = timeline.get(2024, [base_cdk])
        
        geojson = await self.db.fetchval("""
            SELECT ST_AsGeoJSON(ST_Union(geometry))
            FROM district_snapshots
            WHERE district_cdk = ANY($1) AND geometry IS NOT NULL
        """, leaf_cdks)

        return {
            "base_cdk": base_cdk,
            "crop": crop,
            "reconstructed_geometry": json.loads(geojson) if geojson else None,
            "leaf_descendants": leaf_cdks,
            "timeline": result_timeline
        }
