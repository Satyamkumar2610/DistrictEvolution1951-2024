"""
Tests for the AdminGraph and harmonizer.

Uses the classic Adilabad → Adilabad (new) + Nirmal split as the primary
test fixture: 55/45 area split with 0.9 confidence on 11 Oct 2016.
"""

import pytest
from datetime import date

from pipeline.lib.admin_graph import AdminGraph, AdminUnit, AdminTransition
from pipeline.lib.harmonizer import harmonize_value


@pytest.fixture
def adilabad_split_graph():
    """
    Graph fixture representing the 2016 Adilabad split:
      Adilabad (old, 1950–2016) → Adilabad (new, 2016–) + Nirmal (2016–)
      Area split: 55% / 45%, confidence: 0.9
    """
    graph = AdminGraph()
    graph.units = {
        "adilabad-old": AdminUnit(
            "adilabad-old",
            "Adilabad",
            "Telangana",
            date(1950, 1, 1),
            date(2016, 10, 11),
        ),
        "adilabad-new": AdminUnit(
            "adilabad-new",
            "Adilabad",
            "Telangana",
            date(2016, 10, 11),
            None,
        ),
        "nirmal": AdminUnit(
            "nirmal",
            "Nirmal",
            "Telangana",
            date(2016, 10, 11),
            None,
        ),
    }
    graph.transitions = [
        AdminTransition(
            "e1",
            "adilabad-old",
            "adilabad-new",
            "SPLIT",
            date(2016, 10, 11),
            area_weight=0.55,
            confidence=0.9,
        ),
        AdminTransition(
            "e2",
            "adilabad-old",
            "nirmal",
            "SPLIT",
            date(2016, 10, 11),
            area_weight=0.45,
            confidence=0.9,
        ),
    ]
    return graph


class TestAdminGraph:
    """Tests for the AdminGraph data structure."""

    def test_split_weights_sum_to_one(self, adilabad_split_graph):
        """Area weights from a single parent must sum to 1.0."""
        graph = adilabad_split_graph
        edges_from_old = [
            t for t in graph.transitions if t.from_unit_id == "adilabad-old"
        ]
        total_weight = sum(e.area_weight for e in edges_from_old)
        assert abs(total_weight - 1.0) < 0.001

    def test_ancestors_returns_parent(self, adilabad_split_graph):
        """Nirmal's ancestor at 1975 should include Adilabad (old)."""
        ancestors = adilabad_split_graph.ancestors("nirmal", at_year=1975)
        names = [a.name for a in ancestors]
        assert "Adilabad" in names

    def test_ancestors_returns_empty_for_root(self, adilabad_split_graph):
        """The root unit should have no ancestors."""
        ancestors = adilabad_split_graph.ancestors(
            "adilabad-old", at_year=1950
        )
        assert len(ancestors) == 0

    def test_apportionment_chain_for_child(self, adilabad_split_graph):
        """Nirmal at 1975 should have one edge back to Adilabad (old)."""
        chain = adilabad_split_graph.apportionment_chain("nirmal", 1975)
        assert len(chain) == 1
        assert chain[0].from_unit_id == "adilabad-old"
        assert chain[0].to_unit_id == "nirmal"
        assert chain[0].area_weight == 0.45

    def test_apportionment_chain_empty_for_existing_unit(
        self, adilabad_split_graph
    ):
        """A unit that existed at target_year needs no apportionment."""
        chain = adilabad_split_graph.apportionment_chain(
            "adilabad-old", 1975
        )
        assert chain == []

    def test_children_of(self, adilabad_split_graph):
        """Adilabad (old) should have two outgoing transitions."""
        children = adilabad_split_graph.children_of("adilabad-old")
        assert len(children) == 2

    def test_parents_of(self, adilabad_split_graph):
        """Nirmal should have one incoming transition."""
        parents = adilabad_split_graph.parents_of("nirmal")
        assert len(parents) == 1

    def test_active_units_at_year(self, adilabad_split_graph):
        """At 2020, only adilabad-new and nirmal should be active."""
        active = adilabad_split_graph.active_units_at(2020)
        names = sorted([u.name for u in active])
        assert names == ["Adilabad", "Nirmal"]

    def test_active_units_at_historical_year(self, adilabad_split_graph):
        """At 1990, only adilabad-old should be active."""
        active = adilabad_split_graph.active_units_at(1990)
        assert len(active) == 1
        assert active[0].id == "adilabad-old"

    def test_get_unit_by_name(self, adilabad_split_graph):
        """Should find Nirmal by name."""
        unit = adilabad_split_graph.get_unit_by_name("Nirmal")
        assert unit is not None
        assert unit.id == "nirmal"

    def test_get_unit_by_name_with_state(self, adilabad_split_graph):
        """Should find Nirmal filtered by state."""
        unit = adilabad_split_graph.get_unit_by_name("Nirmal", "Telangana")
        assert unit is not None

    def test_get_unit_by_name_wrong_state(self, adilabad_split_graph):
        """Should return None for wrong state."""
        unit = adilabad_split_graph.get_unit_by_name("Nirmal", "Karnataka")
        assert unit is None


class TestHarmonizer:
    """Tests for the harmonize_value function."""

    def test_harmonized_value_applies_area_weight(self, adilabad_split_graph):
        """Area-weighted value for Nirmal should be 45% of parent's value."""
        result = harmonize_value(
            adilabad_split_graph,
            "nirmal",
            1975,
            "adilabad-old",
            1975,
            raw_value=1000.0,
        )
        assert result.is_harmonized is True
        assert abs(result.value - 450.0) < 0.01  # 1000 * 0.45

    def test_confidence_degrades_through_chain(self, adilabad_split_graph):
        """Cumulative confidence should equal the edge confidence."""
        result = harmonize_value(
            adilabad_split_graph,
            "nirmal",
            1975,
            "adilabad-old",
            1975,
            raw_value=1000.0,
        )
        assert result.cumulative_confidence == pytest.approx(0.9, abs=0.001)

    def test_direct_measurement_unchanged(self, adilabad_split_graph):
        """Direct measurement (same unit) should pass through untouched."""
        result = harmonize_value(
            adilabad_split_graph,
            "nirmal",
            2020,
            "nirmal",
            2020,
            raw_value=500.0,
        )
        assert result.is_harmonized is False
        assert result.value == 500.0
        assert result.cumulative_confidence == 1.0
        assert result.provenance_path == []

    def test_provenance_path_contains_edge_id(self, adilabad_split_graph):
        """Provenance path should contain the transition edge ID."""
        result = harmonize_value(
            adilabad_split_graph,
            "nirmal",
            1975,
            "adilabad-old",
            1975,
            raw_value=1000.0,
        )
        assert "e2" in result.provenance_path

    def test_parent_district_name_set(self, adilabad_split_graph):
        """Parent district name should be set for harmonized values."""
        result = harmonize_value(
            adilabad_split_graph,
            "nirmal",
            1975,
            "adilabad-old",
            1975,
            raw_value=1000.0,
        )
        assert result.parent_district_name == "Adilabad"

    def test_adilabad_new_gets_55_percent(self, adilabad_split_graph):
        """Adilabad (new) should get 55% of the parent's value."""
        result = harmonize_value(
            adilabad_split_graph,
            "adilabad-new",
            1975,
            "adilabad-old",
            1975,
            raw_value=1000.0,
        )
        assert abs(result.value - 550.0) < 0.01
        assert result.is_harmonized is True

    def test_values_sum_to_original(self, adilabad_split_graph):
        """Sum of harmonized children should equal the parent's value."""
        nirmal = harmonize_value(
            adilabad_split_graph,
            "nirmal",
            1975,
            "adilabad-old",
            1975,
            raw_value=1000.0,
        )
        adilabad_new = harmonize_value(
            adilabad_split_graph,
            "adilabad-new",
            1975,
            "adilabad-old",
            1975,
            raw_value=1000.0,
        )
        total = nirmal.value + adilabad_new.value
        assert abs(total - 1000.0) < 0.01


class TestMultiHopGraph:
    """Tests for chains that traverse multiple split events."""

    @pytest.fixture
    def two_hop_graph(self):
        """
        A → B + C (2000), then B → D + E (2010)
        A(1950–2000), B(2000–2010), C(2000–), D(2010–), E(2010–)
        """
        graph = AdminGraph()
        graph.units = {
            "a": AdminUnit("a", "A-District", "State", date(1950, 1, 1), date(2000, 1, 1)),
            "b": AdminUnit("b", "B-District", "State", date(2000, 1, 1), date(2010, 1, 1)),
            "c": AdminUnit("c", "C-District", "State", date(2000, 1, 1), None),
            "d": AdminUnit("d", "D-District", "State", date(2010, 1, 1), None),
            "e": AdminUnit("e", "E-District", "State", date(2010, 1, 1), None),
        }
        graph.transitions = [
            AdminTransition("t1", "a", "b", "SPLIT", date(2000, 1, 1), 0.6, 0.9),
            AdminTransition("t2", "a", "c", "SPLIT", date(2000, 1, 1), 0.4, 0.9),
            AdminTransition("t3", "b", "d", "SPLIT", date(2010, 1, 1), 0.7, 0.85),
            AdminTransition("t4", "b", "e", "SPLIT", date(2010, 1, 1), 0.3, 0.85),
        ]
        return graph

    def test_two_hop_chain_length(self, two_hop_graph):
        """D at 1980 should require two hops: A → B → D."""
        chain = two_hop_graph.apportionment_chain("d", 1980)
        assert len(chain) == 2

    def test_two_hop_value(self, two_hop_graph):
        """D's value should be: 1000 * 0.6 * 0.7 = 420."""
        result = harmonize_value(
            two_hop_graph, "d", 1980, "a", 1980, raw_value=1000.0
        )
        assert abs(result.value - 420.0) < 0.01

    def test_two_hop_confidence(self, two_hop_graph):
        """Confidence should be: 0.9 * 0.85 = 0.765."""
        result = harmonize_value(
            two_hop_graph, "d", 1980, "a", 1980, raw_value=1000.0
        )
        assert result.cumulative_confidence == pytest.approx(0.765, abs=0.001)

    def test_two_hop_provenance(self, two_hop_graph):
        """Provenance path should contain both edge IDs in order."""
        result = harmonize_value(
            two_hop_graph, "d", 1980, "a", 1980, raw_value=1000.0
        )
        assert result.provenance_path == ["t1", "t3"]
