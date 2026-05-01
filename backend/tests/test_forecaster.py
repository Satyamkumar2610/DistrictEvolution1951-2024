"""
Tests for the YieldForecaster and CropRecommender.
"""

import pytest

from app.ml.forecaster import CropRecommender, ForecastResult, YieldForecaster

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def forecaster():
    return YieldForecaster()


@pytest.fixture
def sufficient_data():
    """20 years of realistic wheat yield data (kg/ha) with slight upward trend."""
    base = 2000
    return {
        year: base + (year - 2000) * 30 + ((-1) ** year) * 50
        for year in range(2000, 2021)
    }


@pytest.fixture
def minimal_data():
    """Exactly 5 data points — too few for SARIMA, enough for linear."""
    return {2015: 2100, 2016: 2200, 2017: 2150, 2018: 2300, 2019: 2350}


@pytest.fixture
def sparse_data():
    """Only 3 points — insufficient for any forecast."""
    return {2018: 2000, 2019: 2100, 2020: 2200}


# ---------------------------------------------------------------------------
# YieldForecaster — SARIMA / Linear Strategy
# ---------------------------------------------------------------------------

class TestYieldForecaster:
    """Tests for SARIMA + linear fallback forecaster."""

    def test_forecast_with_sufficient_data(self, forecaster, sufficient_data):
        """With 20+ points, should produce a forecast (SARIMA or linear)."""
        result = forecaster.forecast("UP_agra_1971", "wheat", sufficient_data, horizon_years=3)

        assert result is not None
        assert isinstance(result, ForecastResult)
        assert len(result.forecasts) == 3
        assert result.method in ("sarima", "linear_fallback")
        assert result.historical_years == len(sufficient_data)
        assert result.cdk == "UP_agra_1971"
        assert result.crop == "wheat"

    def test_forecast_with_minimal_data_uses_linear(self, forecaster, minimal_data):
        """With 5 points (< 10), should use linear fallback."""
        result = forecaster.forecast("UP_agra_1971", "wheat", minimal_data, horizon_years=2)

        assert result is not None
        assert result.method == "linear_fallback"
        assert len(result.forecasts) == 2

    def test_forecast_insufficient_data_returns_none(self, forecaster, sparse_data):
        """With < 5 points, should return None."""
        result = forecaster.forecast("UP_agra_1971", "wheat", sparse_data)
        assert result is None

    def test_forecast_all_zeros(self, forecaster):
        """Historical data of all zeros (after filtering) should return None."""
        data = {y: 0 for y in range(2010, 2021)}
        result = forecaster.forecast("UP_agra_1971", "wheat", data)
        assert result is None

    def test_forecast_constant_yields(self, forecaster):
        """Constant yield values should still produce a forecast."""
        data = {y: 2500 for y in range(2000, 2021)}
        result = forecaster.forecast("UP_agra_1971", "wheat", data, horizon_years=3)

        assert result is not None
        assert len(result.forecasts) == 3
        # Predicted yield should be close to constant value
        for fp in result.forecasts:
            assert abs(fp.predicted_yield - 2500) < 500

    def test_forecast_points_are_non_negative(self, forecaster, sufficient_data):
        """All predicted values should be non-negative."""
        result = forecaster.forecast("UP_agra_1971", "wheat", sufficient_data, horizon_years=5)

        assert result is not None
        for fp in result.forecasts:
            assert fp.predicted_yield >= 0
            assert fp.lower_bound >= 0
            assert fp.upper_bound >= 0

    def test_forecast_confidence_decreases(self, forecaster, sufficient_data):
        """Confidence should decrease for further horizons."""
        result = forecaster.forecast("UP_agra_1971", "wheat", sufficient_data, horizon_years=5)

        assert result is not None
        confidences = [fp.confidence for fp in result.forecasts]
        # Each subsequent confidence should be <= previous
        for i in range(1, len(confidences)):
            assert confidences[i] <= confidences[i - 1]

    def test_forecast_years_are_sequential(self, forecaster, sufficient_data):
        """Forecast years should be sequential from last historical year."""
        result = forecaster.forecast("UP_agra_1971", "wheat", sufficient_data, horizon_years=3)

        assert result is not None
        last_historical = max(sufficient_data.keys())
        for i, fp in enumerate(result.forecasts):
            assert fp.year == last_historical + i + 1

    def test_to_dict(self, forecaster, sufficient_data):
        """to_dict() should return a JSON-serializable dictionary."""
        result = forecaster.forecast("UP_agra_1971", "wheat", sufficient_data)

        assert result is not None
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "forecasts" in d
        assert isinstance(d["forecasts"], list)
        assert "method" in d
        assert "model_stats" in d

    def test_trend_direction_valid(self, forecaster, sufficient_data):
        """Trend should be one of the valid categories."""
        result = forecaster.forecast("UP_agra_1971", "wheat", sufficient_data)
        assert result is not None
        assert result.trend_direction in (
            "strong_increase", "mild_increase", "mild_decrease", "strong_decrease"
        )


# ---------------------------------------------------------------------------
# CropRecommender
# ---------------------------------------------------------------------------

class TestCropRecommender:
    """Tests for crop recommendation engine."""

    def test_basic_recommendation(self):
        recommender = CropRecommender()
        performances: dict[str, dict[str, float]] = {
            "wheat": {"yield": 3000, "area": 50000, "trend": 5},
            "rice": {"yield": 2500, "area": 40000, "trend": -2},
            "maize": {"yield": 1800, "area": 20000, "trend": 10},
        }
        benchmarks: dict[str, float] = {"wheat": 2800, "rice": 2600, "maize": 2000}

        result = recommender.recommend(performances, benchmarks, top_n=3)

        assert len(result) == 3
        assert all("crop" in r for r in result)
        assert all("score" in r for r in result)
        # Should be sorted by score descending
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_filters_unknown_crops(self):
        recommender = CropRecommender()
        performances: dict[str, dict[str, float]] = {
            "wheat": {"yield": 3000, "area": 50000, "trend": 5},
            "exotic_fruit": {"yield": 5000, "area": 1000, "trend": 20},
        }
        benchmarks: dict[str, float] = {"wheat": 2800, "exotic_fruit": 3000}

        result = recommender.recommend(performances, benchmarks)
        crops = [r["crop"] for r in result]
        assert "exotic_fruit" not in crops
        assert "wheat" in crops

    def test_empty_input(self):
        recommender = CropRecommender()
        result = recommender.recommend({}, {})
        assert result == []

    def test_recommendation_labels(self):
        recommender = CropRecommender()
        performances: dict[str, dict[str, float]] = {
            "wheat": {"yield": 3500, "area": 50000, "trend": 10},  # High → expand
            "rice": {"yield": 1000, "area": 30000, "trend": -20},  # Low → review
        }
        benchmarks: dict[str, float] = {"wheat": 2500, "rice": 2500}

        result = recommender.recommend(performances, benchmarks)
        wheat_rec = next(r for r in result if r["crop"] == "wheat")
        rice_rec = next(r for r in result if r["crop"] == "rice")

        assert wheat_rec["recommendation"] == "expand"
        assert rice_rec["recommendation"] == "review"
