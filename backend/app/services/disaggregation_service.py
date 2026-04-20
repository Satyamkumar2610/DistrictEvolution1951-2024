"""
Counterfactual district disaggregation service.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import asyncpg

from app.exceptions import NotFoundError
from app.ml.yield_backcaster import YieldBackcaster
from app.repositories.disaggregation_repo import DisaggregationRepository
from app.schemas.disaggregation import (
    ChildSeriesEstimate,
    DisaggregationEventDetail,
    DisaggregationEventListResponse,
    DisaggregationEventSummary,
    DisaggregationSeriesResponse,
    DisaggregationSource,
    EstimatePoint,
    ParentSeries,
    SplitEventWeight,
)
from app.services.disaggregation_artifacts import (
    DEFAULT_PANEL_PATH,
    DEFAULT_PACKET_PATH,
    DEFAULT_WEIGHT_PATH,
    load_packets,
    load_panel_index,
    load_weights,
    panel_metric_value,
)

_SOURCE_CONFIDENCE = {
    "official": 0.95,
    "official_compiled": 0.8,
    "official_unverified": 0.7,
    "secondary_compiled": 0.55,
    "heuristic": 0.4,
    "unknown": 0.3,
}
_HARMONIZATION_CONFIDENCE = {
    "Raw": 1.0,
    "SplitInherited": 0.85,
    "Backcast": 0.6,
}
_METHODOLOGY_NOTE = (
    "Lineage certainty reflects confidence in the parent-child administrative event. "
    "Weight certainty reflects how confidently parent totals can be distributed across children. "
    "Model certainty reflects confidence in harmonized panel or yield backcast estimates. "
    "Public confidence uses the minimum of those three signals."
)


class DisaggregationService:
    """Service for packet discovery and counterfactual child series generation."""

    def __init__(
        self,
        conn: asyncpg.Connection | None = None,
        packet_path: Path = DEFAULT_PACKET_PATH,
        weight_path: Path = DEFAULT_WEIGHT_PATH,
        panel_path: Path = DEFAULT_PANEL_PATH,
    ):
        self.conn = conn
        self.repo = DisaggregationRepository(conn) if conn is not None else None
        self.packet_path = Path(packet_path)
        self.weight_path = Path(weight_path)
        self.panel_path = Path(panel_path)

    def _packet_rows(self) -> dict[str, dict[str, Any]]:
        return load_packets(str(self.packet_path))

    def _weight_rows(self) -> dict[str, list[dict[str, Any]]]:
        return load_weights(str(self.weight_path))

    def _panel_index(self) -> dict[str, dict[int, dict[str, Any]]]:
        return load_panel_index(str(self.panel_path))

    def _source_confidence(self, source_quality: str) -> float:
        return _SOURCE_CONFIDENCE.get(source_quality, 0.3)

    def _method_confidence(self, harmonization_method: str) -> float:
        if harmonization_method == "Raw":
            return 1.0
        if harmonization_method.startswith("Backcast_from_"):
            return 0.6
        return _HARMONIZATION_CONFIDENCE.get(harmonization_method, 0.75)

    def _bounds(self, value: float, confidence: float) -> tuple[float, float]:
        spread = max(0.05, 1.0 - confidence)
        lower = max(0.0, value * (1.0 - spread))
        upper = value * (1.0 + spread)
        return round(lower, 4), round(upper, 4)

    def _packets_from_artifacts(self) -> list[dict[str, Any]]:
        return list(self._packet_rows().values())

    async def _list_packet_dicts(self, state: str | None, readiness_tier: str | None) -> list[dict[str, Any]]:
        packets: list[dict[str, Any]] = []
        if self.repo is not None:
            packets = await self.repo.list_packets(state=state, readiness_tier=readiness_tier)
        if not packets:
            packets = self._packets_from_artifacts()
            if state:
                packets = [packet for packet in packets if packet.get("state") == state]
            if readiness_tier:
                packets = [packet for packet in packets if packet.get("readiness_tier") == readiness_tier]
        return packets

    async def _get_packet_dict(self, event_id: str) -> dict[str, Any]:
        packet: dict[str, Any] | None = None
        if self.repo is not None:
            packet = await self.repo.get_packet(event_id)
        if packet is None:
            packet = self._packet_rows().get(event_id)
        if packet is None:
            raise NotFoundError("Disaggregation event", event_id)
        return packet

    async def _get_source_dicts(self, event_id: str, packet: dict[str, Any]) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        if self.repo is not None:
            sources = await self.repo.get_sources(event_id)
        if sources:
            return sources
        return [
            {
                "source_url": url,
                "source_label": "Packet source",
                "source_type": "official_record",
                "is_primary": index == 0,
            }
            for index, url in enumerate(packet.get("source_urls", []))
        ]

    async def _get_weight_dicts(self, event_id: str) -> list[dict[str, Any]]:
        weights: list[dict[str, Any]] = []
        if self.repo is not None:
            weights = await self.repo.get_weights(event_id)
        if weights:
            return weights
        return self._weight_rows().get(event_id, [])

    def _summary_from_packet(self, packet: dict[str, Any]) -> DisaggregationEventSummary:
        warnings: list[str] = []
        if not packet.get("source_urls"):
            warnings.append("Packet has no linked source URLs yet.")
        if packet.get("weight_status") == "fallback_ready":
            warnings.append("Weights currently rely on equal split fallback.")
        return DisaggregationEventSummary(
            event_id=packet["event_id"],
            parent_cdk=packet["parent_cdk"],
            parent_name=packet.get("parent_name"),
            child_cdks=list(packet.get("child_cdks", [])),
            child_names=list(packet.get("child_names", [])),
            state=packet["state"],
            split_year=int(packet["split_year"]),
            effective_date=packet.get("effective_date"),
            event_type=packet.get("event_type", "SPLIT"),
            readiness_tier=packet.get("readiness_tier", "Tier C"),
            source_quality=packet.get("source_quality", "unknown"),
            geometry_status=packet.get("geometry_status", "unknown"),
            weight_status=packet.get("weight_status", "none"),
            warnings=warnings,
        )

    async def list_events(
        self,
        state: str | None = None,
        readiness_tier: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> DisaggregationEventListResponse:
        packets = await self._list_packet_dicts(state, readiness_tier)
        summaries = [self._summary_from_packet(packet) for packet in packets]
        total = len(summaries)
        return DisaggregationEventListResponse(total=total, items=summaries[offset : offset + limit])

    async def get_event_detail(self, event_id: str) -> DisaggregationEventDetail:
        packet = await self._get_packet_dict(event_id)
        sources = [DisaggregationSource(**row) for row in await self._get_source_dicts(event_id, packet)]
        weights = [SplitEventWeight(**row) for row in await self._get_weight_dicts(event_id)]
        summary = self._summary_from_packet(packet)
        return DisaggregationEventDetail(
            **summary.model_dump(),
            split_event_id=packet.get("split_event_id"),
            source_urls=list(packet.get("source_urls", [])),
            source_text_path=packet.get("source_text_path"),
            aliases=list(packet.get("aliases", [])),
            notes=packet.get("notes"),
            sources=sources,
            weights=weights,
            methodology_note=_METHODOLOGY_NOTE,
        )

    def _panel_point(
        self,
        cdk: str,
        year: int,
        crop: str,
        metric: str,
        provenance_ref: str,
    ) -> EstimatePoint | None:
        value, method = panel_metric_value(self._panel_index(), cdk, year, crop, metric)
        if value is None:
            return None
        confidence = self._method_confidence(method)
        lower, upper = self._bounds(value, confidence)
        return EstimatePoint(
            year=year,
            value=round(value, 4),
            is_estimated=method != "Raw",
            method=method if method else "Raw",
            confidence=round(confidence, 4),
            lower_bound=lower,
            upper_bound=upper,
            provenance_ref=provenance_ref,
        )

    def _parent_series(
        self,
        parent_cdk: str,
        parent_name: str | None,
        crop: str,
        metric: str,
        start_year: int,
        end_year: int,
    ) -> ParentSeries:
        points = []
        for year in range(start_year, end_year + 1):
            point = self._panel_point(parent_cdk, year, crop, metric, f"panel:{parent_cdk}:{year}")
            if point is not None:
                points.append(point)
        return ParentSeries(cdk=parent_cdk, name=parent_name, metric=metric, points=points)

    def _weight_for_child(self, weights: list[dict[str, Any]], child_cdk: str, metric: str) -> dict[str, Any] | None:
        metric_candidates = [metric, "extensive"]
        for candidate in metric_candidates:
            for row in weights:
                if row["child_cdk"] == child_cdk and row["metric_basis"] == candidate:
                    return row
        for row in weights:
            if row["child_cdk"] == child_cdk:
                return row
        return None

    def _weighted_point(
        self,
        parent_point: EstimatePoint | None,
        weight_row: dict[str, Any],
        source_quality: str,
        child_cdk: str,
    ) -> EstimatePoint | None:
        if parent_point is None:
            return None
        value = parent_point.value * float(weight_row["weight_value"])
        confidence = min(
            self._source_confidence(source_quality),
            float(weight_row["weight_confidence"]),
            parent_point.confidence,
        )
        lower, upper = self._bounds(value, confidence)
        return EstimatePoint(
            year=parent_point.year,
            value=round(value, 4),
            is_estimated=True,
            method=str(weight_row["weight_method"]),
            confidence=round(confidence, 4),
            lower_bound=lower,
            upper_bound=upper,
            provenance_ref=f"weight:{child_cdk}:{weight_row['metric_basis']}:{parent_point.year}",
        )

    def _merge_points(self, points: list[EstimatePoint]) -> list[EstimatePoint]:
        deduped: dict[int, EstimatePoint] = {}
        for point in sorted(points, key=lambda item: (item.year, item.is_estimated)):
            existing = deduped.get(point.year)
            if existing is None or (existing.is_estimated and not point.is_estimated):
                deduped[point.year] = point
        return [deduped[year] for year in sorted(deduped)]

    async def _backcast_points(
        self,
        packet: dict[str, Any],
        crop: str,
        child_cdk: str,
        start_year: int,
        end_year: int,
    ) -> list[EstimatePoint]:
        if self.conn is None:
            return []
        try:
            result = await YieldBackcaster().backcast_all_children(
                parent_cdk=packet["parent_cdk"],
                child_cdks=list(packet["child_cdks"]),
                split_year=int(packet["split_year"]),
                crop=crop,
                start_year=start_year,
            )
        except Exception:
            return []

        child_result = result.children.get(child_cdk)
        if child_result is None:
            return []

        points = []
        for year_point in child_result.backcasted_yields:
            if year_point.year < start_year or year_point.year > end_year:
                continue
            points.append(
                EstimatePoint(
                    year=year_point.year,
                    value=round(year_point.predicted_yield, 4),
                    is_estimated=True,
                    method=year_point.method,
                    confidence=round(
                        min(
                            self._source_confidence(packet.get("source_quality", "unknown")),
                            year_point.confidence,
                        ),
                        4,
                    ),
                    lower_bound=round(year_point.lower_bound, 4),
                    upper_bound=round(year_point.upper_bound, 4),
                    provenance_ref=f"backcast:{packet['event_id']}:{child_cdk}:{year_point.year}",
                )
            )
        return points

    async def _child_extensive_points(
        self,
        packet: dict[str, Any],
        child_cdk: str,
        child_name: str | None,
        crop: str,
        metric: str,
        start_year: int,
        end_year: int,
        parent_points: dict[int, EstimatePoint],
        weights: list[dict[str, Any]],
    ) -> ChildSeriesEstimate:
        direct_points: list[EstimatePoint] = []
        for year in range(start_year, end_year + 1):
            direct_point = self._panel_point(child_cdk, year, crop, metric, f"panel:{child_cdk}:{year}")
            if direct_point is not None:
                direct_points.append(direct_point)

        weight_row = self._weight_for_child(weights, child_cdk, metric)
        estimated_points: list[EstimatePoint] = []
        if weight_row is not None:
            for year in range(start_year, min(end_year, int(packet["split_year"]) - 1) + 1):
                if any(point.year == year for point in direct_points):
                    continue
                weighted = self._weighted_point(
                    parent_points.get(year),
                    weight_row,
                    packet.get("source_quality", "unknown"),
                    child_cdk,
                )
                if weighted is not None:
                    estimated_points.append(weighted)

        merged = self._merge_points(direct_points + estimated_points)
        return ChildSeriesEstimate(
            child_cdk=child_cdk,
            child_name=child_name,
            metric=metric,
            weight_method=weight_row["weight_method"] if weight_row else None,
            weight_confidence=float(weight_row["weight_confidence"]) if weight_row else None,
            points=merged,
        )

    def _derive_yield_points(
        self,
        production: ChildSeriesEstimate,
        area: ChildSeriesEstimate,
    ) -> list[EstimatePoint]:
        prod_by_year = {point.year: point for point in production.points}
        area_by_year = {point.year: point for point in area.points}
        points: list[EstimatePoint] = []
        for year in sorted(set(prod_by_year) & set(area_by_year)):
            prod_point = prod_by_year[year]
            area_point = area_by_year[year]
            if area_point.value <= 0:
                continue
            value = (prod_point.value / area_point.value) * 1000.0
            confidence = min(prod_point.confidence, area_point.confidence)
            lower, upper = self._bounds(value, confidence)
            points.append(
                EstimatePoint(
                    year=year,
                    value=round(value, 4),
                    is_estimated=prod_point.is_estimated or area_point.is_estimated,
                    method="derived_from_production_area",
                    confidence=round(confidence, 4),
                    lower_bound=lower,
                    upper_bound=upper,
                    provenance_ref=f"derived_yield:{production.child_cdk}:{year}",
                )
            )
        return points

    async def _child_yield_points(
        self,
        packet: dict[str, Any],
        child_cdk: str,
        child_name: str | None,
        crop: str,
        start_year: int,
        end_year: int,
        parent_yield_points: dict[int, EstimatePoint],
        weights: list[dict[str, Any]],
    ) -> ChildSeriesEstimate:
        direct_points: list[EstimatePoint] = []
        for year in range(start_year, end_year + 1):
            direct_point = self._panel_point(child_cdk, year, crop, "yield", f"panel:{child_cdk}:{year}")
            if direct_point is not None:
                direct_points.append(direct_point)

        prod_points = await self._child_extensive_points(
            packet,
            child_cdk,
            child_name,
            crop,
            "production",
            start_year,
            end_year,
            parent_points={point.year: point for point in self._parent_series(packet["parent_cdk"], None, crop, "production", start_year, end_year).points},
            weights=weights,
        )
        area_points = await self._child_extensive_points(
            packet,
            child_cdk,
            child_name,
            crop,
            "area",
            start_year,
            end_year,
            parent_points={point.year: point for point in self._parent_series(packet["parent_cdk"], None, crop, "area", start_year, end_year).points},
            weights=weights,
        )
        derived_points = self._derive_yield_points(prod_points, area_points)

        backcast_points = []
        missing_pre_split = [
            year
            for year in range(start_year, min(end_year, int(packet["split_year"]) - 1) + 1)
            if year not in {point.year for point in direct_points + derived_points}
        ]
        if missing_pre_split:
            backcast_points = await self._backcast_points(packet, crop, child_cdk, start_year, end_year)

        passthrough_points: list[EstimatePoint] = []
        weight_row = self._weight_for_child(weights, child_cdk, "production") or self._weight_for_child(weights, child_cdk, "area")
        for year in missing_pre_split:
            if any(point.year == year for point in backcast_points):
                continue
            parent_point = parent_yield_points.get(year)
            if parent_point is None:
                continue
            confidence = min(
                self._source_confidence(packet.get("source_quality", "unknown")),
                float(weight_row["weight_confidence"]) if weight_row else 0.2,
                0.2,
            )
            lower, upper = self._bounds(parent_point.value, confidence)
            passthrough_points.append(
                EstimatePoint(
                    year=year,
                    value=parent_point.value,
                    is_estimated=True,
                    method="parent_yield_passthrough",
                    confidence=round(confidence, 4),
                    lower_bound=lower,
                    upper_bound=upper,
                    provenance_ref=f"passthrough:{child_cdk}:{year}",
                )
            )

        merged = self._merge_points(direct_points + derived_points + backcast_points + passthrough_points)
        return ChildSeriesEstimate(
            child_cdk=child_cdk,
            child_name=child_name,
            metric="yield",
            weight_method=weight_row["weight_method"] if weight_row else None,
            weight_confidence=float(weight_row["weight_confidence"]) if weight_row else None,
            points=merged,
        )

    async def get_event_series(
        self,
        event_id: str,
        crop: str,
        metric: str,
        start_year: int,
        end_year: int,
    ) -> DisaggregationSeriesResponse:
        packet = await self._get_packet_dict(event_id)
        detail = await self.get_event_detail(event_id)
        parent_series = self._parent_series(packet["parent_cdk"], packet.get("parent_name"), crop, metric, start_year, end_year)

        warnings = list(detail.warnings)
        if detail.readiness_tier == "Tier C":
            warnings.append("Event is metadata-only until usable weights or official sources are added.")
            return DisaggregationSeriesResponse(
                event_id=event_id,
                crop=crop,
                metric=metric,
                readiness_tier=detail.readiness_tier,
                readiness_status="not_ready",
                parent_series=parent_series,
                child_series=[],
                warnings=warnings,
                methodology_note=_METHODOLOGY_NOTE,
            )

        weights = [weight.model_dump() for weight in detail.weights]
        parent_points = {point.year: point for point in parent_series.points}

        child_series: list[ChildSeriesEstimate] = []
        child_names = list(packet.get("child_names", []))
        child_cdks = list(packet.get("child_cdks", []))
        for index, child_cdk in enumerate(child_cdks):
            child_name = child_names[index] if index < len(child_names) else child_cdk
            if metric in {"area", "production"}:
                child_series.append(
                    await self._child_extensive_points(
                        packet,
                        child_cdk,
                        child_name,
                        crop,
                        metric,
                        start_year,
                        end_year,
                        parent_points,
                        weights,
                    )
                )
            else:
                child_series.append(
                    await self._child_yield_points(
                        packet,
                        child_cdk,
                        child_name,
                        crop,
                        start_year,
                        end_year,
                        parent_points,
                        weights,
                    )
                )

        if any(series.weight_method == "equal_split_fallback" for series in child_series):
            warnings.append("Some child estimates use equal split fallback weights.")
        if any(any(point.method == "parent_yield_passthrough" for point in series.points) for series in child_series):
            warnings.append("Some yield points fall back to parent-yield passthrough because supporting area/production signals were missing.")
        if any(any(point.method.startswith("Backcast") or point.method == "ratio_extrapolation" for point in series.points) for series in child_series):
            warnings.append("Yield backcast methods were used where direct extensive reconstruction was unavailable.")

        return DisaggregationSeriesResponse(
            event_id=event_id,
            crop=crop,
            metric=metric,
            readiness_tier=detail.readiness_tier,
            readiness_status="ready",
            parent_series=parent_series,
            child_series=child_series,
            warnings=warnings,
            methodology_note=_METHODOLOGY_NOTE,
        )
