"""
Reconstructor Service — core logic for lineage epoch reconstruction.
Bridges split_events (text CDKs) with district_snapshots (geometries)
and agri_metrics (yields via LGD integer codes).

v5: Fixed CDK→LGD resolution — text CDKs from split_events must be
    resolved to integer district_lgd before querying agri_metrics.
"""

import json
import logging
from typing import Any, Literal, cast

import asyncpg  # type: ignore

from app.core.data_apportioner import DataApportioner  # type: ignore
from app.core.epoch_builder import Epoch, build_epochs_from_graph  # type: ignore
from app.core.lineage_graph import LineageGraph  # type: ignore

logger = logging.getLogger("app.services.reconstructor")

# State code to state name mapping for display
STATE_CODE_MAP: dict[str, str] = {
    "WB": "West Bengal",
    "DL": "Delhi",
    "NC": "NCT of Delhi",
    "UP": "Uttar Pradesh",
    "MH": "Maharashtra",
    "TN": "Tamil Nadu",
    "KA": "Karnataka",
    "RJ": "Rajasthan",
    "GJ": "Gujarat",
    "MP": "Madhya Pradesh",
    "HR": "Haryana",
    "PB": "Punjab",
    "JH": "Jharkhand",
    "OD": "Odisha",
    "KL": "Kerala",
    "HP": "Himachal Pradesh",
    "UK": "Uttarakhand",
    "JK": "Jammu and Kashmir",
    "TG": "Telangana",
    "AP": "Andhra Pradesh",
    "BR": "Bihar",
    "AS": "Assam",
    "SK": "Sikkim",
    "NL": "Nagaland",
    "MZ": "Mizoram",
    "MN": "Manipur",
    "ML": "Meghalaya",
    "TR": "Tripura",
    "GA": "Goa",
    "CG": "Chhattisgarh",
    "LD": "Lakshadweep",
    "PY": "Puducherry",
    "AR": "Arunachal Pradesh",
    "NE": "Northeast",
}

# Seasonal variants to try for crops with known seasonal suffixes
CROP_SEASON_MAP: dict[str, list[str]] = {
    "rice": ["kharif", "winter", "autumn", "summer"],
    "wheat": ["rabi"],
    "maize": ["kharif"],
    "soyabean": ["kharif"],
    "groundnut": ["kharif"],
    "cotton": ["kharif"],
    "pearl_millet": ["kharif"],
    "bajra": ["kharif"],
    "jowar": ["kharif"],
    "sugarcane": [],
}


class ReconstructorService:
    def __init__(self, db: asyncpg.Connection):
        self.db = db
        self._lineage_graph: LineageGraph | None = None
        self._graph_cache: dict[str, list[tuple[list[str], int]]] | None = None
        self.apportioner = DataApportioner()
        # Cache: text_cdk -> int lgd_code (or None if unresolvable)
        self._cdk_to_lgd: dict[str, int | None] = {}

    # ------------------------------------------------------------------
    # CDK → LGD resolution (the critical bridge between the two systems)
    # ------------------------------------------------------------------

    async def _resolve_cdk_to_lgd(self, cdk: str) -> int | None:
        """
        Resolve a text CDK (e.g. 'WB_24parg_1961') to an integer LGD code.

        Strategy:
        1. If CDK is already a pure integer string, return it directly.
        2. Check district_snapshots.district_cdk exact match → extract lgd_code if numeric.
        3. Parse state+name from CDK pattern (STATE_NAME_YEAR) and fuzzy-match in districts.
        4. Return None if unresolvable.
        """
        if cdk in self._cdk_to_lgd:
            return self._cdk_to_lgd[cdk]

        # Strategy 1: pure integer CDK
        if cdk.isdigit():
            lgd = int(cdk)
            self._cdk_to_lgd[cdk] = lgd
            return lgd

        # Strategy 2: district_snapshots may already map text CDK -> numeric district_cdk
        # Some snapshots use integer strings as district_cdk
        try:
            snap_cdk = await self.db.fetchval(
                """
                SELECT district_cdk FROM district_snapshots
                WHERE district_cdk = $1
                LIMIT 1
                """,
                cdk,
            )
            if snap_cdk and str(snap_cdk).isdigit():
                lgd = int(snap_cdk)
                self._cdk_to_lgd[cdk] = lgd
                return lgd
        except Exception:
            pass

        # Strategy 3: parse CDK format STATE_NAME_YEAR  → e.g. WB_24parg_1961 → name='24parg', state='West Bengal'
        lgd_result: int | None = await self._resolve_by_name_match(cdk)
        self._cdk_to_lgd[cdk] = lgd_result
        return lgd_result

    async def _resolve_by_name_match(self, cdk: str) -> int | None:
        """Parse text CDK and fuzzy-match against districts table to get lgd_code."""
        parts = cdk.split("_")
        if len(parts) < 2:
            return None

        state_code = parts[0].upper()
        # Name fragment is everything between state code and trailing year
        name_parts = parts[1:-1] if (len(parts) >= 3 and parts[-1].isdigit()) else parts[1:]
        name_fragment = " ".join(name_parts)

        state_name = STATE_CODE_MAP.get(state_code)

        try:
            if state_name:
                # Exact state + name fragment
                lgd = await self.db.fetchval(
                    """
                    SELECT lgd_code FROM districts
                    WHERE state_name ILIKE $1
                      AND district_name ILIKE $2
                    ORDER BY lgd_code ASC
                    LIMIT 1
                    """,
                    f"%{state_name}%",
                    f"%{name_fragment}%",
                )
                if lgd:
                    return int(lgd)

            # Broader name match without state filter
            lgd = await self.db.fetchval(
                """
                SELECT lgd_code FROM districts
                WHERE district_name ILIKE $1
                ORDER BY lgd_code ASC
                LIMIT 1
                """,
                f"%{name_fragment}%",
            )
            if lgd:
                return int(lgd)

        except Exception as e:
            logger.debug(f"Name match failed for CDK {cdk}: {e}")

        return None

    async def _resolve_cdks_to_lgds(self, cdks: list[str]) -> dict[str, int]:
        """Batch resolve text CDKs to integer LGD codes. Returns only successfully resolved ones."""
        result: dict[str, int] = {}
        for cdk in cdks:
            lgd = await self._resolve_cdk_to_lgd(cdk)
            if lgd is not None:
                result[cdk] = lgd
        return result

    # ------------------------------------------------------------------
    # Lineage graph building
    # ------------------------------------------------------------------

    async def _fetch_lineage_graph(self, base_cdk: str) -> LineageGraph:
        """Fetch native Postgres Recursive CTE graph for a specific root."""
        query = """
        WITH RECURSIVE lineage_tree AS (
            SELECT
                parent_cdk, child_cdks, split_year,
                ARRAY[parent_cdk] AS lineage_path,
                1 as generation
            FROM split_events
            WHERE parent_cdk = $1

            UNION ALL

            SELECT
                se.parent_cdk, se.child_cdks, se.split_year,
                lt.lineage_path || se.parent_cdk,
                lt.generation + 1
            FROM split_events se
            JOIN lineage_tree lt ON se.parent_cdk = ANY(lt.child_cdks)
            WHERE NOT se.parent_cdk = ANY(lt.lineage_path)
        )
        SELECT parent_cdk, child_cdks, split_year FROM lineage_tree;
        """
        events = await self.db.fetch(query, base_cdk)
        return LineageGraph.from_split_events([dict(r) for r in events])

    async def _get_split_graph(self, base_cdk: str) -> dict[str, list[tuple[list[str], int]]]:
        """Backward-compatible map extraction using the local CTE lineage graph."""
        graph = await self._fetch_lineage_graph(base_cdk)
        return graph.get_split_graph_compat()

    async def get_lineage_tree(
        self,
        root_cdk: str,
        graph: dict[str, list[tuple[list[str], int]]] | None = None,
    ) -> dict[str, Any]:
        """Returns the tree structure for the frontend without geometry or yields."""
        if graph is None:
            graph = await self._get_split_graph(root_cdk)

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
        # Strategy 1: Try district_snapshots (has text CDK column)
        try:
            name = await self.db.fetchval(
                "SELECT district_name FROM district_snapshots WHERE district_cdk = $1 LIMIT 1",
                cdk,
            )
            if name:
                return str(name)
        except Exception:
            pass

        # Strategy 2: Resolve via LGD then look up in districts
        lgd = await self._resolve_cdk_to_lgd(cdk)
        if lgd is not None:
            try:
                name = await self.db.fetchval(
                    "SELECT district_name FROM districts WHERE lgd_code = $1 LIMIT 1",
                    lgd,
                )
                if name:
                    return str(name)
            except Exception:
                pass

        # Fallback: parse from CDK string (e.g., WB_24parg_1961 → 24 Parganas)
        parts = cdk.split("_")
        if len(parts) >= 2:
            name_parts = parts[1:-1] if (len(parts) >= 3 and parts[-1].isdigit()) else parts[1:]
            return " ".join(name_parts).replace("-", " ").title()
        return cdk

    # ------------------------------------------------------------------
    # Data availability using LGD codes
    # ------------------------------------------------------------------

    async def _find_lgds_with_data(self, lgd_codes: list[int], crop: str) -> set[int]:
        """Check which LGD codes have rows in agri_metrics for this crop."""
        if not lgd_codes:
            return set()

        # Build candidate variable names including seasonal variants
        base_vars = [f"{crop}_production", f"{crop}_area"]
        seasonal_vars: list[str] = []
        for season in CROP_SEASON_MAP.get(crop.lower(), []):
            seasonal_vars.extend([f"{crop}_production_{season}", f"{crop}_area_{season}"])

        all_vars = base_vars + seasonal_vars

        try:
            rows = await self.db.fetch(
                """
                SELECT DISTINCT district_lgd
                FROM agri_metrics
                WHERE district_lgd = ANY($1::int[])
                  AND variable_name = ANY($2)
                """,
                lgd_codes,
                all_vars,
            )
            return {int(r["district_lgd"]) for r in rows}
        except Exception as e:
            logger.warning(f"LGD data check failed: {e}")
            return set()

    def _build_parent_map(self, graph: dict[str, list[tuple[list[str], int]]]) -> dict[str, str]:
        """Build child → parent mapping from the split graph."""
        parent_of: dict[str, str] = {}
        for parent, splits in graph.items():
            for children, _ in splits:
                for child in children:
                    parent_of[child] = parent
        return parent_of

    # Resolution status for each CDK
    CdkResolutionStatus = Literal["direct", "ancestor", "missing"]

    async def _resolve_data_lgds_v2(
        self,
        active_cdks: list[str],
        base_cdk: str,
        parent_map: dict[str, str],
        cdk_to_lgd: dict[str, int],
    ) -> dict[str, tuple[int | None, "ReconstructorService.CdkResolutionStatus"]]:
        """
        Resolve each active CDK to a data LGD code with status annotation.

        Returns:
            {active_cdk: (lgd_code, status)}
            - status='direct': CDK's own LGD has data
            - status='ancestor': using nearest ancestor's LGD
            - status='missing': no data found anywhere in lineage
        """
        result: dict[str, tuple[int | None, ReconstructorService.CdkResolutionStatus]] = {}

        # Get LGDs for all active CDKs
        active_lgds: list[int] = [cdk_to_lgd[c] for c in active_cdks if c in cdk_to_lgd]
        lgds_with_data = await self._find_lgds_with_data(active_lgds, "rice")  # placeholder, refined below

        for cdk in active_cdks:
            lgd = cdk_to_lgd.get(cdk)
            if lgd is not None and lgd in lgds_with_data:
                result[cdk] = (lgd, "direct")
            else:
                result[cdk] = (None, "missing")

        # For CDKs without data, walk up ancestors
        missing_cdks = [c for c, (_, s) in result.items() if s == "missing"]
        if missing_cdks:
            ancestor_candidates: set[str] = set()
            for cdk in missing_cdks:
                current = cdk
                while current in parent_map:
                    current = parent_map[current]
                    ancestor_candidates.add(current)
            ancestor_candidates.add(base_cdk)

            ancestor_lgd_map: dict[str, int] = {}
            for ac in ancestor_candidates:
                lgd = cdk_to_lgd.get(ac) or await self._resolve_cdk_to_lgd(ac)
                if lgd is not None:
                    ancestor_lgd_map[ac] = lgd

            anc_lgds_with_data = await self._find_lgds_with_data(
                list(ancestor_lgd_map.values()), "rice"
            )

            for cdk in missing_cdks:
                current = cdk
                found = False
                while current in parent_map:
                    current = parent_map[current]
                    lgd = ancestor_lgd_map.get(current)
                    if lgd is not None and lgd in anc_lgds_with_data:
                        result[cdk] = (lgd, "ancestor")
                        found = True
                        break
                if not found:
                    base_lgd = ancestor_lgd_map.get(base_cdk)
                    if base_lgd is not None and base_lgd in anc_lgds_with_data:
                        result[cdk] = (base_lgd, "ancestor")

        return result

    @staticmethod
    def _classify_data_quality(
        resolution_map: dict[str, tuple[Any, "ReconstructorService.CdkResolutionStatus"]],
    ) -> Literal["direct", "partial", "ancestor_fallback", "no_data"]:
        """Classify overall data quality from per-CDK resolution statuses."""
        statuses = [s for _, (_, s) in resolution_map.items()]
        if not statuses:
            return "no_data"
        if all(s == "direct" for s in statuses):
            return "direct"
        if all(s == "missing" for s in statuses):
            has_ancestor = any(lgd is not None for _, (lgd, _) in resolution_map.items())
            return "ancestor_fallback" if has_ancestor else "no_data"
        if any(s == "ancestor" for s in statuses) and not any(s == "direct" for s in statuses):
            return "ancestor_fallback"
        return "partial"

    # ------------------------------------------------------------------
    # Fetch metrics — uses integer LGD codes against agri_metrics
    # ------------------------------------------------------------------

    async def _fetch_metrics_for_lgds(
        self,
        lgd_codes: list[int],
        crop: str,
        year_start: int,
        year_end: int,
    ) -> dict[int, dict[int, dict[str, float]]]:
        """
        Fetch production + area for given LGD codes and year range.

        Returns: {lgd_code: {year: {variable_name: value}}}

        Tries base variable names first, then seasonal fallbacks.
        """
        if not lgd_codes:
            return {}

        metric_dict: dict[int, dict[int, dict[str, float]]] = {}

        # Build candidate variable sets (base + seasonal)
        base_prod = f"{crop}_production"
        base_area = f"{crop}_area"
        candidate_pairs: list[tuple[str, str]] = [(base_prod, base_area)]

        for season in CROP_SEASON_MAP.get(crop.lower(), []):
            candidate_pairs.append((f"{crop}_production_{season}", f"{crop}_area_{season}"))

        all_vars = list({v for pair in candidate_pairs for v in pair})

        try:
            rows = await self.db.fetch(
                """
                SELECT district_lgd, year, variable_name, value
                FROM agri_metrics
                WHERE district_lgd = ANY($1::int[])
                  AND variable_name = ANY($2)
                  AND year >= $3 AND year <= $4
                """,
                lgd_codes,
                all_vars,
                year_start,
                year_end,
            )

            for row in rows:
                lgd_key: int = int(row["district_lgd"])
                yr: int = int(row["year"])
                var: str = str(row["variable_name"])
                val: float = float(row["value"]) if row["value"] is not None else 0.0

                if lgd_key not in metric_dict:
                    metric_dict[lgd_key] = {}
                if yr not in metric_dict[lgd_key]:
                    metric_dict[lgd_key][yr] = {}
                metric_dict[lgd_key][yr][var] = val

        except Exception as e:
            logger.warning(f"Metrics fetch failed for LGDs {lgd_codes}: {e}")

        return metric_dict

    def _extract_prod_area(
        self,
        lgd_data: dict[str, float],
        crop: str,
    ) -> tuple[float | None, float | None]:
        """
        Extract (production, area) from a year's data dict for a given crop.
        Tries base variable names first, then seasonal fallbacks.
        """
        base_prod = f"{crop}_production"
        base_area = f"{crop}_area"

        # Try base
        prod = lgd_data.get(base_prod)
        area = lgd_data.get(base_area)
        if prod is not None and area is not None:
            return prod, area

        # Try seasonal variants
        for season in CROP_SEASON_MAP.get(crop.lower(), []):
            s_prod = lgd_data.get(f"{crop}_production_{season}")
            s_area = lgd_data.get(f"{crop}_area_{season}")
            if s_prod is not None and s_area is not None:
                return s_prod, s_area

        # Partial matches — try each independently
        if prod is None:
            for season in CROP_SEASON_MAP.get(crop.lower(), []):
                prod = lgd_data.get(f"{crop}_production_{season}")
                if prod is not None:
                    break
        if area is None:
            for season in CROP_SEASON_MAP.get(crop.lower(), []):
                area = lgd_data.get(f"{crop}_area_{season}")
                if area is not None:
                    break

        if prod is not None and area is not None:
            return prod, area

        return None, None

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
        2. Resolve all text CDKs -> integer LGD codes via districts table
        3. For each epoch, try PostGIS ST_Union for geometry
        4. For yield data, fetch from agri_metrics using LGD codes
        5. Aggregate yield, production, area across data LGDs
        """
        graph = await self._fetch_lineage_graph(base_cdk)

        # 1. Build standard non-overlapping epochs (using DAG)
        epochs = build_epochs_from_graph(base_cdk, graph, min_year=min_year)

        if not epochs:
            return {"root_cdk": base_cdk, "crop": crop, "epochs": []}

        # 2. Gather all CDKs that ever appear across epochs
        all_cdk_set: set[str] = set()
        for ep in epochs:
            all_cdk_set.update(ep.active_cdks)
        all_cdk_set.add(base_cdk)

        all_cdks_list = list(all_cdk_set)

        # 3. Resolve all text CDKs -> integer LGD codes
        cdk_to_lgd = await self._resolve_cdks_to_lgds(all_cdks_list)
        logger.info(
            f"CDK resolution for {base_cdk}: resolved {len(cdk_to_lgd)}/{len(all_cdks_list)} CDKs to LGD codes"
        )

        # 4. Build CDK → district name map for display
        cdk_name_map: dict[str, str] = {}
        for cdk in all_cdk_set:
            cdk_name_map[cdk] = await self._get_cdk_name(cdk)

        # 5. Build parent map for ancestor fallback
        split_graph = await self._get_split_graph(base_cdk)
        parent_map = self._build_parent_map(split_graph)

        # 6. Process each epoch
        epoch_results: list[dict[str, Any]] = []
        for ep_raw in epochs:
            ep = cast(Epoch, ep_raw)
            leaves = ep.leaf_cdks

            # --- Geometry ---
            geojson = None
            is_contiguous = True
            if leaves:
                try:
                    geom_row = await self.db.fetchrow(
                        """
                        WITH leaves AS (
                            SELECT geometry FROM district_snapshots
                            WHERE district_cdk = ANY($1) AND geometry IS NOT NULL
                        )
                        SELECT
                            ST_AsGeoJSON(ST_Union(geometry)) as geojson,
                            GeometryType(ST_Union(geometry)) as type
                        FROM leaves
                    """,
                        list(leaves),
                    )

                    if geom_row and geom_row["geojson"]:
                        geojson = json.loads(geom_row["geojson"])
                        is_contiguous = geom_row["type"] != "MULTIPOLYGON" if geom_row["type"] else True
                except Exception as geo_err:
                    logger.warning(f"Geometry lookup failed for epoch {ep.epoch_num}: {geo_err}")

            # --- Yield aggregation ---
            y_start: int = int(ep.year_start)
            y_end: int = int(ep.year_end) if ep.year_end is not None else 2024
            metrics_list: list[dict[str, Any]] = []

            active_cdks_list: list[str] = list(ep.active_cdks)
            num_active: int = len(active_cdks_list)

            # Resolve active CDKs for this epoch to LGDs
            epoch_cdk_to_lgd = {c: cdk_to_lgd[c] for c in active_cdks_list if c in cdk_to_lgd}

            # Determine which LGDs have data (direct)
            direct_lgds: set[int] = set()
            ancestor_lgd_map: dict[str, int] = {}  # cdk -> ancestor lgd for missing ones

            active_lgds = list(epoch_cdk_to_lgd.values())
            lgds_with_data = await self._find_lgds_with_data(active_lgds, crop)

            # Per-CDK resolution
            resolution_map: dict[str, tuple[int | None, str]] = {}
            for cdk in active_cdks_list:
                lgd = epoch_cdk_to_lgd.get(cdk)
                if lgd is not None and lgd in lgds_with_data:
                    resolution_map[cdk] = (lgd, "direct")
                    direct_lgds.add(lgd)
                else:
                    # Walk up ancestor chain
                    current = cdk
                    found = False
                    while current in parent_map:
                        current = parent_map[current]
                        anc_lgd = cdk_to_lgd.get(current) or await self._resolve_cdk_to_lgd(current)
                        if anc_lgd is not None:
                            anc_check = await self._find_lgds_with_data([anc_lgd], crop)
                            if anc_lgd in anc_check:
                                resolution_map[cdk] = (anc_lgd, "ancestor")
                                ancestor_lgd_map[cdk] = anc_lgd
                                found = True
                                break
                    if not found:
                        resolution_map[cdk] = (None, "missing")

            epoch_data_quality = self._classify_data_quality(resolution_map)  # type: ignore[arg-type]
            is_fallback = epoch_data_quality in ("ancestor_fallback", "partial")

            # Collect unique data LGDs for querying
            data_lgds_set: set[int] = set()
            for _, (lgd, _) in resolution_map.items():
                if lgd is not None:
                    data_lgds_set.add(lgd)
            data_lgds: list[int] = list(data_lgds_set)

            # Rebuild data_cdks as text for response schema
            lgd_to_cdk_rev: dict[int, str] = {v: k for k, v in cdk_to_lgd.items() if v is not None}
            data_cdks: list[str] = [lgd_to_cdk_rev.get(lgd, str(lgd)) for lgd in data_lgds]

            # Count direct vs ancestor
            direct_count = sum(1 for _, (_, s) in resolution_map.items() if s == "direct")
            ancestor_count = sum(1 for _, (_, s) in resolution_map.items() if s == "ancestor")

            # Fetch yield data from resolved LGD codes
            metric_by_lgd: dict[int, dict[int, dict[str, float]]] = {}
            if data_lgds:
                metric_by_lgd = await self._fetch_metrics_for_lgds(data_lgds, crop, y_start, y_end)

            data_years_count: int = 0
            epoch_span: int = max(y_end - y_start + 1, 1)

            for year in range(y_start, y_end + 1):
                total_prod: float = 0.0
                total_area: float = 0.0
                lgds_with_year_data: int = 0

                for lgd in data_lgds:
                    lgd_year_data = metric_by_lgd.get(lgd, {}).get(year, {})
                    p, a = self._extract_prod_area(lgd_year_data, crop)
                    if p is not None and a is not None and a > 0:
                        total_prod += p
                        total_area += a
                        lgds_with_year_data += 1

                coverage: float = float(lgds_with_year_data) / float(num_active) if num_active > 0 else 0.0
                yield_val: float | None = (
                    round((total_prod / total_area) * 1000.0, 2) if total_area > 0 else None
                )

                if lgds_with_year_data > 0:
                    data_years_count += 1

                # Per-year data quality
                if lgds_with_year_data == 0:
                    year_quality = "no_data"
                elif is_fallback:
                    year_quality = epoch_data_quality
                else:
                    year_quality = "direct" if lgds_with_year_data == num_active else "partial"

                metrics_list.append(
                    {
                        "year": year,
                        "data_coverage": round(coverage, 3),
                        "collective_yield": yield_val,
                        "collective_production": round(total_prod, 2) if lgds_with_year_data > 0 else None,
                        "collective_area": round(total_area, 2) if lgds_with_year_data > 0 else None,
                        "is_fallback": is_fallback,
                        "data_quality": year_quality,
                    }
                )

            # Epoch-level confidence score
            source_quality: float = 0.0
            if num_active > 0:
                source_quality = (direct_count * 1.0 + ancestor_count * 0.6) / num_active
            resolved_coverage: float = (direct_count + ancestor_count) / num_active if num_active > 0 else 0.0
            temporal_coverage: float = data_years_count / epoch_span if epoch_span > 0 else 0.0
            epoch_confidence: float = round(
                source_quality * 0.4 + resolved_coverage * 0.4 + temporal_coverage * 0.2,
                3,
            )

            active_names = [cdk_name_map.get(c, c) for c in ep.active_cdks]

            # Resolution details for transparency (using text CDK for API response)
            resolution_details: dict[str, dict[str, Any]] = {}
            for active_cdk, (lgd, status) in resolution_map.items():
                resolution_details[active_cdk] = {
                    "data_cdk": lgd_to_cdk_rev.get(lgd, str(lgd)) if lgd else None,
                    "status": status,
                }

            ep_data: dict[str, Any] = {
                "epoch_num": ep.epoch_num,
                "year_start": ep.year_start,
                "year_end": ep.year_end,
                "event_label": ep.event_label,
                "active_cdks": ep.active_cdks,
                "active_names": active_names,
                "data_cdks": data_cdks,
                "is_fallback": is_fallback,
                "data_quality": epoch_data_quality,
                "confidence_score": epoch_confidence,
                "cdk_resolution": resolution_details,
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
