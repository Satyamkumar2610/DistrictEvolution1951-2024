"""
Analysis Service: Orchestrates split impact analysis.
Coordinates between repositories and analytics engine.
"""

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import asyncpg

from app.analytics.harmonizer import BoundaryHarmonizer
from app.analytics.impact_analyzer import ImpactAnalyzer
from app.analytics.split_impact_insights import get_insights_analyzer
from app.analytics.uncertainty import calculate_impact_uncertainty
from app.cache import CacheTTL, cached
from app.config import get_settings
from app.repositories.district_repo import DistrictRepository
from app.repositories.lineage_repo import LineageRepository
from app.repositories.metric_repo import MetricRepository
from app.repositories.split_repo import SplitRepository
from app.schemas.analysis import (
    AdvancedStats,
    AnalysisMeta,
    AnalysisMode,
    ChildPerformanceInfo,
    ConvergenceInfo,
    CounterfactualInfo,
    DivergenceInfo,
    EffectSizeInfo,
    FragmentationInfo,
    SeriesMeta,
    SplitImpactDistrictSummary,
    SplitImpactResponse,
    SplitInsightsInfo,
    StateSummary,
    SummaryResponse,
)
from app.schemas.common import ProvenanceMetadata
from app.schemas.lineage import SplitEventSummary

settings = get_settings()


class AnalysisService:
    """
    Service for split impact analysis.
    Orchestrates data fetching, harmonization, and statistical analysis.
    """

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn
        self.district_repo = DistrictRepository(conn)
        self.metric_repo = MetricRepository(conn)
        self.lineage_repo = LineageRepository(conn)
        self.split_repo = SplitRepository(conn)
        self.harmonizer = BoundaryHarmonizer()
        self.impact_analyzer = ImpactAnalyzer()
        self.insights_analyzer = get_insights_analyzer()

    async def get_split_summary(self) -> SummaryResponse:
        """Get split-impact summary stats for all states."""
        states = await self.split_repo.get_state_district_counts()
        split_counts = await self.split_repo.get_boundary_change_counts()

        state_list: list[str] = []
        stats: dict[str, StateSummary] = {}

        for row in states:
            state = str(row["state_name"])
            total_districts = int(row["total_districts"])
            changes = split_counts.get(state.strip().upper(), 0)

            state_list.append(state)
            stats[state] = StateSummary(
                state=state,
                total=total_districts,
                total_districts=total_districts,
                changed=changes,
                boundary_changes=changes,
                coverage=100,
                data_coverage="High",
                comparability="Active" if changes > 0 else "N/A",
            )

        return SummaryResponse(states=state_list, stats=stats)

    async def get_resolved_split_events_for_state(
        self,
        state: str,
    ) -> list[SplitImpactDistrictSummary]:
        """Get split events for a state with LGD resolution and agri coverage flags."""
        from app.services.name_resolver import resolve_lgd

        rows = await self.split_repo.get_split_rows_for_state(state)
        if not rows:
            return []

        has_nulls = any(row["parent_lgd"] is None or row["child_lgd"] is None for row in rows)
        lgd_lookup = await self.district_repo.get_lgd_lookup() if has_nulls else {}

        cdk_set: set[int | str] = set()
        for row in rows:
            p_cdk = row.get("parent_cdk_real") or row.get("parent_lgd")
            c_cdk = row.get("child_cdk_real") or row.get("child_lgd")
            if p_cdk is not None:
                cdk_set.add(p_cdk)
            if c_cdk is not None:
                cdk_set.add(c_cdk)

        agri_lgds = await self.split_repo.get_agri_lgds(list(cdk_set))
        groups: dict[tuple[str, int], dict[str, Any]] = defaultdict(
            lambda: {
                "parent_district": "",
                "parent_cdk": None,
                "split_year": 0,
                "state": "",
                "children_districts": [],
                "children_cdks": [],
                "children_has_agri": [],
            }
        )

        for row in rows:
            parent_district = str(row["parent_district"])
            raw_split_year = row["split_year"]
            if raw_split_year is None:
                continue
            split_year = raw_split_year if isinstance(raw_split_year, int) else int(str(raw_split_year))
            state_name = str(row["state_name"])
            key = (parent_district, split_year)

            group = groups[key]
            group["parent_district"] = parent_district
            group["split_year"] = split_year
            group["state"] = state_name

            parent_lgd = row.get("parent_cdk_real") or row.get("parent_lgd")
            if parent_lgd is None and lgd_lookup:
                parent_lgd = resolve_lgd(parent_district, state_name, lgd_lookup)
            group["parent_cdk"] = str(parent_lgd) if parent_lgd is not None else None

            child_name = str(row["child_district"])
            child_lgd = row.get("child_cdk_real") or row.get("child_lgd")
            if child_lgd is None and lgd_lookup:
                child_lgd = resolve_lgd(child_name, state_name, lgd_lookup)
            child_cdk = str(child_lgd) if child_lgd is not None else None

            if child_name not in group["children_districts"]:
                group["children_districts"].append(child_name)
                group["children_cdks"].append(child_cdk)
                
                # Check against agri_lgds
                has_agri = False
                if child_cdk is not None:
                    # agri_lgds may contain strings or ints depending on schema
                    has_agri = child_cdk in agri_lgds or (child_cdk.isdigit() and int(child_cdk) in agri_lgds)
                group["children_has_agri"].append(has_agri)

        results: list[SplitImpactDistrictSummary] = []
        for (parent, year), group in sorted(groups.items(), key=lambda item: -item[0][1]):
            parent_cdk = group["parent_cdk"]
            parent_has_agri = False
            if parent_cdk is not None:
                parent_has_agri = parent_cdk in agri_lgds or (parent_cdk.isdigit() and int(parent_cdk) in agri_lgds)
                
            children_cdks = group["children_cdks"]
            results.append(
                SplitImpactDistrictSummary(
                    id=f"{parent}_{year}",
                    parent_district=group["parent_district"],
                    parent_name=group["parent_district"],
                    parent_cdk=group["parent_cdk"],
                    split_year=group["split_year"],
                    children_districts=group["children_districts"],
                    children_names=group["children_districts"],
                    children_cdks=children_cdks,
                    state=group["state"],
                    resolved_count=sum(1 for child in children_cdks if child is not None),
                    total_count=len(children_cdks),
                    parent_has_agri=parent_has_agri,
                    children_has_agri=group["children_has_agri"],
                )
            )

        return results

    @cached(ttl=CacheTTL.SUMMARY, prefix="state_summary")
    async def get_state_summary(self) -> dict[str, Any]:
        """Get summary statistics for all states."""
        states = await self.district_repo.get_states()
        counts = await self.district_repo.count_by_state()
        cdk_to_state = {cdk: meta["state"] for cdk, meta in (await self.district_repo.get_cdk_to_meta_map()).items()}

        # Count boundary changes per state from lineage
        events = await self.lineage_repo.get_all_events()
        state_changes: dict[str, set] = {}

        for e in events:
            state = cdk_to_state.get(e.parent_cdk)
            if state:
                if state not in state_changes:
                    state_changes[state] = set()
                state_changes[state].add(e.parent_cdk)

        stats = {}
        for state in states:
            state_str = str(state)
            stats[state_str] = {
                "state": state_str,
                "total_districts": counts.get(state_str, 0),
                "boundary_changes": len(state_changes.get(state_str, set())),
                "data_coverage": "High",
                "comparability": "Active" if len(state_changes.get(state_str, set())) > 0 else "N/A",
            }

        return {"states": states, "stats": stats}

    @cached(ttl=CacheTTL.SPLIT_EVENTS, prefix="split_events")
    async def get_split_events_for_state(self, state: str) -> list[SplitEventSummary]:
        """Get all split events for a state."""
        cdk_meta = await self.district_repo.get_cdk_to_meta_map()
        cdk_to_state = {cdk: meta["state"] for cdk, meta in cdk_meta.items()}

        events = await self.lineage_repo.get_events_by_state(state, cdk_to_state)
        groups = self.lineage_repo.group_by_parent_year(events)

        results = []
        for _key, group in groups.items():
            parent_name = cdk_meta.get(group["parent_cdk"], {}).get("name", group["parent_cdk"])
            children_list = list(group["children"])
            children_names = [cdk_meta.get(c, {}).get("name", c) for c in children_list]

            results.append(
                SplitEventSummary(
                    id=f"{group['parent_cdk']}_{group['event_year']}",
                    parent_cdk=group["parent_cdk"],
                    parent_name=parent_name,
                    split_year=group["event_year"],
                    children_cdks=children_list,
                    children_names=children_names,
                    children_count=len(children_list),
                    coverage="High",
                )
            )

        # Sort by year descending
        results.sort(key=lambda x: x.split_year, reverse=True)
        return results

    @cached(ttl=CacheTTL.ANALYSIS, prefix="impact_analysis")
    async def analyze_split_impact(
        self,
        parent_cdk: str,
        children_cdks: list[str],
        split_year: int,
        domain: str,
        variable: str,
        mode: str,
        query_hash: str,
    ) -> SplitImpactResponse:
        """
        Perform complete split impact analysis.

        Args:
            parent_cdk: Parent district CDK
            children_cdks: List of child CDKs
            split_year: Year of split
            domain: Metric domain (agriculture, climate, etc.)
            variable: Variable to analyze (e.g., wheat_yield)
            mode: Analysis mode (before_after or entity_comparison)
            query_hash: Hash of query params for provenance

        Returns:
            SplitImpactResponse with timeline, stats, and provenance
        """
        # Determine metric type from variable name
        metric_type = variable.split("_")[-1] if "_" in variable else "yield"

        # Build variable list for query
        # Handle cases like "rice_yield_kharif" vs "rice_yield"
        parts = variable.split("_")
        if len(parts) >= 3 and parts[-1] in ["kharif", "rabi", "zaid"]:
            # Already has season
            base = "_".join(parts[:-2])
            suffix = f"_{parts[-1]}"
            metric_type = parts[-2]
        else:
            base = variable.rsplit("_", 1)[0] if "_" in variable else variable
            suffix = ""

        variables = [f"{base}_area{suffix}", f"{base}_production{suffix}", f"{base}_yield{suffix}"]

        # Fetch data
        all_cdks = [parent_cdk] + children_cdks
        data_map = await self.metric_repo.build_data_map(all_cdks, variables)

        # Also fetch seasonal data and merge it (crops often have both base and seasonal variables)
        # This handles cases where parent has base variables (rice_yield) but
        # children have seasonal (rice_yield_kharif)
        if not suffix:
            season_map = {
                "rice": "kharif",
                "wheat": "rabi",
                "maize": "kharif",
                "soyabean": "kharif",
                "groundnut": "kharif",
                "cotton": "kharif",
                "pearl_millet": "kharif",
                "sorghum": "kharif",
                "chickpea": "rabi",
            }
            # Extract crop name from base (e.g. "rice" from "rice")
            crop_name = base.split("_")[0]
            season = season_map.get(crop_name)

            if season:
                seasonal_suffix = f"_{season}"
                seasonal_variables = [
                    f"{base}_area{seasonal_suffix}",
                    f"{base}_production{seasonal_suffix}",
                    f"{base}_yield{seasonal_suffix}",
                ]
                seasonal_data_map = await self.metric_repo.build_data_map(all_cdks, seasonal_variables)

                # Merge seasonal data into main data_map (seasonal data takes
                # precedence for same year/cdk)
                for year, cdk_data in seasonal_data_map.items():
                    if year not in data_map:
                        data_map[year] = {}
                    for cdk, values in cdk_data.items():
                        if cdk not in data_map[year]:
                            data_map[year][cdk] = values
                        else:
                            # Merge values: prefer seasonal if available
                            for key in ["area", "prod", "yld"]:
                                if values.get(key, 0) > 0:
                                    data_map[year][cdk][key] = values[key]

                # If we got more data from seasonal, update variable name for
                # metadata
                if seasonal_data_map:
                    variable = f"{variable}{seasonal_suffix}"

        timeline = []
        series_meta = []
        advanced_stats = None
        warnings = []

        if mode == "before_after":
            # Longitudinal reconstruction
            series_meta.append(
                SeriesMeta(
                    id="value",
                    label="Boundary Adjusted District",
                    style="solid",
                )
            )

            years = sorted(data_map.keys())

            # Use BoundaryHarmonizer for reconstruction
            # 1. Get pre-split parent data
            metric_literal = metric_type if metric_type in ("area", "production", "yield") else "yield"
            parent_series = self.harmonizer.get_parent_series(
                data_map,
                parent_cdk,
                metric_literal,  # type: ignore[arg-type]
            )

            # 2. Reconstruct post-split data from children
            # IMPORTANT: Only use post-split data for reconstruction
            # Children did not exist before split_year, any pre-split data is
            # invalid
            post_split_data = {year: data for year, data in data_map.items() if year >= split_year}
            reconstructed_series = self.harmonizer.reconstruct_parent_from_children(
                post_split_data,
                children_cdks,
                metric_literal,  # type: ignore[arg-type]
            )

            # 3. Merge into single timeline
            harmonized_points = self.harmonizer.merge_series(parent_series, reconstructed_series, split_year)

            # Convert to dictionary format expected by frontend
            timeline = [{"year": p.year, "value": round(p.value, 2)} for p in harmonized_points]

            # Calculate advanced statistics
            if timeline:
                pre_values = [p["value"] for p in timeline if p["year"] < split_year]
                post_values = [p["value"] for p in timeline if p["year"] >= split_year]

                if pre_values and post_values:
                    result = self.impact_analyzer.analyze_from_values(pre_values, post_values, split_year)

                    # Calculate uncertainty
                    uncertainty = calculate_impact_uncertainty(pre_values, post_values)
                    result.impact.uncertainty = uncertainty

                    # ============================================================
                    # NEW: Compute Split Impact Insights
                    # ============================================================

                    # Get pre/post years for counterfactual projection
                    pre_years = [p["year"] for p in timeline if p["year"] < split_year]

                    # Compute children's mean yields for divergence analysis
                    children_mean_yields: dict[str, list[float]] = {}
                    yearly_children_yields: dict[int, dict[str, float]] = {}  # For convergence trend

                    for year, year_data in data_map.items():
                        if year >= split_year:
                            if year not in yearly_children_yields:
                                yearly_children_yields[year] = {}
                            for cdk in children_cdks:
                                if cdk in year_data and year_data[cdk].get("yld", 0) > 0:
                                    yld = year_data[cdk]["yld"]
                                    yearly_children_yields[year][cdk] = yld
                                    if cdk not in children_mean_yields:
                                        children_mean_yields[cdk] = []
                                    children_mean_yields[cdk].append(yld)

                    # Calculate mean yields per child
                    children_means = {
                        cdk: sum(vals) / len(vals) if vals else 0 for cdk, vals in children_mean_yields.items()
                    }

                    # Compute insights
                    fragmentation = self.insights_analyzer.calculate_fragmentation(len(children_cdks))
                    divergence = self.insights_analyzer.calculate_divergence(children_means)
                    convergence = self.insights_analyzer.calculate_convergence_trend(yearly_children_yields, split_year)
                    effect_size = self.insights_analyzer.calculate_effect_size(pre_values, post_values)
                    counterfactual = self.insights_analyzer.calculate_counterfactual(
                        pre_values, [int(y) for y in pre_years], result.post_stats.mean, split_year + 5
                    )

                    # Analyze child performance
                    children_performance = self.insights_analyzer.analyze_child_performance(
                        data_map, children_cdks, None, split_year
                    )

                    # Build insights schema objects
                    insights = SplitInsightsInfo(
                        fragmentation=FragmentationInfo(
                            index=fragmentation.index,
                            child_count=fragmentation.child_count,
                            interpretation=fragmentation.interpretation,
                        ),
                        divergence=DivergenceInfo(
                            score=divergence.score,
                            interpretation=divergence.interpretation,
                            best_performer=divergence.best_performer,
                            best_yield=divergence.best_yield,
                            worst_performer=divergence.worst_performer,
                            worst_yield=divergence.worst_yield,
                            spread=divergence.spread,
                        ),
                        convergence=ConvergenceInfo(
                            trend=convergence.trend, rate=convergence.rate, interpretation=convergence.interpretation
                        ),
                        effect_size=EffectSizeInfo(
                            cohens_d=effect_size.cohens_d,
                            interpretation=effect_size.interpretation,
                            confidence=effect_size.confidence,
                        ),
                        counterfactual=CounterfactualInfo(
                            projected_yield=counterfactual.projected_yield,
                            method=counterfactual.method,
                            actual_yield=counterfactual.actual_yield,
                            attribution_pct=counterfactual.attribution_pct,
                            interpretation=counterfactual.interpretation,
                        ),
                        children_performance=[
                            ChildPerformanceInfo(
                                cdk=cp.cdk,
                                name=cp.name,
                                mean_yield=cp.mean_yield,
                                cv=cp.cv,
                                cagr=cp.cagr,
                                observations=cp.observations,
                                rank=cp.rank,
                            )
                            for cp in children_performance
                        ],
                        warnings=[],
                    )

                    advanced_stats = AdvancedStats(
                        pre=result.pre_stats,
                        post=result.post_stats,
                        impact=result.impact,
                        insights=insights,
                    )

                    warnings.extend(result.warnings)

        else:
            # Entity comparison mode
            series_meta.append(SeriesMeta(id="parent", label=f"Parent ({parent_cdk})", style="solid"))
            for cdk in children_cdks:
                series_meta.append(SeriesMeta(id=cdk, label=f"Child ({cdk})", style="dashed"))

            years = sorted(data_map.keys())

            for year in years:
                year_data = data_map[year]
                row = {"year": year}

                # Parent value - show for all years (parent existed before
                # split)
                if parent_cdk in year_data:
                    d = year_data[parent_cdk]
                    val = d.get("yld") if metric_type == "yield" else d.get(metric_type[:4], 0)
                    if val:
                        row["parent"] = round(val, 2)

                # Children values
                for cdk in children_cdks:
                    if cdk in year_data:
                        d = year_data[cdk]
                        val = d.get("yld") if metric_type == "yield" else d.get(metric_type[:4], 0)
                        if val:
                            row[cdk] = round(val, 2)

                if len(row) > 1:
                    timeline.append(row)

        # Fetch district metadata for labels
        cdk_map = await self.district_repo.get_cdk_to_meta_map()

        parent_name = cdk_map.get(str(parent_cdk), {}).get("name", f"Parent ({parent_cdk})")

        # Build response
        meta = AnalysisMeta(
            split_year=split_year,
            mode=AnalysisMode(mode),
            metric=metric_type,
            variable=variable,
            parent_cdk=parent_cdk,
            children_cdks=children_cdks,
        )

        provenance = ProvenanceMetadata(
            dataset_version=settings.dataset_version,
            boundary_version=settings.boundary_version,
            query_hash=query_hash,
            generated_at=datetime.now(UTC),
            harmonization_method="area_weighted" if mode == "before_after" else None,
            warnings=warnings,
        )

        # update series labels with names
        for series in series_meta:
            if series.id == "value":
                # Keep "Boundary Adjusted District" for the reconstructed line
                continue
            elif series.id == "parent":
                series.label = f"{parent_name} ({parent_cdk})"
            elif series.id in children_cdks:
                child_name = cdk_map.get(str(series.id), {}).get("name", f"Child ({series.id})")
                series.label = f"{child_name} ({series.id})"

        return SplitImpactResponse(
            data=timeline,
            series=series_meta,
            advanced_stats=advanced_stats,
            meta=meta,
            provenance=provenance,
        )
