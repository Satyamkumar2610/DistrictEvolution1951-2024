"""
Lineage Repository: Data access for lineage events (DB-based).

Performance features:
  - Recursive CTEs for deep ancestry / descendant traversal.
  - Redis-backed caching for frequently accessed apportionment chains.

Note: lineage_events uses CDK text keys which cannot join to districts.cdk.
"""

import contextlib
import logging
from typing import Any

from app.cache import CacheTTL, get_cache
from app.repositories.base import BaseRepository
from app.schemas.lineage import (
    CoverageDistrictItem,
    DistrictHistoryItem,
    EventType,
    LineageEvent,
    TrackingCoverage,
    TrackingDistrict,
)

logger = logging.getLogger(__name__)


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
        has no relationship to districts.cdk (int). We filter in Python instead.
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
            SELECT cdk::text as cdk, district_name, state_name, NULL::int as start_year, NULL::int as end_year
            FROM districts
            WHERE cdk::text = $1
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
            WHERE cdk::text = $1
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
                d.cdk::text as cdk,
                d.district_name,
                NULL::int as start_year,
                NULL::int as end_year,
                COUNT(DISTINCT am.year) as years_with_data,
                COUNT(am.year) as record_count,
                'original' as lineage_status
            FROM districts d
            LEFT JOIN agri_metrics am ON d.cdk = am.cdk
            WHERE d.state_name = $1
            GROUP BY d.cdk, d.district_name
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

    # ------------------------------------------------------------------
    # Recursive CTE-based Ancestry Resolution (v2.0)
    # ------------------------------------------------------------------

    async def get_full_ancestry(self, cdk: str, max_depth: int = 10) -> list[dict[str, Any]]:
        """
        Walk backwards through the lineage graph using a recursive CTE
        to find all ancestor districts and the transition events that
        connect them.

        Returns a flat list of dicts:
            [{cdk, parent_cdk, event_year, event_type, depth}, ...]
        sorted by depth (closest ancestors first).
        """
        # Check cache first
        cache = get_cache()
        cache_key = f"ancestry:{cdk}:{max_depth}"
        try:
            cached = await cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            pass

        query = """
            WITH RECURSIVE lineage AS (
                -- Base case: direct parents of the target district
                SELECT
                    le.parent_cdk,
                    le.child_cdk,
                    le.event_year,
                    le.event_type,
                    1 AS depth
                FROM lineage_events le
                WHERE le.child_cdk = $1

                UNION ALL

                -- Recursive step: walk up to grandparents
                SELECT
                    le.parent_cdk,
                    le.child_cdk,
                    le.event_year,
                    le.event_type,
                    l.depth + 1 AS depth
                FROM lineage_events le
                INNER JOIN lineage l ON le.child_cdk = l.parent_cdk
                WHERE l.depth < $2
            )
            SELECT parent_cdk, child_cdk, event_year, event_type, depth
            FROM lineage
            ORDER BY depth ASC, event_year DESC
        """
        rows = await self.fetch_all(query, cdk, max_depth)
        result = [dict(row) for row in rows]

        # Cache for 24 hours (lineage data rarely changes)
        with contextlib.suppress(Exception):
            await cache.set(cache_key, result, CacheTTL.LINEAGE)

        return result

    async def get_full_descendants(self, cdk: str, max_depth: int = 10) -> list[dict[str, Any]]:
        """
        Walk forward through the lineage graph using a recursive CTE
        to find all descendant districts.

        Returns a flat list of dicts:
            [{parent_cdk, child_cdk, event_year, event_type, depth}, ...]
        sorted by depth (immediate children first).
        """
        cache = get_cache()
        cache_key = f"descendants:{cdk}:{max_depth}"
        try:
            cached = await cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            pass

        query = """
            WITH RECURSIVE lineage AS (
                -- Base case: direct children of the target district
                SELECT
                    le.parent_cdk,
                    le.child_cdk,
                    le.event_year,
                    le.event_type,
                    1 AS depth
                FROM lineage_events le
                WHERE le.parent_cdk = $1

                UNION ALL

                -- Recursive step: walk down to grandchildren
                SELECT
                    le.parent_cdk,
                    le.child_cdk,
                    le.event_year,
                    le.event_type,
                    l.depth + 1 AS depth
                FROM lineage_events le
                INNER JOIN lineage l ON le.parent_cdk = l.child_cdk
                WHERE l.depth < $2
            )
            SELECT parent_cdk, child_cdk, event_year, event_type, depth
            FROM lineage
            ORDER BY depth ASC, event_year ASC
        """
        rows = await self.fetch_all(query, cdk, max_depth)
        result = [dict(row) for row in rows]

        with contextlib.suppress(Exception):
            await cache.set(cache_key, result, CacheTTL.LINEAGE)

        return result

    async def get_apportionment_chain(self, cdk: str) -> list[dict[str, Any]]:
        """
        Get the full apportionment chain for a district — the ordered list
        of transition edges from the oldest ancestor down to the target.

        This is the critical path used by the harmonization engine to
        compute area-weighted historical yields.

        Results are heavily cached since apportionment chains are immutable
        once ingested.
        """
        cache = get_cache()
        cache_key = f"apportionment:{cdk}"
        try:
            cached = await cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            pass

        ancestors = await self.get_full_ancestry(cdk)

        # The chain is the ancestor list reversed (root -> target)
        chain = list(reversed(ancestors))

        with contextlib.suppress(Exception):
            await cache.set(cache_key, chain, CacheTTL.LINEAGE)

        return chain
