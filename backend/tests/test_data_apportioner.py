"""Tests for DataApportioner (hybrid apportionment with conservation)."""
import pytest
from app.core.lineage_graph import (
    DistrictEvent,
    EventType,
    LineageGraph,
)
from app.core.data_apportioner import DataApportioner, ConservationResult


# ---------------------------------------------------------------------------
# Single-hop apportionment
# ---------------------------------------------------------------------------

class TestApportionToModern:
    def test_equal_split(self):
        ap = DataApportioner()
        event = DistrictEvent(
            EventType.SPLIT, 1980, ("A",), ("B", "C")
        )
        result = ap.apportion_to_modern(
            {"A": 1000.0}, event, mode="equal_split"
        )
        assert result["B"].value == pytest.approx(500.0)
        assert result["C"].value == pytest.approx(500.0)

    def test_area_weighted_with_ratios(self):
        ap = DataApportioner()
        event = DistrictEvent(
            EventType.SPLIT, 1980, ("A",), ("B", "C")
        )
        result = ap.apportion_to_modern(
            {"A": 1000.0}, event, mode="area_weighted",
            area_ratios={"B": 0.3, "C": 0.7},
        )
        assert result["B"].value == pytest.approx(300.0)
        assert result["C"].value == pytest.approx(700.0)

    def test_rename_passthrough(self):
        ap = DataApportioner()
        event = DistrictEvent(
            EventType.RENAME, 1991, ("A",), ("B",)
        )
        result = ap.apportion_to_modern({"A": 42.0}, event)
        assert result["B"].value == pytest.approx(42.0)
        assert result["B"].method == "rename_passthrough"
        assert result["B"].confidence == 1.0

    def test_three_way_split_equal(self):
        ap = DataApportioner()
        event = DistrictEvent(
            EventType.SPLIT, 2000, ("P",), ("X", "Y", "Z")
        )
        result = ap.apportion_to_modern(
            {"P": 900.0}, event, mode="equal_split"
        )
        assert result["X"].value == pytest.approx(300.0)
        assert result["Y"].value == pytest.approx(300.0)
        assert result["Z"].value == pytest.approx(300.0)

    def test_population_weighted(self):
        ap = DataApportioner()
        event = DistrictEvent(
            EventType.SPLIT, 2014, ("AP",), ("TG", "AP2")
        )
        result = ap.apportion_to_modern(
            {"AP": 1000.0}, event, mode="population_weighted",
            population_ratios={"TG": 4000000, "AP2": 6000000},
        )
        assert result["TG"].value == pytest.approx(400.0)
        assert result["AP2"].value == pytest.approx(600.0)

    def test_coverage_values(self):
        ap = DataApportioner()
        event = DistrictEvent(
            EventType.SPLIT, 1980, ("A",), ("B", "C")
        )
        result = ap.apportion_to_modern(
            {"A": 100.0}, event, mode="area_weighted",
            area_ratios={"B": 0.4, "C": 0.6},
        )
        assert result["B"].coverage == pytest.approx(0.4)
        assert result["C"].coverage == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Conservation validation
# ---------------------------------------------------------------------------

class TestConservation:
    def test_valid_conservation(self):
        ap = DataApportioner()
        result = ap.validate_conservation(
            {"A": 1000.0},
            {"B": 500.0, "C": 500.0},
        )
        assert result.is_valid is True
        assert result.absolute_error == 0.0

    def test_minor_float_error_ok(self):
        ap = DataApportioner(tolerance=0.01)
        result = ap.validate_conservation(
            {"A": 1000.0},
            {"B": 499.95, "C": 500.0},  # 0.005% error
        )
        assert result.is_valid is True

    def test_conservation_violation(self):
        ap = DataApportioner(tolerance=0.01)
        result = ap.validate_conservation(
            {"A": 1000.0},
            {"B": 400.0, "C": 500.0},  # 10% missing
        )
        assert result.is_valid is False
        assert result.relative_error > 0.01

    def test_conservation_with_apportionment(self):
        """Equal split should always conserve."""
        ap = DataApportioner()
        event = DistrictEvent(EventType.SPLIT, 2000, ("P",), ("X", "Y"))
        result = ap.apportion_to_modern({"P": 1000.0}, event, mode="equal_split")
        after = {k: v.value for k, v in result.items()}
        cr = ap.validate_conservation({"P": 1000.0}, after)
        assert cr.is_valid is True

    def test_conservation_with_area_weighted(self):
        ap = DataApportioner()
        event = DistrictEvent(EventType.SPLIT, 2000, ("P",), ("X", "Y", "Z"))
        result = ap.apportion_to_modern(
            {"P": 1000.0}, event, mode="area_weighted",
            area_ratios={"X": 100, "Y": 200, "Z": 300},
        )
        after = {k: v.value for k, v in result.items()}
        cr = ap.validate_conservation({"P": 1000.0}, after)
        assert cr.is_valid is True


# ---------------------------------------------------------------------------
# Cascading multi-hop apportionment
# ---------------------------------------------------------------------------

class TestCascade:
    def test_single_hop_cascade(self):
        g = LineageGraph()
        g.add_event(DistrictEvent(EventType.SPLIT, 1980, ("A",), ("B", "C")))

        ap = DataApportioner()
        result = ap.apportion_cascade("A", {1975: 1000.0}, g)
        # 1975 data should be split equally to B and C (no ratios)
        assert "B" in result
        assert "C" in result
        assert result["B"][1975] == pytest.approx(500.0)
        assert result["C"][1975] == pytest.approx(500.0)

    def test_cascade_data_after_split_stays(self):
        g = LineageGraph()
        g.add_event(DistrictEvent(EventType.SPLIT, 1980, ("A",), ("B", "C")))

        ap = DataApportioner()
        result = ap.apportion_cascade("A", {1985: 500.0}, g)
        # 1985 is after the split → data stays with A
        assert "A" in result
        assert result["A"][1985] == 500.0

    def test_two_hop_cascade(self):
        g = LineageGraph()
        g.add_event(DistrictEvent(EventType.SPLIT, 1980, ("A",), ("B", "C")))
        g.add_event(DistrictEvent(EventType.SPLIT, 1990, ("C",), ("D", "E")))

        ap = DataApportioner()
        result = ap.apportion_cascade("A", {1970: 1200.0}, g)
        # A(1200) → B(600) + C(600) → B(600) + D(300) + E(300)
        assert result["B"][1970] == pytest.approx(600.0)
        assert result["D"][1970] == pytest.approx(300.0)
        assert result["E"][1970] == pytest.approx(300.0)

    def test_cascade_conservation(self):
        g = LineageGraph()
        g.add_event(DistrictEvent(EventType.SPLIT, 1980, ("A",), ("B", "C")))
        g.add_event(DistrictEvent(EventType.SPLIT, 1990, ("C",), ("D", "E")))

        ap = DataApportioner()
        result = ap.apportion_cascade("A", {1970: 1200.0}, g)
        total = sum(result[cdk][1970] for cdk in result if 1970 in result[cdk])
        assert total == pytest.approx(1200.0)


# ---------------------------------------------------------------------------
# Collective yield aggregation
# ---------------------------------------------------------------------------

class TestCollectiveYield:
    def test_full_coverage(self):
        ap = DataApportioner()
        data = {
            "B": {"rice_production": 100, "rice_area": 50},
            "C": {"rice_production": 300, "rice_area": 150},
        }
        r = ap.aggregate_collective_yield(data, ["B", "C"], "rice")
        assert r["yield"] == pytest.approx(2000.0)
        assert r["production"] == 400.0
        assert r["area"] == 200.0
        assert r["coverage"] == 1.0

    def test_partial_coverage(self):
        ap = DataApportioner()
        data = {
            "B": {"rice_production": 100, "rice_area": 50},
            # C has no data
        }
        r = ap.aggregate_collective_yield(data, ["B", "C", "D"], "rice")
        assert r["coverage"] == pytest.approx(1 / 3, abs=0.001)

    def test_zero_data(self):
        ap = DataApportioner()
        r = ap.aggregate_collective_yield({}, ["B", "C"], "rice")
        assert r["yield"] is None
        assert r["coverage"] == 0.0


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

class TestConfidence:
    def test_rename_highest_confidence(self):
        ap = DataApportioner()
        event = DistrictEvent(EventType.RENAME, 1991, ("A",), ("B",))
        result = ap.apportion_to_modern({"A": 42.0}, event)
        assert result["B"].confidence == 1.0

    def test_equal_split_lowest_confidence(self):
        ap = DataApportioner()
        event = DistrictEvent(EventType.SPLIT, 1980, ("A",), ("B", "C"))
        result = ap.apportion_to_modern({"A": 100.0}, event, mode="equal_split")
        assert result["B"].confidence == 0.4
