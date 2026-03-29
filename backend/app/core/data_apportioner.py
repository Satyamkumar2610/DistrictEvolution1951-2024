"""
DataApportioner — distributes historical data across administrative splits.

Supports area-weighted, population-weighted, and crop-area-weighted modes.
Every apportionment is annotated with the method used, and conservation of
extensive properties (production, area) is validated post-hoc.
"""

import logging
from dataclasses import dataclass
from typing import Any, Literal

from app.core.lineage_graph import DistrictEvent, EventType, LineageGraph  # type: ignore

logger = logging.getLogger("app.core.data_apportioner")

ApportionMethod = Literal[
    "raw",
    "area_weighted",
    "population_weighted",
    "crop_area_weighted",
    "equal_split",
    "rename_passthrough",
    "exact_geometric",
]


@dataclass
class ApportionedValue:
    """Single data value with full provenance."""
    cdk: str
    year: int
    value: float
    method: ApportionMethod
    source_cdks: tuple[str, ...]
    coverage: float              # 0.0–1.0: proportion of area covered by data
    confidence: float = 1.0      # 0.0–1.0: confidence in the method used


@dataclass
class ConservationResult:
    """Result of a conservation check comparing pre- and post-event totals."""
    is_valid: bool
    before_total: float
    after_total: float
    absolute_error: float
    relative_error: float
    tolerance: float


class DataApportioner:
    """
    Distributes metric values across administrative boundary changes.

    Core invariant for extensive properties (area, production):
        sum(after_values) ≈ sum(before_values)  within tolerance

    For intensive properties (yield):
        area_weighted_average(after_yields) ≈ before_yield
    """

    def __init__(self, tolerance: float = 0.01) -> None:
        self.tolerance = tolerance

    # ------------------------------------------------------------------
    # Single-hop apportionment
    # ------------------------------------------------------------------

    def apportion_to_modern(
        self,
        historical_data: dict[str, float],
        event: DistrictEvent,
        mode: ApportionMethod = "area_weighted",
        area_ratios: dict[str, float] | None = None,
        population_ratios: dict[str, float] | None = None,
    ) -> dict[str, ApportionedValue]:
        """
        Redistribute values from source_cdks to target_cdks across one event.

        Args:
            historical_data: {cdk: value} for source districts
            event: the administrative event to apportion across
            mode: apportionment strategy
            area_ratios: {target_cdk: proportion} from geometry intersection
            population_ratios: {target_cdk: proportion} from census data

        Returns:
            {target_cdk: ApportionedValue}
        """
        results: dict[str, ApportionedValue] = {}
        total_source = sum(
            historical_data.get(src, 0.0) for src in event.source_cdks
        )

        # --- Handle renames (1:1 passthrough) ---
        if event.event_type == EventType.RENAME and len(event.source_cdks) == 1 and len(event.target_cdks) == 1:
            src = event.source_cdks[0]
            tgt = event.target_cdks[0]
            val = historical_data.get(src, 0.0)
            results[tgt] = ApportionedValue(
                cdk=tgt, year=event.year, value=val,
                method="rename_passthrough",
                source_cdks=event.source_cdks,
                coverage=1.0, confidence=1.0,
            )
            return results

        # --- Determine weights ---
        weights = self._compute_weights(
            event, mode, area_ratios, population_ratios
        )

        # --- Apply weights ---
        for tgt in event.target_cdks:
            w: float = weights.get(tgt, 0.0)
            apportioned_val: float = float(total_source) * w

            actual_method: ApportionMethod = mode
            if area_ratios is not None and mode == "area_weighted":
                actual_method = "exact_geometric" if str(tgt) in area_ratios else "area_weighted"  # type: ignore[operator]

            results[tgt] = ApportionedValue(
                cdk=tgt, year=event.year, value=apportioned_val,
                method=actual_method,
                source_cdks=event.source_cdks,
                coverage=w,
                confidence=self._method_confidence(actual_method),
            )

        return results

    def _compute_weights(
        self,
        event: DistrictEvent,
        mode: ApportionMethod,
        area_ratios: dict[str, float] | None,
        population_ratios: dict[str, float] | None,
    ) -> dict[str, float]:
        """
        Determine per-target weights based on available data.

        Priority order:
        1. exact_geometric (area_transfers with ST_Intersection)
        2. population_weighted (census data)
        3. area_weighted (from provided ratios)
        4. equal_split (fallback)
        """
        # Use event-level area_ratios if available and mode matches
        if event.area_ratios:
            return event.area_ratios

        if area_ratios and mode in ("area_weighted", "exact_geometric"):
            total = sum(area_ratios.values())
            if total > 0:
                return {k: v / total for k, v in area_ratios.items()}

        if population_ratios and mode == "population_weighted":
            total = sum(population_ratios.values())
            if total > 0:
                return {k: v / total for k, v in population_ratios.items()}

        # Fallback: equal split
        n = len(event.target_cdks)
        if n > 0:
            return {tgt: 1.0 / n for tgt in event.target_cdks}
        return {}

    def _method_confidence(self, method: ApportionMethod) -> float:
        """Confidence score for each apportionment method."""
        return {
            "exact_geometric": 0.95,
            "population_weighted": 0.85,
            "crop_area_weighted": 0.80,
            "area_weighted": 0.70,
            "equal_split": 0.40,
            "rename_passthrough": 1.00,
            "raw": 1.00,
        }.get(method, 0.50)

    # ------------------------------------------------------------------
    # Multi-hop cascading apportionment
    # ------------------------------------------------------------------

    def apportion_cascade(
        self,
        root_cdk: str,
        data: dict[int, float],
        graph: LineageGraph,
        mode: ApportionMethod = "area_weighted",
    ) -> dict[str, dict[int, float]]:
        """
        Cascade data from a root district through all downstream splits.

        For each year of data, walk the lineage graph and apportion
        through every event that happened AFTER that year.

        Args:
            root_cdk: the historical district CDK
            data: {year: value} historical data for root
            graph: the full lineage graph
            mode: apportionment strategy

        Returns:
            {modern_cdk: {year: apportioned_value}}
        """
        result: dict[str, dict[int, float]] = {}
        subtree_events = graph.get_subtree_events(root_cdk)

        for year, value in data.items():
            # Find events that happened AFTER this data year
            relevant_events = [e for e in subtree_events if e.year > year]

            if not relevant_events:
                # No splits after this year — data stays with root
                if root_cdk not in result:
                    result[root_cdk] = {}
                result[root_cdk][year] = value
                continue

            # Walk through events chronologically, apportioning at each step
            # current_values: {cdk: value}
            current_values: dict[str, float] = {root_cdk: value}

            for event in sorted(relevant_events, key=lambda e: e.year):
                new_values: dict[str, float] = {}
                for src in event.source_cdks:
                    if src in current_values:
                        src_val: float = current_values[src]  # type: ignore[index]
                        src_data: dict[str, float] = {str(src): src_val}
                        apportioned = self.apportion_to_modern(
                            src_data, event, mode
                        )
                        for tgt, av in apportioned.items():
                            new_values[tgt] = new_values.get(tgt, 0.0) + av.value
                        current_values.pop(str(src))

                # Merge: districts not involved in this event carry forward
                current_values.update(new_values)

            # Store final distribution
            for cdk_key, cdk_val in current_values.items():
                if cdk_key not in result:
                    result[cdk_key] = {}
                result[cdk_key][year] = cdk_val  # type: ignore[index]

        return result

    # ------------------------------------------------------------------
    # Conservation validation
    # ------------------------------------------------------------------

    def validate_conservation(
        self,
        before: dict[str, float],
        after: dict[str, float],
        tolerance: float | None = None,
    ) -> ConservationResult:
        """
        Assert that totals are preserved within tolerance.

        For extensive properties (area, production):
            sum(before) ≈ sum(after)

        Returns a ConservationResult with diagnostics.
        """
        tol = tolerance if tolerance is not None else self.tolerance
        before_total = sum(before.values())
        after_total = sum(after.values())
        absolute_error = abs(after_total - before_total)
        relative_error = (
            absolute_error / before_total if before_total > 0 else 0.0
        )
        is_valid = relative_error <= tol

        if not is_valid:
            logger.warning(
                f"Conservation violation: before={before_total:.4f}, "
                f"after={after_total:.4f}, error={relative_error:.4%} "
                f"(tolerance={tol:.4%})"
            )

        return ConservationResult(
            is_valid=is_valid,
            before_total=before_total,
            after_total=after_total,
            absolute_error=absolute_error,
            relative_error=relative_error,
            tolerance=tol,
        )

    # ------------------------------------------------------------------
    # Collective yield aggregation (replaces inline logic in service)
    # ------------------------------------------------------------------

    def aggregate_collective_yield(
        self,
        district_data: dict[str, dict[str, float]],
        active_cdks: list[str],
        crop: str,
    ) -> dict[str, Any]:
        """
        Compute collective yield from multiple district data dicts.

        Args:
            district_data: {cdk: {"production": val, "area": val}}
            active_cdks: list of CDKs that SHOULD have data
            crop: crop name (for variable naming)

        Returns:
            {"yield": float|None, "production": float|None, "area": float|None,
             "coverage": float, "method": str}
        """
        total_prod: float = 0.0
        total_area: float = 0.0
        cdks_with_data: int = 0

        for cdk in active_cdks:
            cdk_d = district_data.get(cdk, {})
            prod = cdk_d.get("production") or cdk_d.get(f"{crop}_production")
            area = cdk_d.get("area") or cdk_d.get(f"{crop}_area")
            if prod is not None and area is not None:
                total_prod = total_prod + float(prod)  # type: ignore[operator]
                total_area = total_area + float(area)  # type: ignore[operator]
                cdks_with_data = cdks_with_data + 1  # type: ignore[operator]

        coverage: float = (
            float(cdks_with_data) / len(active_cdks)
            if active_cdks else 0.0
        )
        yield_val: float | None = (
            float(int((total_prod / total_area) * 1000.0 * 100)) / 100.0  # type: ignore[operator]
            if total_area > 0.0 else None
        )

        result: dict[str, Any] = {
            "yield": yield_val,
            "production": float(int(total_prod * 100)) / 100.0 if cdks_with_data > 0 else None,  # type: ignore[operator]
            "area": float(int(total_area * 100)) / 100.0 if cdks_with_data > 0 else None,  # type: ignore[operator]
            "coverage": float(int(coverage * 1000)) / 1000.0,
            "method": "area_weighted" if cdks_with_data > 0 else "none",
        }
        return result

    def compute_epoch_confidence(
        self,
        total_active: int,
        direct_count: int,
        fallback_count: int,
        data_years: int,
        epoch_span: int,
    ) -> float:
        """
        Compute a 0.0–1.0 confidence score for an epoch.

        Formula:
          source_quality (40%):  direct=1.0, fallback=0.6, missing=0.0
          coverage (40%):        resolved CDKs / active CDKs
          temporal (20%):        years with data / epoch span
        """
        if total_active == 0:
            return 0.0

        missing_count = total_active - direct_count - fallback_count
        source_quality = (
            direct_count * 1.0
            + fallback_count * 0.6
            + missing_count * 0.0
        ) / total_active

        resolved_coverage = (direct_count + fallback_count) / total_active
        temporal_coverage = data_years / epoch_span if epoch_span > 0 else 0.0

        confidence = (
            source_quality * 0.4
            + resolved_coverage * 0.4
            + temporal_coverage * 0.2
        )
        return round(min(1.0, max(0.0, confidence)), 3)  # type: ignore[call-overload]
