"""Tests for LineageGraph (DAG-based district lineage tracking)."""
from app.core.lineage_graph import (
    DistrictEvent,
    EventType,
    LineageGraph,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_simple_graph() -> LineageGraph:
    """A splits into B+C in 1980; C splits into D+E in 1990."""
    g = LineageGraph()
    g.add_event(DistrictEvent(
        event_type=EventType.SPLIT, year=1980,
        source_cdks=("A",), target_cdks=("B", "C"),
    ))
    g.add_event(DistrictEvent(
        event_type=EventType.SPLIT, year=1990,
        source_cdks=("C",), target_cdks=("D", "E"),
    ))
    return g


def make_rename_graph() -> LineageGraph:
    """A renamed to B in 1991."""
    g = LineageGraph()
    g.add_event(DistrictEvent(
        event_type=EventType.RENAME, year=1991,
        source_cdks=("A",), target_cdks=("B",),
    ))
    return g


def make_merge_graph() -> LineageGraph:
    """X and Y merge into Z in 2000."""
    g = LineageGraph()
    g.add_event(DistrictEvent(
        event_type=EventType.MERGE, year=2000,
        source_cdks=("X", "Y"), target_cdks=("Z",),
    ))
    return g


def make_complex_graph() -> LineageGraph:
    """
    Delhi lineage:
      DL_delhi_1951 → SPLIT(1961) → DL_delhi_1961 + DL_newdel_1961
      DL_delhi_1961 → RENAME(1991) → DL_delhi_1991
      DL_delhi_1991 → SPLIT(2001) → DL_northw_2001 + DL_south_2001 + DL_east_2001
    """
    g = LineageGraph()
    g.add_event(DistrictEvent(
        event_type=EventType.SPLIT, year=1961,
        source_cdks=("DL_delhi_1951",),
        target_cdks=("DL_delhi_1961", "DL_newdel_1961"),
    ))
    g.add_event(DistrictEvent(
        event_type=EventType.RENAME, year=1991,
        source_cdks=("DL_delhi_1961",),
        target_cdks=("DL_delhi_1991",),
    ))
    g.add_event(DistrictEvent(
        event_type=EventType.SPLIT, year=2001,
        source_cdks=("DL_delhi_1991",),
        target_cdks=("DL_northw_2001", "DL_south_2001", "DL_east_2001"),
    ))
    return g


# ---------------------------------------------------------------------------
# EventType
# ---------------------------------------------------------------------------

class TestEventType:
    def test_all_types_exist(self):
        assert len(EventType) == 7

    def test_string_values(self):
        assert EventType.SPLIT.value == "SPLIT"
        assert EventType.MERGE.value == "MERGE"
        assert EventType.RENAME.value == "RENAME"
        assert EventType.STATE_TRANSFER.value == "STATE_TRANSFER"


# ---------------------------------------------------------------------------
# DistrictEvent
# ---------------------------------------------------------------------------

class TestDistrictEvent:
    def test_split_label(self):
        e = DistrictEvent(EventType.SPLIT, 1980, ("A",), ("B", "C"))
        assert "A" in e.label
        assert "1980" in e.label

    def test_rename_label(self):
        e = DistrictEvent(EventType.RENAME, 1991, ("A",), ("B",))
        assert "renamed" in e.label

    def test_merge_label(self):
        e = DistrictEvent(EventType.MERGE, 2000, ("X", "Y"), ("Z",))
        assert "merged" in e.label

    def test_frozen_hashable(self):
        e = DistrictEvent(EventType.SPLIT, 1980, ("A",), ("B", "C"))
        hash(e)  # should be hashable


# ---------------------------------------------------------------------------
# LineageGraph construction
# ---------------------------------------------------------------------------

class TestLineageGraphConstruction:
    def test_add_event(self):
        g = make_simple_graph()
        assert len(g.events) == 2

    def test_deduplication(self):
        g = LineageGraph()
        e = DistrictEvent(EventType.SPLIT, 1980, ("A",), ("B", "C"))
        assert g.add_event(e) is True
        assert g.add_event(e) is False  # duplicate
        assert len(g.events) == 1

    def test_continuity_not_stored_as_edge(self):
        g = LineageGraph()
        e = DistrictEvent(EventType.CONTINUITY, 1981, ("A",), ("A",))
        g.add_event(e)
        assert len(g.events) == 0  # continuity events don't create edges
        assert "A" in g.all_cdks   # but the CDK is registered

    def test_from_split_events(self):
        rows = [
            {"parent_cdk": "A", "child_cdks": ["B", "C"], "split_year": 1980},
            {"parent_cdk": "C", "child_cdks": ["D", "E"], "split_year": 1990},
        ]
        g = LineageGraph.from_split_events(rows)
        assert len(g.events) == 2
        assert len(g.all_cdks) == 5

    def test_from_split_events_with_duplicates(self):
        """Simulates the real data where Manipur has 16 identical rows."""
        rows = [
            {"parent_cdk": "MN_manipu_1951", "child_cdks": ["MN_manipu_1951"],
             "split_year": 1971, "event_type": "CONTINUITY"},
        ] * 16
        g = LineageGraph.from_split_events(rows)
        # All 16 duplicates should be deduped to 0 events (continuity)
        assert len(g.events) == 0
        assert "MN_manipu_1951" in g.all_cdks

    def test_implicit_rename_detection(self):
        """1 parent → 1 different child labeled as SPLIT should be RENAME."""
        rows = [
            {"parent_cdk": "WB_hooghl_1971", "child_cdks": ["WB_hugli_1981"],
             "split_year": 1981},
        ]
        g = LineageGraph.from_split_events(rows)
        assert g.events[0].event_type == EventType.RENAME

    def test_from_csv_rows(self):
        rows = [
            {"parent_cdk": "A", "child_cdk": "B", "event_year": 1980, "event_type": "SPLIT"},
            {"parent_cdk": "A", "child_cdk": "C", "event_year": 1980, "event_type": "SPLIT"},
            {"parent_cdk": "A", "child_cdk": "B", "event_year": 1980, "event_type": "SPLIT"},  # dup
        ]
        g = LineageGraph.from_csv_rows(rows)
        assert len(g.events) == 1
        assert set(g.events[0].target_cdks) == {"B", "C"}


# ---------------------------------------------------------------------------
# Graph queries
# ---------------------------------------------------------------------------

class TestLineageGraphQueries:
    def test_is_root(self):
        g = make_simple_graph()
        assert g.is_root("A") is True
        assert g.is_root("B") is False
        assert g.is_root("D") is False

    def test_is_leaf(self):
        g = make_simple_graph()
        assert g.is_leaf("A") is False
        assert g.is_leaf("B") is True
        assert g.is_leaf("D") is True
        assert g.is_leaf("E") is True

    def test_get_root_cdks(self):
        g = make_simple_graph()
        assert g.get_root_cdks() == ["A"]

    def test_get_leaf_cdks(self):
        g = make_simple_graph()
        assert set(g.get_leaf_cdks()) == {"B", "D", "E"}

    def test_get_children(self):
        g = make_simple_graph()
        children_events = g.get_children("A")
        assert len(children_events) == 1
        assert set(children_events[0].target_cdks) == {"B", "C"}

    def test_get_parents(self):
        g = make_simple_graph()
        parent_events = g.get_parents("C")
        assert len(parent_events) == 1
        assert parent_events[0].source_cdks == ("A",)


# ---------------------------------------------------------------------------
# Ancestor / descendant queries
# ---------------------------------------------------------------------------

class TestAncestorDescendant:
    def test_get_canonical_ancestors_simple(self):
        g = make_simple_graph()
        anc = g.get_canonical_ancestors("D")
        assert "C" in anc
        assert "A" in anc

    def test_get_canonical_ancestors_leaf(self):
        g = make_simple_graph()
        anc = g.get_canonical_ancestors("B")
        assert "A" in anc

    def test_get_canonical_descendants_simple(self):
        g = make_simple_graph()
        desc = g.get_canonical_descendants("A")
        assert set(desc) == {"B", "D", "E"}

    def test_get_canonical_descendants_mid_node(self):
        g = make_simple_graph()
        desc = g.get_canonical_descendants("C")
        assert set(desc) == {"D", "E"}

    def test_get_leaf_descendants(self):
        g = make_simple_graph()
        leaves = g.get_leaf_descendants("A")
        assert set(leaves) == {"B", "D", "E"}

    def test_get_leaf_descendants_of_leaf(self):
        g = make_simple_graph()
        assert g.get_leaf_descendants("B") == ["B"]

    def test_complex_delhi_ancestors(self):
        g = make_complex_graph()
        anc = g.get_canonical_ancestors("DL_east_2001")
        assert "DL_delhi_1991" in anc
        assert "DL_delhi_1961" in anc
        assert "DL_delhi_1951" in anc

    def test_complex_delhi_descendants(self):
        g = make_complex_graph()
        desc = g.get_canonical_descendants("DL_delhi_1951")
        assert "DL_newdel_1961" in desc
        assert "DL_northw_2001" in desc
        assert "DL_south_2001" in desc
        assert "DL_east_2001" in desc


# ---------------------------------------------------------------------------
# Subtree and compatibility
# ---------------------------------------------------------------------------

class TestSubtreeAndCompat:
    def test_get_subtree_events(self):
        g = make_simple_graph()
        events = g.get_subtree_events("A")
        assert len(events) == 2
        assert events[0].year <= events[1].year

    def test_get_subtree_events_partial(self):
        g = make_simple_graph()
        events = g.get_subtree_events("C")
        assert len(events) == 1
        assert events[0].year == 1990

    def test_split_graph_compat(self):
        g = make_simple_graph()
        compat = g.get_split_graph_compat()
        assert "A" in compat
        assert len(compat["A"]) == 1
        assert set(compat["A"][0][0]) == {"B", "C"}
        assert compat["A"][0][1] == 1980


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_acyclicity_valid(self):
        g = make_simple_graph()
        assert g.validate_acyclicity() is True

    def test_summary(self):
        g = make_simple_graph()
        s = g.summary()
        assert s["total_nodes"] == 5
        assert s["total_events"] == 2
        assert s["root_nodes"] == 1
        assert s["leaf_nodes"] == 3

    def test_merge_graph_queries(self):
        g = make_merge_graph()
        assert g.is_leaf("Z") is True
        assert g.is_root("X") is True
        assert g.is_root("Y") is True
        desc = g.get_canonical_descendants("X")
        assert "Z" in desc
