"""
Domain tool: get_lineage

Returns the full administrative ancestry and descendant tree
for a given district, including transition events with dates,
area weights, and confidence scores.
"""

from __future__ import annotations

from pydantic import BaseModel

import asyncpg


class TransitionEvent(BaseModel):
    """A single boundary change event."""

    from_district: str
    to_district: str
    transition_type: str
    effective_date: str
    area_weight: float
    confidence: float


class LineageTree(BaseModel):
    """Full lineage tree for a district."""

    unit_id: str
    unit_name: str
    state: str
    valid_from: str
    valid_to: str | None
    ancestors: list[TransitionEvent]
    descendants: list[TransitionEvent]


async def get_lineage(conn: asyncpg.Connection, unit_id: str) -> LineageTree:
    """
    Get the full administrative ancestry and descendants of a district.

    Queries admin_transitions with admin_units joins to build the
    complete lineage tree in both directions.

    Args:
        conn: Database connection
        unit_id: District UUID

    Returns:
        LineageTree with ancestor and descendant transition events.
    """
    # Get the unit info
    unit = await conn.fetchrow(
        "SELECT id, name, state, valid_from, valid_to FROM admin_units WHERE id = $1",
        unit_id,
    )
    if not unit:
        return LineageTree(
            unit_id=unit_id,
            unit_name="Unknown",
            state="Unknown",
            valid_from="",
            valid_to=None,
            ancestors=[],
            descendants=[],
        )

    # Get ancestors (transitions where this unit is the target)
    ancestor_rows = await conn.fetch(
        """
        SELECT
            from_u.name as from_district,
            to_u.name as to_district,
            t.transition_type::text,
            t.effective_date::text,
            t.area_weight,
            t.confidence
        FROM admin_transitions t
        JOIN admin_units from_u ON from_u.id = t.from_unit_id
        JOIN admin_units to_u ON to_u.id = t.to_unit_id
        WHERE t.to_unit_id = $1
        ORDER BY t.effective_date DESC
        """,
        unit_id,
    )

    # Get descendants (transitions where this unit is the source)
    descendant_rows = await conn.fetch(
        """
        SELECT
            from_u.name as from_district,
            to_u.name as to_district,
            t.transition_type::text,
            t.effective_date::text,
            t.area_weight,
            t.confidence
        FROM admin_transitions t
        JOIN admin_units from_u ON from_u.id = t.from_unit_id
        JOIN admin_units to_u ON to_u.id = t.to_unit_id
        WHERE t.from_unit_id = $1
        ORDER BY t.effective_date ASC
        """,
        unit_id,
    )

    return LineageTree(
        unit_id=str(unit["id"]),
        unit_name=unit["name"],
        state=unit["state"],
        valid_from=str(unit["valid_from"]),
        valid_to=str(unit["valid_to"]) if unit["valid_to"] else None,
        ancestors=[TransitionEvent(**dict(r)) for r in ancestor_rows],
        descendants=[TransitionEvent(**dict(r)) for r in descendant_rows],
    )
