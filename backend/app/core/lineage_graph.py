"""
LineageGraph — DAG-based district lineage tracking.

Represents all Indian administrative boundary changes (1951–2024) as a
directed acyclic graph where:
  - Nodes are CDK strings (e.g., 'DL_delhi_1991')
  - Edges are typed by event (SPLIT, MERGE, RENAME, STATE_TRANSFER, etc.)

Supports bidirectional traversal:
  get_canonical_ancestors(cdk, year)  → who contributed area to this district?
  get_canonical_descendants(cdk, year) → where did this district's area go?
"""
from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger("app.core.lineage_graph")


# ---------------------------------------------------------------------------
# Event Types
# ---------------------------------------------------------------------------

class EventType(StrEnum):
    """All possible administrative boundary change types."""
    SPLIT = "SPLIT"
    MERGE = "MERGE"
    RENAME = "RENAME"
    STATE_TRANSFER = "STATE_TRANSFER"
    CREATION = "CREATION"
    DISSOLUTION = "DISSOLUTION"
    CONTINUITY = "CONTINUITY"


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DistrictEvent:
    """A single administrative boundary change event."""
    event_type: EventType
    year: int
    source_cdks: tuple[str, ...]     # parents / predecessor(s)
    target_cdks: tuple[str, ...]     # children / successor(s)
    confidence: float = 1.0
    area_ratios: dict[str, float] | None = field(
        default=None, hash=False, compare=False
    )

    @property
    def label(self) -> str:
        """Human-readable event description."""
        src = ", ".join(self.source_cdks)
        tgt = ", ".join(self.target_cdks)
        if self.event_type == EventType.SPLIT:
            return f"{src} → {tgt} ({self.year})"
        if self.event_type == EventType.RENAME:
            return f"{src} renamed to {tgt} ({self.year})"
        if self.event_type == EventType.MERGE:
            return f"{src} merged into {tgt} ({self.year})"
        if self.event_type == EventType.STATE_TRANSFER:
            return f"{src} transferred to {tgt} ({self.year})"
        return f"{self.event_type.value}: {src} → {tgt} ({self.year})"


@dataclass
class DistrictNode:
    """Metadata about a district at a point in time."""
    cdk: str
    name: str | None = None
    state_code: str | None = None
    valid_from: int | None = None
    valid_to: int | None = None

    @property
    def state_name(self) -> str:
        from app.services.reconstructor_service import STATE_CODE_MAP  # type: ignore
        return STATE_CODE_MAP.get(self.state_code or "", self.state_code or "")


# ---------------------------------------------------------------------------
# Lineage Graph
# ---------------------------------------------------------------------------

class LineageGraph:
    """
    Directed acyclic graph representing district lineage.

    Forward map:  parent_cdk → [(children, year, event_type)]
    Inverse map:  child_cdk  → [(parents, year, event_type)]
    Events index: all DistrictEvent objects keyed by year
    """

    def __init__(self) -> None:
        # Forward: parent → children edges
        self._forward: dict[str, list[DistrictEvent]] = defaultdict(list)
        # Inverse: child → parent edges
        self._inverse: dict[str, list[DistrictEvent]] = defaultdict(list)
        # All events, chronologically indexable
        self._events: list[DistrictEvent] = []
        # Dedup set to prevent duplicate event insertion
        self._event_set: set[frozenset] = set()
        # Node metadata
        self._nodes: dict[str, DistrictNode] = {}
        # All known CDKs
        self._all_cdks: set[str] = set()

    # --- Construction ---

    def add_event(self, event: DistrictEvent) -> bool:
        """
        Add a DistrictEvent to the graph. Returns False if duplicate.

        Automatically builds both forward and inverse indices a
        and deduplicates events.
        """
        # Dedup key: (type, year, sources, targets)
        dedup_key = frozenset([
            event.event_type.value,
            str(event.year),
            "|".join(sorted(event.source_cdks)),
            "|".join(sorted(event.target_cdks)),
        ])
        if dedup_key in self._event_set:
            return False
        self._event_set.add(dedup_key)

        # Skip pure continuity events — they add no edges
        if event.event_type == EventType.CONTINUITY:
            for cdk in event.source_cdks:
                self._all_cdks.add(cdk)
            return True

        self._events.append(event)

        # Forward edges: each source → event
        for src in event.source_cdks:
            self._forward[src].append(event)
            self._all_cdks.add(src)

        # Inverse edges: each target → event
        for tgt in event.target_cdks:
            self._inverse[tgt].append(event)
            self._all_cdks.add(tgt)

        return True

    def add_node(self, node: DistrictNode) -> None:
        """Register metadata for a CDK."""
        self._nodes[node.cdk] = node
        self._all_cdks.add(node.cdk)

    @classmethod
    def from_split_events(
        cls,
        rows: list[dict],
    ) -> LineageGraph:
        """
        Build a LineageGraph from split_events DB rows.

        Each row: {parent_cdk, child_cdks: List[str], split_year, event_type?}
        Handles deduplication automatically.
        """
        graph = cls()
        for row in rows:
            parent = row["parent_cdk"]
            children = row["child_cdks"]
            year = row["split_year"]
            raw_type = row.get("event_type", "SPLIT")

            # Normalise event type
            try:
                etype = EventType(raw_type.upper() if isinstance(raw_type, str) else "SPLIT")
            except ValueError:
                etype = EventType.SPLIT

            # Detect implicit renames (1 parent → 1 child, different CDK)
            if etype == EventType.SPLIT and len(children) == 1 and children[0] != parent:
                etype = EventType.RENAME

            event = DistrictEvent(
                event_type=etype,
                year=year,
                source_cdks=(parent,),
                target_cdks=tuple(children),
                confidence=row.get("confidence", 1.0),
            )
            graph.add_event(event)

            # Register nodes
            state_code = parent.split("_")[0] if "_" in parent else ""
            graph.add_node(DistrictNode(
                cdk=parent,
                state_code=state_code,
                valid_to=year,
            ))
            for child in children:
                child_state = child.split("_")[0] if "_" in child else ""
                graph.add_node(DistrictNode(
                    cdk=child,
                    state_code=child_state,
                    valid_from=year,
                ))

        logger.info(
            f"LineageGraph built: {len(graph._all_cdks)} nodes, "
            f"{len(graph._events)} events (deduped)"
        )
        return graph

    @classmethod
    def from_csv_rows(
        cls,
        rows: list[dict],
    ) -> LineageGraph:
        """
        Build from raw lineage CSV rows.

        Each row: {parent_cdk, child_cdk (singular), event_year, event_type, ...}
        Groups children by (parent, year) to form proper events.
        """
        graph = cls()

        # Group by (parent, year, type) to collect siblings
        groups: dict[tuple[str, int, str], list[str]] = defaultdict(list)
        for row in rows:
            parent = row["parent_cdk"]
            child = row["child_cdk"]
            year = int(row["event_year"])
            etype = row.get("event_type", "SPLIT")
            key = (parent, year, etype)
            if child not in groups[key]:
                groups[key].append(child)

        for (parent, year, raw_type), children in groups.items():
            try:
                etype = EventType(raw_type.upper())
            except ValueError:
                etype = EventType.SPLIT

            # Detect renames
            if etype == EventType.SPLIT and len(children) == 1 and children[0] != parent:
                etype = EventType.RENAME

            event = DistrictEvent(
                event_type=etype,
                year=year,
                source_cdks=(parent,),
                target_cdks=tuple(children),
            )
            graph.add_event(event)

            # Nodes
            state_code = parent.split("_")[0] if "_" in parent else ""
            graph.add_node(DistrictNode(cdk=parent, state_code=state_code, valid_to=year))
            for c in children:
                cs = c.split("_")[0] if "_" in c else ""
                graph.add_node(DistrictNode(cdk=c, state_code=cs, valid_from=year))

        logger.info(
            f"LineageGraph from CSV: {len(graph._all_cdks)} nodes, "
            f"{len(graph._events)} events"
        )
        return graph

    # --- Queries ---

    @property
    def all_cdks(self) -> set[str]:
        """All known CDKs in the graph."""
        return self._all_cdks

    @property
    def events(self) -> list[DistrictEvent]:
        """All events, sorted chronologically."""
        return sorted(self._events, key=lambda e: e.year)

    def get_node(self, cdk: str) -> DistrictNode | None:
        return self._nodes.get(cdk)

    def get_children(self, cdk: str) -> list[DistrictEvent]:
        """Events where cdk is a source (forward traversal)."""
        return self._forward.get(cdk, [])

    def get_parents(self, cdk: str) -> list[DistrictEvent]:
        """Events where cdk is a target (inverse traversal)."""
        return self._inverse.get(cdk, [])

    def is_root(self, cdk: str) -> bool:
        """True if cdk has children but no parents in the graph."""
        return bool(self._forward.get(cdk)) and not bool(self._inverse.get(cdk))

    def is_leaf(self, cdk: str) -> bool:
        """True if cdk has no children (current modern district)."""
        return not bool(self._forward.get(cdk))

    def get_root_cdks(self) -> list[str]:
        """All CDKs that are root nodes (have children, no parents)."""
        return sorted([cdk for cdk in self._all_cdks if self.is_root(cdk)])

    def get_leaf_cdks(self) -> list[str]:
        """All CDKs that are leaf nodes (no children)."""
        return sorted([cdk for cdk in self._all_cdks if self.is_leaf(cdk)])

    def get_canonical_ancestors(
        self, cdk: str, target_year: int | None = None
    ) -> list[str]:
        """
        All historical districts that contributed area to this district.

        Traverses the inverse graph (child → parents) via BFS.
        If target_year is given, stops when reaching nodes from that era.
        """
        ancestors: list[str] = []
        visited: set[str] = set()
        queue: deque = deque([cdk])

        while queue:
            curr = queue.popleft()
            if curr in visited:
                continue
            visited.add(curr)

            parent_events = self._inverse.get(curr, [])
            if not parent_events:
                # This is a root — it's the ultimate ancestor
                if curr != cdk:
                    ancestors.append(curr)
                continue

            for event in parent_events:
                for src in event.source_cdks:
                    if src not in visited:
                        if target_year and event.year <= target_year:
                            ancestors.append(src)
                        else:
                            ancestors.append(src)
                            queue.append(src)

        return ancestors

    def get_canonical_descendants(
        self, cdk: str, from_year: int | None = None
    ) -> list[str]:
        """
        All modern districts that inherited area from this district.

        Traverses the forward graph (parent → children) via BFS.
        """
        descendants: list[str] = []
        visited: set[str] = set()
        queue: deque = deque([cdk])

        while queue:
            curr = queue.popleft()
            if curr in visited:
                continue
            visited.add(curr)

            child_events = self._forward.get(curr, [])
            if not child_events:
                # Leaf — this is a modern descendant
                if curr != cdk:
                    descendants.append(curr)
                continue

            for event in child_events:
                if from_year and event.year < from_year:
                    continue
                for tgt in event.target_cdks:
                    if tgt not in visited:
                        queue.append(tgt)

        return descendants

    def get_leaf_descendants(self, cdk: str) -> list[str]:
        """
        All leaf (modern) CDKs reachable from cdk.
        If cdk is itself a leaf, returns [cdk].
        """
        if self.is_leaf(cdk):
            return [cdk]

        leaves: list[str] = []
        visited: set[str] = set()
        queue: deque = deque([cdk])

        while queue:
            curr = queue.popleft()
            if curr in visited:
                continue
            visited.add(curr)

            child_events = self._forward.get(curr, [])
            if not child_events:
                leaves.append(curr)
            else:
                for event in child_events:
                    for tgt in event.target_cdks:
                        if tgt not in visited:
                            queue.append(tgt)

        return sorted(leaves)

    def get_subtree_events(self, root_cdk: str) -> list[DistrictEvent]:
        """
        All events in the subtree rooted at root_cdk, sorted by year.
        """
        events: list[DistrictEvent] = []
        visited_cdks: set[str] = set()
        queue: deque = deque([root_cdk])

        while queue:
            curr = queue.popleft()
            if curr in visited_cdks:
                continue
            visited_cdks.add(curr)

            for event in self._forward.get(curr, []):
                events.append(event)
                for tgt in event.target_cdks:
                    if tgt not in visited_cdks:
                        queue.append(tgt)

        return sorted(events, key=lambda e: e.year)

    def get_split_graph_compat(
        self,
    ) -> dict[str, list[tuple[list[str], int]]]:
        """
        Return a forward graph dict compatible with the existing
        epoch_builder.build_epochs() interface.

        { parent_cdk: [ ([child1, child2], split_year), ... ] }
        """
        compat: dict[str, list[tuple[list[str], int]]] = defaultdict(list)
        for event in self._events:
            if event.event_type in (
                EventType.SPLIT, EventType.RENAME,
                EventType.MERGE, EventType.STATE_TRANSFER,
            ):
                for src in event.source_cdks:
                    compat[src].append(
                        (list(event.target_cdks), event.year)
                    )
        return dict(compat)

    def validate_acyclicity(self) -> bool:
        """
        Verify the graph has no cycles (is a valid DAG).
        Uses Kahn's algorithm.
        """
        in_degree: dict[str, int] = defaultdict(int)
        for cdk in self._all_cdks:
            if cdk not in in_degree:
                in_degree[cdk] = 0
        for event in self._events:
            for tgt in event.target_cdks:
                in_degree[tgt] += 1

        queue: deque = deque(
            [cdk for cdk, deg in in_degree.items() if deg == 0]
        )
        visited = 0
        while queue:
            curr = queue.popleft()
            visited += 1
            for event in self._forward.get(curr, []):
                for tgt in event.target_cdks:
                    in_degree[tgt] -= 1
                    if in_degree[tgt] == 0:
                        queue.append(tgt)

        is_dag = visited == len(self._all_cdks)
        if not is_dag:
            logger.error(
                f"Graph has cycles! Visited {visited}/{len(self._all_cdks)} nodes"
            )
        return is_dag

    def summary(self) -> dict:
        """Graph statistics for debugging."""
        roots = self.get_root_cdks()
        leaves = self.get_leaf_cdks()
        event_type_counts = defaultdict(int)
        for e in self._events:
            event_type_counts[e.event_type.value] += 1
        return {
            "total_nodes": len(self._all_cdks),
            "total_events": len(self._events),
            "root_nodes": len(roots),
            "leaf_nodes": len(leaves),
            "event_types": dict(event_type_counts),
        }
