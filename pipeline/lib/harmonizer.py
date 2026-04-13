"""
Graph-based harmonizer for I-ASCAP.

Replaces the old BoundaryHarmonizer with a simpler, graph-traversal approach:
1. Walk the AdminGraph to find the apportionment chain from ancestor → target unit
2. Multiply through area_weight edges to compute the harmonized value
3. Multiply through confidence edges to compute cumulative confidence
4. Record the full provenance path (list of transition edge IDs)
"""

from __future__ import annotations

from dataclasses import dataclass

from .admin_graph import AdminGraph, AdminTransition


@dataclass
class HarmonizedResult:
    """Result of harmonizing a raw measurement to a target unit."""

    value: float
    is_harmonized: bool
    provenance_path: list[str]  # ordered list of transition edge IDs
    cumulative_confidence: float
    parent_district_name: str | None  # human-readable, for AI citations


def harmonize_value(
    graph: AdminGraph,
    unit_id: str,
    target_year: int,
    raw_unit_id: str,
    raw_year: int,
    raw_value: float,
) -> HarmonizedResult:
    """
    Given a raw measurement (raw_value at raw_year for raw_unit_id),
    apportion it to unit_id at target_year using the graph's edge weights.

    If unit_id == raw_unit_id, the value is a direct measurement (no
    harmonization needed). Otherwise, walk the apportionment chain and
    multiply through area weights and confidence scores.

    Args:
        graph: The AdminGraph with all units and transitions loaded.
        unit_id: Target district UUID to compute the value for.
        target_year: Year context for the apportionment.
        raw_unit_id: Source district UUID where the measurement was taken.
        raw_year: Year the measurement was recorded.
        raw_value: The raw measurement value.

    Returns:
        HarmonizedResult with the apportioned value, provenance, and confidence.

    Raises:
        ValueError: If no apportionment chain exists between the units.
    """
    # Direct measurement — no harmonization needed
    if unit_id == raw_unit_id:
        return HarmonizedResult(
            value=raw_value,
            is_harmonized=False,
            provenance_path=[],
            cumulative_confidence=1.0,
            parent_district_name=None,
        )

    # Walk the graph to find the apportionment chain
    chain: list[AdminTransition] = graph.apportionment_chain(
        unit_id, target_year
    )
    if not chain:
        raise ValueError(
            f"No apportionment chain found from {raw_unit_id} to {unit_id}"
        )

    # Multiply through area weights and confidence scores
    value = raw_value
    confidence = 1.0
    for edge in chain:
        value *= edge.area_weight
        confidence *= edge.confidence

    # Get the root ancestor name for human-readable provenance
    parent = graph.units.get(chain[0].from_unit_id)

    return HarmonizedResult(
        value=value,
        is_harmonized=True,
        provenance_path=[edge.id for edge in chain],
        cumulative_confidence=round(confidence, 4),
        parent_district_name=parent.name if parent else None,
    )
