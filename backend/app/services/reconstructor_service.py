import logging
import json
from typing import List, Dict, Any, Optional, Tuple, Set
import asyncpg

from app.core.epoch_builder import build_epochs, Epoch

logger = logging.getLogger("app.services.reconstructor")

class ReconstructorService:
    def __init__(self, db: asyncpg.Connection):
        self.db = db
        # Caches
        self._graph_cache: Optional[Dict[str, List[Tuple[List[str], int]]]] = None

    async def _get_split_graph(self) -> Dict[str, List[Tuple[List[str], int]]]:
        if self._graph_cache is not None:
            return self._graph_cache
            
        events = await self.db.fetch("SELECT parent_cdk, child_cdks, split_year FROM split_events")
        graph: Dict[str, List[Tuple[List[str], int]]] = {}
        for row in events:
            p = row["parent_cdk"]
            if p not in graph:
                graph[p] = []
            graph[p].append((row["child_cdks"], row["split_year"]))
            
        self._graph_cache = graph
        return graph

    async def get_lineage_tree(self, root_cdk: str, graph: Dict[str, List[Tuple[List[str], int]]] = None) -> Dict[str, Any]:
        """Returns the tree structure for the frontend without geometry or yields."""
        if graph is None:
            graph = await self._get_split_graph()
            
        def build_node(cdk: str) -> Dict[str, Any]:
            node = {"cdk": cdk, "children": []}
            splits = graph.get(cdk, [])
            for children, s_year in splits:
                for c in children:
                    child_node = build_node(c)
                    child_node["split_year"] = s_year
                    node["children"].append(child_node)
            return node
            
        return build_node(root_cdk)

    async def reconstruct(self, base_cdk: str, crop: str = "rice", min_year: int = 1966) -> Dict[str, Any]:
        """
        Reconstruct the timeline of a district splitting into descendants, aggregating yields,
        using strict epochs from epoch_builder.
        """
        graph = await self._get_split_graph()
        
        # 1. Build standard non-overlapping epochs
        epochs = build_epochs(base_cdk, graph, min_year=min_year)
        
        # 2. Gather all CDKs that ever appear
        all_descendants = set()
        leaf_cdks = set()
        for ep in epochs:
            all_descendants.update(ep.active_cdks)
            leaf_cdks.update(ep.leaf_cdks)
            
        # Optional: check if base_cdk ever had rows in agri_metrics to accurately set is_virtual
        # But we'll trust the epoch builder's guess (which flags it virtual if it split before min_year)
        has_base_data = await self.db.fetchval("""
            SELECT 1 FROM agri_metrics WHERE cdk = $1 LIMIT 1
        """, base_cdk)
        if not has_base_data:
            # Re-flag all epochs
            for ep in epochs:
                ep.is_virtual = True

        # 3. GeoJSON geometries for each epoch
        # PostGIS ST_Union for leaves of that epoch
        epoch_results = []
        for ep in epochs:
            leaves = ep.leaf_cdks
            if leaves:
                geom_row = await self.db.fetchrow("""
                    WITH leaves AS (
                        SELECT geometry FROM district_snapshots
                        WHERE district_cdk = ANY($1) AND geometry IS NOT NULL
                    )
                    SELECT 
                        ST_AsGeoJSON(ST_Union(geometry)) as geojson,
                        GeometryType(ST_Union(geometry)) as type
                    FROM leaves
                """, list(leaves))
                
                geojson = geom_row["geojson"] if geom_row else None
                is_contiguous = geom_row["type"] != "MULTIPOLYGON" if geom_row and geom_row["type"] else True
            else:
                geojson = None
                is_contiguous = True

            ep_data = {
                "epoch_num": ep.epoch_num,
                "year_start": ep.year_start,
                "year_end": ep.year_end,
                "event_label": ep.event_label,
                "active_cdks": ep.active_cdks,
                "leaf_cdks": list(leaves),
                "is_virtual": ep.is_virtual,
                "reconstructed_geojson": json.loads(geojson) if geojson else None,
                "is_contiguous": is_contiguous,
                "metrics": []
            }
            epoch_results.append((ep, ep_data))

        # 4. Yield aggregation per epoch year
        # Fetch all metrics
        metrics = await self.db.fetch("""
            SELECT cdk, year, variable_name, value
            FROM agri_metrics
            WHERE cdk = ANY($1) 
              AND variable_name IN ($2, $3)
        """, list(all_descendants), f"{crop}_production", f"{crop}_area")

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
            
        # Get reference active area for coverage metric. 
        # A simple method: use the sum of geo area from snapshots or max area across years.
        # We will approximate coverage as length of cdks with data / length of active cdks.
        
        final_epochs = []
        for ep, ep_data in epoch_results:
            y_start = ep.year_start
            y_end = ep.year_end if ep.year_end else 2024
            
            for year in range(y_start, y_end + 1):
                active = ep.active_cdks
                
                total_prod = 0.0
                total_area = 0.0
                cdks_with_data = 0
                
                for cdk in active:
                    cdk_data = metric_dict.get(year, {}).get(cdk, {})
                    p = cdk_data.get(f"{crop}_production")
                    a = cdk_data.get(f"{crop}_area")
                    if p is not None and a is not None:
                        total_prod += p
                        total_area += a
                        cdks_with_data += 1
                        
                coverage = cdks_with_data / len(active) if active else 0.0
                yield_val = (total_prod / total_area) * 1000 if total_area > 0 else None
                
                ep_data["metrics"].append({
                    "year": year,
                    "data_coverage": coverage,
                    "collective_yield": yield_val,
                    "collective_production": total_prod if cdks_with_data > 0 else None,
                    "collective_area": total_area if cdks_with_data > 0 else None,
                })
                
            final_epochs.append(ep_data)

        return {
            "root_cdk": base_cdk,
            "crop": crop,
            "epochs": final_epochs
        }
