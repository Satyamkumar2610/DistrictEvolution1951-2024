"""
Repository for disaggregation packet metadata.
"""

from __future__ import annotations

import asyncpg

from app.repositories.base import BaseRepository


class DisaggregationRepository(BaseRepository):
    """Repository for packet, source, and weight tables."""

    async def list_packets(
        self,
        state: str | None = None,
        readiness_tier: str | None = None,
    ) -> list[dict]:
        clauses: list[str] = []
        args: list[object] = []

        if state:
            args.append(state)
            clauses.append(f"state = ${len(args)}")

        if readiness_tier:
            args.append(readiness_tier)
            clauses.append(f"readiness_tier = ${len(args)}")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT
                event_id,
                split_event_id,
                parent_cdk,
                parent_name,
                child_cdks,
                child_names,
                state,
                split_year,
                effective_date::text as effective_date,
                event_type,
                source_quality,
                source_urls,
                source_text_path,
                aliases,
                geometry_status,
                weight_status,
                readiness_tier,
                notes
            FROM split_event_packets
            {where}
            ORDER BY split_year DESC, parent_cdk ASC
        """
        try:
            rows = await self.fetch_all(query, *args)
        except asyncpg.UndefinedTableError:
            return []
        return [dict(row) for row in rows]

    async def get_packet(self, event_id: str) -> dict | None:
        query = """
            SELECT
                event_id,
                split_event_id,
                parent_cdk,
                parent_name,
                child_cdks,
                child_names,
                state,
                split_year,
                effective_date::text as effective_date,
                event_type,
                source_quality,
                source_urls,
                source_text_path,
                aliases,
                geometry_status,
                weight_status,
                readiness_tier,
                notes
            FROM split_event_packets
            WHERE event_id = $1
        """
        try:
            row = await self.fetch_one(query, event_id)
        except asyncpg.UndefinedTableError:
            return None
        return dict(row) if row else None

    async def get_sources(self, event_id: str) -> list[dict]:
        query = """
            SELECT
                source_url,
                source_label,
                source_type,
                is_primary
            FROM split_event_sources
            WHERE event_id = $1
            ORDER BY is_primary DESC, id ASC
        """
        try:
            rows = await self.fetch_all(query, event_id)
        except asyncpg.UndefinedTableError:
            return []
        return [dict(row) for row in rows]

    async def get_weights(self, event_id: str) -> list[dict]:
        query = """
            SELECT
                event_id,
                child_cdk,
                child_name,
                metric_basis,
                weight_value,
                weight_method,
                weight_confidence,
                source_year,
                basis,
                is_fallback
            FROM split_event_weights
            WHERE event_id = $1
            ORDER BY metric_basis, child_cdk
        """
        try:
            rows = await self.fetch_all(query, event_id)
        except asyncpg.UndefinedTableError:
            return []
        return [dict(row) for row in rows]
