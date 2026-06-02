"""
Tests for the NDVI-enhanced Yield Backcaster.
"""

import pytest

from app.ml.yield_backcaster import (
    NDVIDataset,
    NDVIRecord,
    YieldBackcaster,
)
from app.schemas.backcast import BackcastYearPoint


# ---------------------------------------------------------------------------
# NDVIDataset Tests
# ---------------------------------------------------------------------------


class TestNDVIDataset:
    """Tests for the NDVIDataset data class."""

    def test_empty_dataset_has_no_data(self):
        ds = NDVIDataset()
        assert ds.has_data is False
        assert ds.overlap_years == []

    def test_partial_dataset_has_no_data(self):
        ds = NDVIDataset(
            child_ndvi={2010: NDVIRecord(2010, 0.6, 0.8, 120)},
            parent_ndvi={},
        )
        assert ds.has_data is False

    def test_full_dataset_has_data(self):
        ds = NDVIDataset(
            child_ndvi={2010: NDVIRecord(2010, 0.6, 0.8, 120)},
            parent_ndvi={2010: NDVIRecord(2010, 0.7, 0.85, 130)},
        )
        assert ds.has_data is True
        assert ds.overlap_years == [2010]

    def test_overlap_years(self):
        ds = NDVIDataset(
            child_ndvi={
                2008: NDVIRecord(2008, 0.5, 0.7, 100),
                2010: NDVIRecord(2010, 0.6, 0.8, 120),
                2012: NDVIRecord(2012, 0.55, 0.75, 110),
            },
            parent_ndvi={
                2009: NDVIRecord(2009, 0.65, 0.82, 125),
                2010: NDVIRecord(2010, 0.7, 0.85, 130),
                2012: NDVIRecord(2012, 0.68, 0.83, 128),
            },
        )
        assert ds.overlap_years == [2010, 2012]


# ---------------------------------------------------------------------------
# NDVI-Weighted Prediction Tests
# ---------------------------------------------------------------------------


class TestNDVIWeightedPrediction:
    """Tests for the _predict_ndvi_weighted method."""

    def test_ndvi_weighted_basic(self):
        """When we have NDVI for child and parent, yields should scale by NDVI ratio."""
        from app.ml.backcast_data_pipeline import BackcastTrainingData

        backcaster = YieldBackcaster()

        # Simulate training data
        data = BackcastTrainingData(
            child_yields={2015: 2000.0, 2016: 2200.0, 2017: 1800.0},
            parent_yields={
                2000: 3000.0, 2001: 3100.0, 2002: 2900.0,  # pre-split
                2015: 3500.0, 2016: 3600.0, 2017: 3400.0,  # post-split overlap
            },
            sibling_yields={},
            parent_areas={},
            climate={},
            area_ratio=0.4,
        )

        # NDVI data showing child has ~60% of parent's vegetation
        ndvi = NDVIDataset(
            child_ndvi={
                2000: NDVIRecord(2000, 0.42, 0.6, 100),
                2001: NDVIRecord(2001, 0.43, 0.62, 105),
                2002: NDVIRecord(2002, 0.41, 0.58, 98),
                2015: NDVIRecord(2015, 0.45, 0.65, 110),
                2016: NDVIRecord(2016, 0.46, 0.66, 112),
                2017: NDVIRecord(2017, 0.44, 0.63, 108),
            },
            parent_ndvi={
                2000: NDVIRecord(2000, 0.70, 0.85, 130),
                2001: NDVIRecord(2001, 0.72, 0.87, 132),
                2002: NDVIRecord(2002, 0.69, 0.84, 128),
                2015: NDVIRecord(2015, 0.73, 0.88, 135),
                2016: NDVIRecord(2016, 0.74, 0.89, 136),
                2017: NDVIRecord(2017, 0.72, 0.86, 133),
            },
        )

        result = backcaster._predict_ndvi_weighted(
            child_cdk="CHILD_01",
            target_years=range(2000, 2003),
            data=data,
            ndvi=ndvi,
        )

        assert result.child_cdk == "CHILD_01"
        assert len(result.backcasted_yields) == 3
        assert all(yp.method == "ndvi_weighted" for yp in result.backcasted_yields)
        assert all(yp.predicted_yield > 0 for yp in result.backcasted_yields)
        # NDVI ratio is ~0.6, so child yields should be roughly 60% of parent
        for yp in result.backcasted_yields:
            assert 1000 < yp.predicted_yield < 3000

        # Check model stats
        assert "calibration_factor" in result.model_stats
        assert "ndvi_ratio" in result.features_used

    def test_ndvi_fallback_to_area_when_ndvi_missing(self):
        """Years without NDVI should fall back to area_apportionment_fallback."""
        from app.ml.backcast_data_pipeline import BackcastTrainingData

        backcaster = YieldBackcaster()

        data = BackcastTrainingData(
            child_yields={2015: 2000.0},
            parent_yields={1990: 3000.0, 2015: 3500.0},
            sibling_yields={},
            parent_areas={},
            climate={},
            area_ratio=0.5,
        )

        # Only have NDVI for 2015 (post-split), not 1990
        ndvi = NDVIDataset(
            child_ndvi={2015: NDVIRecord(2015, 0.5, 0.7, 110)},
            parent_ndvi={2015: NDVIRecord(2015, 0.7, 0.85, 130)},
        )

        result = backcaster._predict_ndvi_weighted(
            child_cdk="CHILD_02",
            target_years=range(1990, 1991),
            data=data,
            ndvi=ndvi,
        )

        assert len(result.backcasted_yields) == 1
        # Should use area_apportionment_fallback since no NDVI for 1990
        assert result.backcasted_yields[0].method == "area_apportionment_fallback"
        # With area_ratio 0.5, predicted = 3000 * 0.5 = 1500
        assert abs(result.backcasted_yields[0].predicted_yield - 1500.0) < 1.0
