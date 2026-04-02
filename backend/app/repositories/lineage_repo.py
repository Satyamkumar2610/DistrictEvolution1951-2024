"""
Lineage Repository: Data access for lineage events (DB-based).
Note: lineage_events uses CDK text keys which cannot join to districts.lgd_code.
"""

from app.repositories.base import BaseRepository
from app.schemas.lineage import (
    CoverageDistrictItem,
    DistrictHistoryItem,
    EventType,
    LineageEvent,
    TrackingCoverage,
    TrackingDistrict,
)


class LineageRepository(BaseRepository):
    """
    Repository for lineage event data (DB implementation).
    """

    async def get_all_events(self) -> list[LineageEvent]:
        """Get all lineage events from DB."""
        query = """
            SELECT parent_cdk, child_cdk, event_year, event_type
            FROM lineage_events
        """
        rows = await self.fetch_all(query)

        events = []
        for r in rows:
            events.append(
                LineageEvent(
                    id=f"{r['parent_cdk']}_{r['event_year']}",
                    parent_cdk=r["parent_cdk"],
                    children_cdks=[r["child_cdk"]],
                    children_names=[],
                    children_count=1,
                    event_year=r["event_year"],
                    event_type=EventType.SPLIT,
                    confidence=0.9,  # Default confidence
                )
            )
        return events

    async def get_events_by_state(self, state: str, cdk_to_state: dict[str, str]) -> list[LineageEvent]:
        """Filter events where parent belongs to given state using Python filtering.

        Cannot use SQL JOIN because lineage_events.parent_cdk (text like AR_balipa_1951)
        has no relationship to districts.lgd_code (int). We filter in Python instead.
        """
        all_events = await self.get_all_events()

        # Filter by state using the cdk_to_state mapping
        events = []
        for e in all_events:
            parent_state = cdk_to_state.get(e.parent_cdk)
            if parent_state == state:
                events.append(e)

        return events

    def group_by_parent_year(self, events: list[LineageEvent]) -> dict[str, dict]:
        """
        Group events by parent_cdk|year to consolidate multi-child splits.
        Returns dict with grouped event info.
        """
        groups: dict[str, dict] = {}

        for e in events:
            key = f"{e.parent_cdk}|{e.event_year}"
            if key not in groups:
                groups[key] = {
                    "parent_cdk": e.parent_cdk,
                    "event_year": e.event_year,
                    "children": set(),
                    "confidence": e.confidence,
                }
            groups[key]["children"].update(e.children_cdks)

        return groups

    async def get_district_history(
        self,
        state: str | None = None,
    ) -> list[DistrictHistoryItem]:
        """Get district split history records, optionally filtered by state."""
        query = """
            SELECT
                state_name,
                split_year,
                parent_district,
                child_district,
                parent_lgd::text as parent_cdk,
                child_lgd::text as child_cdk,
                source
            FROM district_splits
            WHERE ($1::text IS NULL OR UPPER(state_name) = UPPER($1))
            ORDER BY state_name, split_year
        """
        rows = await self.fetch_all(query, state)
        return [DistrictHistoryItem.model_validate(dict(row)) for row in rows]

    async def get_tracking_district(self, cdk: str) -> TrackingDistrict | None:
        """Get district metadata for provenance tracking."""
        query = """
            SELECT lgd_code::text as cdk, district_name, state_name, NULL::int as start_year, NULL::int as end_year
            FROM districts
            WHERE lgd_code::text = $1
        """
        row = await self.fetch_one(query, cdk)
        if row is None:
            return None
        return TrackingDistrict.model_validate(dict(row))

    async def get_tracking_coverage(self, cdk: str) -> TrackingCoverage:
        """Get metric coverage summary for a district."""
        query = """
            SELECT
                COUNT(DISTINCT year) as years_with_data,
                MIN(year) as first_year,
                MAX(year) as last_year,
                COUNT(DISTINCT variable_name) as variables,
                COUNT(*) as total_records
            FROM agri_metrics
            WHERE district_lgd::text = $1
        """
        row = await self.fetch_one(query, cdk)
        if row is None:
            return TrackingCoverage(
                years_with_data=0,
                first_year=None,
                last_year=None,
                variables=0,
                total_records=0,
            )
        return TrackingCoverage.model_validate(dict(row))

    async def get_state_coverage(self, state: str) -> list[CoverageDistrictItem]:
        """Get district coverage summary for a state."""
        query = """
            SELECT
                d.lgd_code::text as cdk,
                d.district_name,
                NULL::int as start_year,
                NULL::int as end_year,
                COUNT(DISTINCT am.year) as years_with_data,
                COUNT(am.year) as record_count,
                'original' as lineage_status
            FROM districts d
            LEFT JOIN agri_metrics am ON d.lgd_code = am.district_lgd
            WHERE d.state_name = $1
            GROUP BY d.lgd_code, d.district_name
            ORDER BY d.district_name
        """
        rows = await self.fetch_all(query, state)
        return [CoverageDistrictItem.model_validate(dict(row)) for row in rows]

    async def get_split_name_rows(self) -> list[dict[str, object]]:
        """Get split district names used for LGD resolution checks."""
        query = """
            SELECT parent_district, child_district, split_year, state_name
            FROM district_splits
        """
        rows = await self.fetch_all(query)
        return [dict(row) for row in rows]
