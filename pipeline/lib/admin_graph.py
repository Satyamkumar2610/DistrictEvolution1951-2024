"""
AdminGraph — DAG representation of Indian district boundary changes.

Nodes are AdminUnit records (districts with temporal validity).
Edges are AdminTransition records (SPLIT/MERGE/RENAME/BOUNDARY_ADJUST events).

Traversal methods:
  ancestors(unit_id, at_year)       → historical parent units
  apportionment_chain(unit_id, year) → ordered edges for value apportionment
"""

from __future__ import annotations

import functools
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import asyncpg


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class AdminUnit:
    """A single administrative district with temporal validity."""

    id: str
    name: str
    state: str
    valid_from: date
    valid_to: Optional[date]


@dataclass
class AdminTransition:
    """A directed edge in the admin lineage graph."""

    id: str
    from_unit_id: str
    to_unit_id: str
    transition_type: str  # SPLIT | MERGE | RENAME | BOUNDARY_ADJUST
    effective_date: date
    area_weight: float
    confidence: float


@dataclass
class AdminGraph:
    """
    In-memory directed graph of district boundary changes.

    units: mapping from unit ID → AdminUnit
    transitions: flat list of all edges

    Supports backward traversal (ancestors) and forward traversal
    (apportionment chains) for data harmonization.
    """

    units: dict[str, AdminUnit] = field(default_factory=dict)
    transitions: list[AdminTransition] = field(default_factory=list)

    # --- Backward Traversal ---

    def ancestors(self, unit_id: str, at_year: int) -> list[AdminUnit]:
        """
        Walk backwards through SPLIT/MERGE edges to find parent units
        that existed at or before `at_year`.

        Returns all ancestor AdminUnit objects (recursive, depth-first).
        """
        results: list[AdminUnit] = []
        visited: set[str] = set()
        self._collect_ancestors(unit_id, at_year, results, visited)
        return results

    def _collect_ancestors(
        self,
        unit_id: str,
        at_year: int,
        results: list[AdminUnit],
        visited: set[str],
    ) -> None:
        """Recursive ancestor collector with cycle protection."""
        if unit_id in visited:
            return
        visited.add(unit_id)

        target_date = date(at_year, 1, 1)
        incoming = [
            t
            for t in self.transitions
            if t.to_unit_id == unit_id and t.effective_date >= target_date
        ]
        for edge in incoming:
            parent = self.units.get(edge.from_unit_id)
            if parent:
                results.append(parent)
                self._collect_ancestors(parent.id, at_year, results, visited)

    # --- Forward Traversal ---

    def apportionment_chain(
        self, unit_id: str, target_year: int
    ) -> list[AdminTransition]:
        """
        Return the ordered list of transition edges needed to apportion
        historical data from an ancestor to this unit.

        If the unit existed in target_year, returns empty list (no
        apportionment needed — data is direct).
        """
        target_date = date(target_year, 1, 1)
        unit = self.units.get(unit_id)

        if not unit:
            return []

        # Unit already existed at target_year → no apportionment needed
        if unit.valid_from <= target_date:
            return []

        # Find the transition that created this unit
        incoming = [t for t in self.transitions if t.to_unit_id == unit_id]
        if not incoming:
            return []

        # Use the earliest transition (the one that created this unit)
        edge = sorted(incoming, key=lambda e: e.effective_date)[0]

        # Recurse to find the full chain back to the ancestor
        parent_chain = self.apportionment_chain(edge.from_unit_id, target_year)
        return parent_chain + [edge]

    # --- Query Helpers ---

    def children_of(self, unit_id: str) -> list[AdminTransition]:
        """All transitions where unit_id is the source (forward edges)."""
        return [t for t in self.transitions if t.from_unit_id == unit_id]

    def parents_of(self, unit_id: str) -> list[AdminTransition]:
        """All transitions where unit_id is the target (backward edges)."""
        return [t for t in self.transitions if t.to_unit_id == unit_id]

    def get_unit_by_name(
        self, name: str, state: str | None = None
    ) -> AdminUnit | None:
        """Find a unit by name (case-insensitive), optionally filtered by state."""
        for unit in self.units.values():
            if unit.name.lower() == name.lower():
                if state is None or unit.state.lower() == state.lower():
                    return unit
        return None

    def active_units_at(self, year: int) -> list[AdminUnit]:
        """Return all units that were active at the given year."""
        ref = date(year, 1, 1)
        return [
            u
            for u in self.units.values()
            if u.valid_from <= ref and (u.valid_to is None or u.valid_to > ref)
        ]


# ---------------------------------------------------------------------------
# Graph Builder from Database
# ---------------------------------------------------------------------------

_graph_cache: AdminGraph | None = None


async def build_graph(dsn: str | None = None) -> AdminGraph:
    """
    Build the AdminGraph from the database.

    Caches the result in a module-level variable. Call `invalidate_graph()`
    to force a rebuild (e.g., after loading new transitions).
    """
    global _graph_cache
    if _graph_cache is not None:
        return _graph_cache

    if dsn is None:
        dsn = os.environ.get(
            "DATABASE_URL", "postgresql://user:password@localhost:5432/i_ascap"
        )

    conn = await asyncpg.connect(dsn)
    try:
        units_rows = await conn.fetch(
            "SELECT id, name, state, valid_from, valid_to FROM admin_units"
        )
        transitions_rows = await conn.fetch(
            """
            SELECT id, from_unit_id, to_unit_id, transition_type,
                   effective_date, area_weight, confidence
            FROM admin_transitions
            """
        )

        graph = AdminGraph()
        for r in units_rows:
            uid = str(r["id"])
            graph.units[uid] = AdminUnit(
                id=uid,
                name=r["name"],
                state=r["state"],
                valid_from=r["valid_from"],
                valid_to=r["valid_to"],
            )

        graph.transitions = [
            AdminTransition(
                id=str(r["id"]),
                from_unit_id=str(r["from_unit_id"]),
                to_unit_id=str(r["to_unit_id"]),
                transition_type=r["transition_type"],
                effective_date=r["effective_date"],
                area_weight=float(r["area_weight"]),
                confidence=float(r["confidence"]),
            )
            for r in transitions_rows
        ]

        _graph_cache = graph
        return graph
    finally:
        await conn.close()


def invalidate_graph() -> None:
    """Clear the cached graph, forcing a rebuild on next call."""
    global _graph_cache
    _graph_cache = None
