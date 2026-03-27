"""
Reconstructor Service — core logic for lineage epoch reconstruction.
Bridges split_events (text CDKs) with district_snapshots (geometries)
and agri_metrics (yields via CDK keys).
v4: Ancestor-fallback yield lookup — when children lack data, uses parent CDK.
"""
import json
import logging
from typing import Any, cast

import asyncpg  # type: ignore

from app.core.data_apportioner import DataApportioner  # type: ignore
from app.core.epoch_builder import Epoch, build_epochs_from_graph  # type: ignore
from app.core.lineage_graph import LineageGraph  # type: ignore

logger = logging.getLogger("app.services.reconstructor")

# State code to state name mapping for display
STATE_CODE_MAP: dict[str, str] = {
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
        self._lineage_graph: LineageGraph | None = None
        self._graph_cache: dict[str, list[tuple[list[str], int]]] | None = None
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

    async def _get_split_graph(self) -> dict[str, list[tuple[list[str], int]]]:
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
        graph: dict[str, list[tuple[list[str], int]]] | None = None,
    ) -> dict[str, Any]:
        """Returns the tree structure for the frontend without geometry or yields."""
        if graph is None:
            graph = await self._get_split_graph()

        def build_node(cdk: str) -> dict[str, Any]:
            node: dict[str, Any] = {"cdk": cdk, "children": []}
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
        # Try districts table first
        name = await self.db.fetchval(
            "SELECT district_name FROM districts "
            "WHERE cdk = $1 LIMIT 1",
            cdk,
        )
        if name:
            return name
        # Try district_snapshots
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

    # ------------------------------------------------------------------
    # Data CDK resolution — resolves active CDKs to CDKs that have data
    # ------------------------------------------------------------------

    async def _find_cdks_with_data(self, candidate_cdks: list[str]) -> set[str]:
        """Check which CDKs actually have rows in agri_metrics."""
        if not candidate_cdks:
            return set()
        try:
            rows = await self.db.fetch(
                "SELECT DISTINCT cdk FROM agri_metrics WHERE cdk = ANY($1)",
                candidate_cdks,
            )
            return {str(r["cdk"]) for r in rows}
        except Exception:
            return set()

    def _build_parent_map(
        self, graph: dict[str, list[tuple[list[str], int]]]
    ) -> dict[str, str]:
        """Build child → parent mapping from the split graph."""
        parent_of: dict[str, str] = {}
        for parent, splits in graph.items():
            for children, _ in splits:
                for child in children:
                    parent_of[child] = parent
        return parent_of

    async def _resolve_data_cdks(
        self,
        active_cdks: list[str],
        base_cdk: str,
        parent_map: dict[str, str],
    ) -> tuple[list[str], bool]:
        """
        Resolve active CDKs to CDKs that have data in agri_metrics.

        Strategy:
        1. Check which active CDKs have data directly
        2. For CDKs without data, walk up ancestors to find nearest with data
        3. If no ancestors found, try the root base_cdk
        4. Return (data_cdks, is_fallback) — deduplicated list of CDKs to query

        The is_fallback flag indicates parent/ancestor data was used.
        """
        # Step 1: Check direct data
        cdks_with_data = await self._find_cdks_with_data(active_cdks)

        if cdks_with_data and len(cdks_with_data) == len(active_cdks):
            # All active CDKs have data — no fallback needed
            return active_cdks, False

        if cdks_with_data:
            # Some have data, use those (partial coverage can be computed normally)
            return list(cdks_with_data), False

        # Step 2: No active CDKs have data — try ancestors
        ancestor_candidates: set[str] = set()
        for cdk in active_cdks:
            current = cdk
            while current in parent_map:
                current = parent_map[current]
                ancestor_candidates.add(current)

        # Also add base_cdk as the ultimate fallback
        ancestor_candidates.add(base_cdk)

        ancestor_with_data = await self._find_cdks_with_data(
            list(ancestor_candidates)
        )

        if ancestor_with_data:
            # Use the most specific ancestor (prefer closer to active CDKs)
            # Walk each active CDK's lineage and pick the first ancestor with data
            data_cdks: set[str] = set()
            for cdk in active_cdks:
                current = cdk
                while current in parent_map:
                    current = parent_map[current]
                    if current in ancestor_with_data:
                        data_cdks.add(current)
                        break
                else:
                    # No ancestor in chain — try base_cdk
                    if base_cdk in ancestor_with_data:
                        data_cdks.add(base_cdk)

            if data_cdks:
                return list(data_cdks), True

        # Step 3: No data anywhere — return active CDKs (will produce N/A)
        return active_cdks, False

    # ------------------------------------------------------------------
    # Main reconstruction
    # ------------------------------------------------------------------

    async def reconstruct(
        self,
        base_cdk: str,
        crop: str = "rice",
        min_year: int = 1966,
    ) -> dict[str, Any]:
        """
        Reconstruct the timeline of a district splitting into descendants.

        Data flow:
        1. Build epochs from split_events graph (text CDKs)
        2. For each epoch, try PostGIS ST_Union for geometry
        3. For yield data, resolve CDKs to data CDKs via ancestor fallback
        4. Aggregate yield, production, area across data CDKs
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
        cdk_name_map: dict[str, str] = {}
        for cdk in all_descendants:
            cdk_name_map[cdk] = await self._get_cdk_name(cdk)

        # 4. Build parent map for ancestor fallback
        split_graph = await self._get_split_graph()
        parent_map = self._build_parent_map(split_graph)

        # 5. Process each epoch
        epoch_results: list[dict[str, Any]] = []
        for ep_raw in epochs:
            ep = cast(Epoch, ep_raw)
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

            # --- Yield aggregation with ancestor fallback ---
            y_start: int = int(ep.year_start)
            y_end: int = int(ep.year_end) if ep.year_end is not None else 2024
            metrics_list: list[dict[str, Any]] = []

            active_cdks_list: list[str] = list(ep.active_cdks)  # type: ignore[attr-defined]

            # Resolve which CDKs to actually query for data
            data_cdks, is_fallback = await self._resolve_data_cdks(
                active_cdks_list, base_cdk, parent_map
            )
            num_data_cdks: int = len(data_cdks)

            # Fetch yield data from resolved data CDKs
            metric_dict: dict[int, dict[str, dict[str, float]]] = {}
            if data_cdks:
                try:
                    prod_var: str = f"{crop}_production"
                    area_var: str = f"{crop}_area"
                    rows = await self.db.fetch("""
                        SELECT cdk, year, variable_name, value
                        FROM agri_metrics
                        WHERE cdk = ANY($1)
                          AND variable_name IN ($2, $3)
                          AND year >= $4 AND year <= $5
                    """, data_cdks, prod_var, area_var, y_start, y_end)

                    for row in rows:
                        yr: int = int(row["year"])
                        cdk_key: str = str(row["cdk"])
                        var: str = str(row["variable_name"])
                        val: float = float(row["value"]) if row["value"] is not None else 0.0

                        if yr not in metric_dict:
                            metric_dict[yr] = {}
                        if cdk_key not in metric_dict[yr]:
                            metric_dict[yr][cdk_key] = {}
                        metric_dict[yr][cdk_key][var] = val
                except Exception as met_err:
                    logger.warning(f"Metrics lookup failed for epoch {ep.epoch_num}: {met_err}")  # type: ignore[attr-defined]

            for year in range(y_start, y_end + 1):  # type: ignore[operator]
                total_prod: float = 0.0
                total_area: float = 0.0
                cdks_with_data: int = 0

                for cdk_key in data_cdks:
                    cdk_data = metric_dict.get(year, {}).get(cdk_key, {})
                    p = cdk_data.get(f"{crop}_production")
                    a = cdk_data.get(f"{crop}_area")
                    if p is not None and a is not None:
                        total_prod += float(p)  # type: ignore
                        total_area += float(a)  # type: ignore
                        cdks_with_data += 1

                coverage: float = (
                    float(cdks_with_data) / float(num_data_cdks)
                    if num_data_cdks > 0
                    else 0.0
                )
                yield_val = (
                    round((total_prod / total_area) * 1000.0, 2)  # type: ignore
                    if total_area > 0  # type: ignore
                    else None
                )

                metrics_list.append({
                    "year": year,
                    "data_coverage": round(coverage, 3),  # type: ignore
                    "collective_yield": yield_val,
                    "collective_production": round(total_prod, 2) if cdks_with_data > 0 else None,  # type: ignore
                    "collective_area": round(total_area, 2) if cdks_with_data > 0 else None,  # type: ignore
                    "is_fallback": is_fallback,
                })

            # Build event label with district names
            active_names = [cdk_name_map.get(c, c) for c in ep.active_cdks]

            ep_data: dict[str, Any] = {
                "epoch_num": ep.epoch_num,
                "year_start": ep.year_start,
                "year_end": ep.year_end,
                "event_label": ep.event_label,
                "active_cdks": ep.active_cdks,
                "active_names": active_names,
                "data_cdks": data_cdks,
                "is_fallback": is_fallback,
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
