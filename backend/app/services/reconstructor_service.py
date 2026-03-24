"""
Reconstructor Service — core logic for lineage epoch reconstruction.
Bridges split_events (text CDKs) with district_snapshots (geometries)
and agri_metrics (yields via LGD codes).
v3: Uses LineageGraph DAG and DataApportioner with conservation validation.
"""
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
import asyncpg  # type: ignore

from app.core.epoch_builder import build_epochs_from_graph  # type: ignore
from app.core.lineage_graph import LineageGraph  # type: ignore
from app.core.data_apportioner import DataApportioner  # type: ignore

logger = logging.getLogger("app.services.reconstructor")

# State code to state name mapping for display
STATE_CODE_MAP: Dict[str, str] = {
    "WB": "West Bengal", "DL": "Delhi", "NC": "NCT of Delhi",
    "UP": "Uttar Pradesh", "MH": "Maharashtra", "TN": "Tamil Nadu",
    "KA": "Karnataka", "RJ": "Rajasthan", "GJ": "Gujarat",
    "MP": "Madhya Pradesh", "HR": "Haryana", "PB": "Punjab",
    "JH": "Jharkhand", "OD": "Odisha", "KL": "Kerala",
    "HP": "Himachal Pradesh", "UK": "Uttarakhand", "JK": "Jammu and Kashmir",
    "TG": "Telangana", "AP": "Andhra Pradesh", "BR": "Bihar",
    "AS": "Assam", "SK": "Sikkim", "NL": "Nagaland",
    "MZ": "Mizoram", "MN": "Manipur", "ML": "Meghalaya",
    "TR": "Tripura", "GA": "Goa", "CG": "Chhattisgarh",
    "LD": "Lakshadweep", "PY": "Puducherry",
}


class ReconstructorService:
    def __init__(self, db: asyncpg.Connection):
        self.db = db
        self._lineage_graph: Optional[LineageGraph] = None
        self._graph_cache: Optional[Dict[str, List[Tuple[List[str], int]]]] = None
        self.apportioner = DataApportioner()

    async def _get_lineage_graph(self) -> LineageGraph:
        """Fetch split_events and build a deduplicated LineageGraph."""
        if self._lineage_graph is not None:
            return self._lineage_graph

        events = await self.db.fetch(
            "SELECT parent_cdk, child_cdks, split_year FROM split_events"
        )
        self._lineage_graph = LineageGraph.from_split_events(
            [dict(r) for r in events]
        )
        return self._lineage_graph

    async def _get_split_graph(self) -> Dict[str, List[Tuple[List[str], int]]]:
        """Backward-compatible: fetch graph as raw dict."""
        cache = self._graph_cache
        if cache is not None:
            return cache

        graph = await self._get_lineage_graph()
        self._graph_cache = graph.get_split_graph_compat()
        result = self._graph_cache
        assert result is not None
        return result

    async def get_lineage_tree(
        self,
        root_cdk: str,
        graph: Optional[Dict[str, List[Tuple[List[str], int]]]] = None,
    ) -> Dict[str, Any]:
        """Returns the tree structure for the frontend without geometry or yields."""
        if graph is None:
            graph = await self._get_split_graph()

        def build_node(cdk: str) -> Dict[str, Any]:
            node: Dict[str, Any] = {"cdk": cdk, "children": []}
            splits = graph.get(cdk, [])
            for children, s_year in splits:
                for c in children:
                    child_node = build_node(c)
                    child_node["split_year"] = s_year
                    node["children"].append(child_node)
            return node

        return build_node(root_cdk)

    async def _get_cdk_name(self, cdk: str) -> str:
        """Resolve a text CDK to its human-readable district name."""
        # Try district_snapshots first
        name = await self.db.fetchval(
            "SELECT district_name FROM district_snapshots "
            "WHERE district_cdk = $1 LIMIT 1",
            cdk,
        )
        if name:
            return name
        # Fallback: parse from CDK string (e.g., DL_delhi_1991 → Delhi)
        parts = cdk.split("_")
        if len(parts) >= 2:
            return parts[1].replace("_", " ").title()
        return cdk

    async def reconstruct(
        self,
        base_cdk: str,
        crop: str = "rice",
        min_year: int = 1966,
    ) -> Dict[str, Any]:
        """
        Reconstruct the timeline of a district splitting into descendants.
        
        Data flow:
        1. Build epochs from split_events graph (text CDKs)
        2. For each epoch, try PostGIS ST_Union for geometry
        3. For yield data, attempt to match CDKs to LGD codes via
           district name matching, then aggregate from agri_metrics
        """
        graph = await self._get_lineage_graph()

        # 1. Build standard non-overlapping epochs (using DAG)
        epochs = build_epochs_from_graph(base_cdk, graph, min_year=min_year)

        if not epochs:
            return {"root_cdk": base_cdk, "crop": crop, "epochs": []}

        # 2. Gather all CDKs that ever appear across epochs
        all_descendants: set = set()
        all_leaf_cdks: set = set()
        for ep in epochs:
            all_descendants.update(ep.active_cdks)
            all_leaf_cdks.update(ep.leaf_cdks)

        # 3. Build CDK → district name map for display
        cdk_name_map: Dict[str, str] = {}
        for cdk in all_descendants:
            cdk_name_map[cdk] = await self._get_cdk_name(cdk)

        # 4. Build CDK → LGD code bridge for yield lookup
        # Match text CDK district names to districts table names
        cdk_to_lgd = await self._build_cdk_lgd_bridge(all_descendants)

        # 5. Process each epoch
        epoch_results: List[Dict[str, Any]] = []
        for ep in epochs:
            leaves = ep.leaf_cdks

            # --- Geometry ---
            geojson = None
            is_contiguous = True
            if leaves:
                try:
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

                    if geom_row and geom_row["geojson"]:
                        geojson = json.loads(geom_row["geojson"])
                        is_contiguous = (
                            geom_row["type"] != "MULTIPOLYGON"
                            if geom_row["type"]
                            else True
                        )
                except Exception as geo_err:
                    logger.warning(f"Geometry lookup failed for epoch {ep.epoch_num}: {geo_err}")

            # --- Yield aggregation ---
            y_start = int(ep.year_start)
            y_end = int(ep.year_end) if ep.year_end is not None else 2024
            metrics_list: List[Dict[str, Any]] = []

            # Collect LGD codes for the active CDKs in this epoch
            active_lgds = []
            for cdk in ep.active_cdks:  # type: ignore[attr-defined]
                lgd = cdk_to_lgd.get(cdk)
                if lgd is not None:
                    active_lgds.append(lgd)

            # Fetch yield data if we have any LGD mappings
            metric_dict: Dict[int, Dict[int, Dict[str, float]]] = {}
            if active_lgds:
                try:
                    prod_var = f"{crop}_production"
                    area_var = f"{crop}_area"
                    rows = await self.db.fetch("""
                        SELECT district_lgd, year, variable_name, value
                        FROM agri_metrics
                        WHERE district_lgd = ANY($1)
                          AND variable_name IN ($2, $3)
                          AND year >= $4 AND year <= $5
                    """, active_lgds, prod_var, area_var, y_start, y_end)

                    for row in rows:
                        yr = row["year"]
                        lgd = row["district_lgd"]
                        var = row["variable_name"]
                        val = float(row["value"]) if row["value"] else 0.0

                        if yr not in metric_dict:
                            metric_dict[yr] = {}
                        if lgd not in metric_dict[yr]:
                            metric_dict[yr][lgd] = {}
                        metric_dict[yr][lgd][var] = val
                except Exception as met_err:
                    logger.warning(f"Metrics lookup failed for epoch {ep.epoch_num}: {met_err}")  # type: ignore[attr-defined]

            for year in range(y_start, y_end + 1):  # type: ignore[operator]
                total_prod = 0.0
                total_area = 0.0
                cdks_with_data = 0

                for lgd in active_lgds:
                    lgd_data = metric_dict.get(year, {}).get(lgd, {})
                    p = lgd_data.get(f"{crop}_production")
                    a = lgd_data.get(f"{crop}_area")
                    if p is not None and a is not None:
                        total_prod += p  # type: ignore[operator]
                        total_area += a  # type: ignore[operator]
                        cdks_with_data += 1  # type: ignore[operator]

                coverage = (
                    float(cdks_with_data) / len(ep.active_cdks)
                    if ep.active_cdks
                    else 0.0
                )
                yield_val = (
                    round((total_prod / total_area) * 1000.0, 2)  # type: ignore[call-overload]
                    if total_area > 0  # type: ignore[operator]
                    else None
                )

                metrics_list.append({
                    "year": year,
                    "data_coverage": round(coverage, 3),  # type: ignore[call-overload]
                    "collective_yield": yield_val,
                    "collective_production": round(total_prod, 2) if cdks_with_data > 0 else None,  # type: ignore[call-overload]
                    "collective_area": round(total_area, 2) if cdks_with_data > 0 else None,  # type: ignore[call-overload]
                })

            # Build event label with district names
            active_names = [cdk_name_map.get(c, c) for c in ep.active_cdks]

            ep_data: Dict[str, Any] = {
                "epoch_num": ep.epoch_num,
                "year_start": ep.year_start,
                "year_end": ep.year_end,
                "event_label": ep.event_label,
                "active_cdks": ep.active_cdks,
                "active_names": active_names,
                "leaf_cdks": list(leaves),
                "is_virtual": ep.is_virtual,
                "reconstructed_geojson": geojson,
                "is_contiguous": is_contiguous,
                "metrics": metrics_list,
            }
            epoch_results.append(ep_data)

        return {
            "root_cdk": base_cdk,
            "root_name": cdk_name_map.get(base_cdk, base_cdk),
            "crop": crop,
            "epochs": epoch_results,
        }

    async def _build_cdk_lgd_bridge(
        self, cdks: set
    ) -> Dict[str, int]:
        """
        Build a mapping from text CDKs (e.g., DL_delhi_1991) to numeric
        LGD codes used in the agri_metrics table.
        
        Strategy:
        1. Get district names from district_snapshots for each CDK
        2. Match those names against the districts table to find LGD codes
        3. Return the mapping
        """
        bridge: Dict[str, int] = {}

        for cdk in cdks:
            try:
                # Get the name from district_snapshots
                snap = await self.db.fetchrow(
                    "SELECT district_name FROM district_snapshots "
                    "WHERE district_cdk = $1 LIMIT 1",
                    cdk,
                )
                if not snap:
                    # Try parsing the CDK
                    parts = cdk.split("_")
                    if len(parts) >= 2:
                        name_guess = parts[1]
                    else:
                        continue
                else:
                    name_guess = snap["district_name"]

                # Look up LGD code from districts table by name match
                # Extract state from CDK prefix
                state_prefix = cdk.split("_")[0] if "_" in cdk else ""
                state_name = STATE_CODE_MAP.get(state_prefix, "")

                if state_name:
                    lgd = await self.db.fetchval("""
                        SELECT lgd_code FROM districts
                        WHERE LOWER(district_name) LIKE LOWER($1)
                          AND UPPER(state_name) = UPPER($2)
                        LIMIT 1
                    """, f"%{name_guess}%", state_name)
                else:
                    lgd = await self.db.fetchval("""
                        SELECT lgd_code FROM districts
                        WHERE LOWER(district_name) LIKE LOWER($1)
                        LIMIT 1
                    """, f"%{name_guess}%")

                if lgd:
                    bridge[cdk] = int(lgd)
            except Exception as e:
                logger.debug(f"Could not map CDK {cdk} to LGD: {e}")

        logger.info(
            f"CDK->LGD bridge: mapped {len(bridge)}/{len(cdks)} CDKs"
        )
        return bridge
