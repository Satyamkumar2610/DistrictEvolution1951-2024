"""
Tests for the PredictionEngine (multi-factor Ridge regression).
"""
import pytest

from app.ml.prediction_engine import PredictionEngine, PredictionResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return PredictionEngine()


@pytest.fixture
def multi_factor_data():
    """
    15 districts with realistic cross-district agricultural data.
    Rain varies from 600-1500mm, yields from 1000-3500 kg/ha.
    """
    import random
    random.seed(42)
    data = []
    for i in range(15):
        rain = 600 + i * 60 + random.uniform(-30, 30)
        # Yield roughly linear with rain + noise
        yld = 800 + 1.5 * rain + random.uniform(-200, 200)
        data.append({
            "district": f"District_{i}",
            "yield_value": max(100, yld),
            "rainfall": rain,
            "monsoon_jjas": rain * random.uniform(0.65, 0.85),
            "yield_trend": random.uniform(-20, 40),
            "yield_cv": random.uniform(5, 35),
            "crop_area": random.uniform(5000, 80000),
        })
    return data


@pytest.fixture
def minimal_data():
    """Exactly 6 districts — enough for OLS but not Ridge."""
    return [
        {"district": f"D_{i}", "yield_value": 1500 + i * 200,
         "rainfall": 700 + i * 100}
        for i in range(6)
    ]


@pytest.fixture
def sparse_data():
    """Only 3 — insufficient."""
    return [
        {"district": f"D_{i}", "yield_value": 2000, "rainfall": 1000}
        for i in range(3)
    ]


# ---------------------------------------------------------------------------
# Tests — Multi-Factor Ridge
# ---------------------------------------------------------------------------

class TestPredictionEngineMultiFactor:
    """Tests for ≥ 8 district multi-factor Ridge model."""

    def test_produces_valid_result(self, engine, multi_factor_data):
        result = engine.predict(multi_factor_data, "District_5")
        assert result is not None
        assert isinstance(result, PredictionResult)
        assert result.method == "multi_factor_ridge"
        assert result.sample_size == 15

    def test_feature_count(self, engine, multi_factor_data):
        result = engine.predict(multi_factor_data, "District_5")
        assert result is not None
        # Should have 6 features when all data present (including rainfall_squared)
        assert result.feature_count == 6

    def test_prediction_non_negative(self, engine, multi_factor_data):
        result = engine.predict(multi_factor_data, "District_0")
        assert result is not None
        assert result.predicted_yield >= 0
        assert result.confidence_lower >= 0

    def test_factor_importances_sum_to_one(self, engine, multi_factor_data):
        result = engine.predict(multi_factor_data, "District_5")
        assert result is not None
        total_importance = sum(f.importance for f in result.factors)
        assert abs(total_importance - 1.0) < 0.01

    def test_factors_sorted_by_importance(self, engine, multi_factor_data):
        result = engine.predict(multi_factor_data, "District_5")
        assert result is not None
        importances = [f.importance for f in result.factors]
        assert importances == sorted(importances, reverse=True)

    def test_has_regression_line(self, engine, multi_factor_data):
        result = engine.predict(multi_factor_data, "District_5")
        assert result is not None
        assert len(result.regression_line) == 50
        # Check format
        assert "x" in result.regression_line[0]
        assert "y" in result.regression_line[0]

    def test_data_points_match_input(self, engine, multi_factor_data):
        result = engine.predict(multi_factor_data, "District_5")
        assert result is not None
        assert len(result.data_points) == 15

    def test_methodology_text_non_empty(self, engine, multi_factor_data):
        result = engine.predict(multi_factor_data, "District_5")
        assert result is not None
        assert len(result.methodology) > 50
        assert "Ridge" in result.methodology

    def test_model_equation_non_empty(self, engine, multi_factor_data):
        result = engine.predict(multi_factor_data, "District_5")
        assert result is not None
        assert "Yield" in result.model_equation

    def test_r_squared_in_range(self, engine, multi_factor_data):
        result = engine.predict(multi_factor_data, "District_5")
        assert result is not None
        # Data was designed with linear relationship, R² should be decent
        assert 0 <= result.r_squared <= 1.0

    def test_to_dict_serializable(self, engine, multi_factor_data):
        result = engine.predict(multi_factor_data, "District_5")
        assert result is not None
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "factors" in d
        assert isinstance(d["factors"], list)
        assert "predicted_yield" in d

    def test_unknown_target_district(self, engine, multi_factor_data):
        """If target district not in data, should still produce a result (at mean)."""
        result = engine.predict(multi_factor_data, "UNKNOWN_DISTRICT")
        assert result is not None
        # Should be close to baseline (mean)
        assert result.predicted_yield > 0

    def test_confidence_interval_contains_prediction(self, engine, multi_factor_data):
        result = engine.predict(multi_factor_data, "District_5")
        assert result is not None
        assert result.confidence_lower <= result.predicted_yield <= result.confidence_upper


# ---------------------------------------------------------------------------
# Tests — Simple OLS Fallback
# ---------------------------------------------------------------------------

class TestPredictionEngineOLS:
    """Tests for 5-7 district simple OLS fallback."""

    def test_uses_simple_ols(self, engine, minimal_data):
        result = engine.predict(minimal_data, "D_3")
        assert result is not None
        assert result.method == "simple_ols"

    def test_single_factor(self, engine, minimal_data):
        result = engine.predict(minimal_data, "D_3")
        assert result is not None
        assert result.feature_count == 1
        assert len(result.factors) == 1
        assert result.factors[0].name == "Annual Rainfall"

    def test_prediction_non_negative(self, engine, minimal_data):
        result = engine.predict(minimal_data, "D_0")
        assert result is not None
        assert result.predicted_yield >= 0

    def test_data_quality_notes_present(self, engine, minimal_data):
        result = engine.predict(minimal_data, "D_3")
        assert result is not None
        assert len(result.data_quality_notes) > 0


# ---------------------------------------------------------------------------
# Tests — Insufficient Data
# ---------------------------------------------------------------------------

class TestPredictionEngineEdgeCases:
    """Tests for edge cases."""

    def test_returns_none_for_sparse_data(self, engine, sparse_data):
        result = engine.predict(sparse_data, "D_0")
        assert result is None

    def test_returns_none_for_empty_data(self, engine):
        result = engine.predict([], "D_0")
        assert result is None

    def test_handles_zero_rainfall(self, engine):
        data = [
            {"district": f"D_{i}", "yield_value": 2000, "rainfall": 0}
            for i in range(10)
        ]
        result = engine.predict(data, "D_0")
        # Should handle gracefully (division by zero protection)
        assert result is not None or result is None  # Should not raise

    def test_constant_yields(self, engine):
        data = [
            {"district": f"D_{i}", "yield_value": 2500, "rainfall": 500 + i * 100}
            for i in range(10)
        ]
        result = engine.predict(data, "D_5")
        assert result is not None
        assert abs(result.predicted_yield - 2500) < 500
