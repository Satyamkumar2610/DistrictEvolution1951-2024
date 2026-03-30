"""
Lineage application service for API-facing lineage and provenance workflows.
"""

from typing import cast

import asyncpg

from app.core.name_matching import (
    STATE_ALIASES,
    TELANGANA_DISTRICTS,
    check_historical_resolution,
    resolve_district_name,
)
from app.exceptions import NotFoundError
from app.repositories.district_repo import DistrictRepository
from app.repositories.lineage_repo import LineageRepository
from app.schemas.lineage import (
    DistrictHistoryItem,
    LineageGraph,
    ProvenanceTrackingResponse,
    StateCoverageResponse,
    TrackingLineage,
    TrackingSource,
    UnmappedSplitItem,
)


class LineageService:
    """Service layer for lineage, tracking, and coverage APIs."""

    def __init__(self, conn: asyncpg.Connection):
        self.district_repo = DistrictRepository(conn)
        self.lineage_repo = LineageRepository(conn)

    async def get_district_history_response(
        self,
        state: str | None = None,
    ) -> list[DistrictHistoryItem]:
        """Get district split history, optionally filtered by state."""
        return await self.lineage_repo.get_district_history(state)

    async def get_lineage_events_response(self, state: str | None = None) -> LineageGraph:
        """Get lineage graph data, optionally filtered by state."""
        if state:
            cdk_meta = await self.district_repo.get_cdk_to_meta_map()
            cdk_to_state = {cdk: meta["state"] for cdk, meta in cdk_meta.items()}
            events = await self.lineage_repo.get_events_by_state(state, cdk_to_state)
        else:
            events = await self.lineage_repo.get_all_events()

        return LineageGraph(total_events=len(events), events=events)

    async def get_data_tracking_response(self, cdk: str) -> ProvenanceTrackingResponse:
        """Get provenance and data coverage details for a district."""
        district = await self.lineage_repo.get_tracking_district(cdk)
        if district is None:
            raise NotFoundError("District", cdk)

        coverage = await self.lineage_repo.get_tracking_coverage(cdk)

        return ProvenanceTrackingResponse(
            district=district,
            data_coverage=coverage,
            data_sources=[
                TrackingSource(
                    source="ICRISAT/DES",
                    record_count=coverage.total_records,
                    from_year=coverage.first_year,
                    to_year=coverage.last_year,
                )
            ],
            lineage=TrackingLineage(split_into=[], created_from=[]),
        )

    async def get_state_coverage_response(self, state: str) -> StateCoverageResponse:
        """Get district-level data coverage summary for a state."""
        coverage = await self.lineage_repo.get_state_coverage(state)
        return StateCoverageResponse(
            state=state,
            districts=len(coverage),
            coverage=coverage,
        )

    async def get_unmapped_splits_response(self) -> list[UnmappedSplitItem]:
        """Get split districts that still cannot be resolved to LGD codes."""
        lgd_lookup = await self.district_repo.get_lgd_lookup()
        split_rows = await self.lineage_repo.get_split_name_rows()
        unmapped: set[tuple[str, str, int, str]] = set()

        for row in split_rows:
            state_name = str(row["state_name"])
            split_year_value = cast(int | str, row["split_year"])
            split_year = int(split_year_value)
            parent_name = str(row["parent_district"])
            child_name = str(row["child_district"])

            if not self._resolve_lgd(parent_name, state_name, lgd_lookup) and not check_historical_resolution(
                state_name,
                parent_name,
            ):
                unmapped.add((parent_name, state_name, split_year, "Parent"))

            if not self._resolve_lgd(child_name, state_name, lgd_lookup) and not check_historical_resolution(
                state_name,
                child_name,
            ):
                unmapped.add((child_name, state_name, split_year, "Child"))

        return [
            UnmappedSplitItem(
                district=district,
                state=state,
                year=year,
                role=role,
            )
            for district, state, year, role in sorted(
                unmapped,
                key=lambda item: (item[1], item[0], item[2]),
            )
        ]

    def _resolve_lgd(
        self,
        district_name: str,
        state_name: str,
        lgd_lookup: dict[tuple[str, str], int],
    ) -> int | None:
        """Resolve a district/state pair against known LGD mappings."""
        normalized_name = resolve_district_name(district_name, state_name)
        normalized_state = state_name.lower().strip()

        direct_match = lgd_lookup.get((normalized_name, normalized_state))
        if direct_match is not None:
            return direct_match

        for alias_key, alias_states in STATE_ALIASES.items():
            if alias_key in normalized_state:
                for alias_state in alias_states:
                    alias_match = lgd_lookup.get((normalized_name, alias_state.lower()))
                    if alias_match is not None:
                        return alias_match

        if (
            normalized_name in TELANGANA_DISTRICTS
            and "andhra" in normalized_state
            and (normalized_name, "telangana") in lgd_lookup
        ):
            return lgd_lookup[(normalized_name, "telangana")]

        return None
