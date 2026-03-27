"""
Lineage Repository: Data access for lineage events (DB-based).
Note: lineage_events uses CDK text keys which cannot join to districts.lgd_code.
"""

from app.repositories.base import BaseRepository
from app.schemas.lineage import EventType, LineageEvent


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
            events.append(LineageEvent(
                id=f"{r['parent_cdk']}_{r['event_year']}",
                parent_cdk=r['parent_cdk'],
                children_cdks=[r['child_cdk']],
                children_names=[],
                children_count=1,
                event_year=r['event_year'],
                event_type=EventType.SPLIT,
                confidence=0.9,  # Default confidence
            ))
        return events

    async def get_events_by_state(
        self,
        state: str,
        cdk_to_state: dict[str, str]
    ) -> list[LineageEvent]:
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

    def group_by_parent_year(
        self,
        events: list[LineageEvent]
    ) -> dict[str, dict]:
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
