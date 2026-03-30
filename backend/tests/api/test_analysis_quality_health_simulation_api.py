from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.analytics.advanced import (
    DiversificationResult,
    EfficiencyResult,
    GrowthResult,
    HistoricalEfficiencyResult,
    ResilienceResult,
    RiskCategory,
    RiskProfile,
)
from app.api.deps import get_db as deps_get_db
from app.database import get_db as database_get_db


def _override_db(mock_db):
    async def _override():
        yield mock_db

    return _override


@pytest.mark.asyncio
async def test_analysis_diversification_efficiency_and_risk_endpoints(client):
    analyzer = SimpleNamespace(
        calculate_diversification=lambda crop_areas: DiversificationResult(
            cdi=0.62,
            interpretation="Good diversification",
            dominant_crop="wheat",
            dominant_share=0.4,
            crop_count=3,
            breakdown={"wheat": 0.4, "rice": 0.35, "maize": 0.25},
        ),
        calculate_efficiency=lambda district_yield, state_yields: EfficiencyResult(
            efficiency_score=0.82,
            district_yield=district_yield,
            potential_yield=2500.0,
            yield_gap=450.0,
            yield_gap_pct=18.0,
            percentile_rank=74.0,
        ),
        calculate_historical_efficiency=lambda district_yield, history: HistoricalEfficiencyResult(
            efficiency_ratio=1.08,
            current_yield=district_yield,
            historical_mean=1900.0,
            yield_diff=150.0,
            is_above_trend=True,
        ),
        calculate_risk_profile=lambda values: RiskProfile(
            risk_category=RiskCategory.MEDIUM,
            volatility_score=12.0,
            reliability_rating="B",
            trend_stability="Stable",
            worst_year=2002,
            best_year=2018,
        ),
        calculate_resilience=lambda values: ResilienceResult(
            resilience_score=0.72,
            volatility_component=0.8,
            retention_component=0.64,
            drought_risk="medium",
            reliability_rating="B",
        ),
        calculate_growth_matrix=lambda values: GrowthResult(
            cagr_5y=2.1,
            cagr_historical=1.4,
            mean_yield_5y=2100.0,
            matrix_quadrant="Star",
            trend_direction="upward",
        ),
    )

    # diversification
    mock_db = AsyncMock()
    mock_db.fetch.return_value = [
        {"variable_name": "wheat_area", "value": 40.0},
        {"variable_name": "rice_area", "value": 35.0},
        {"variable_name": "maize_area", "value": 25.0},
    ]
    client._transport.app.dependency_overrides[deps_get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.analysis.get_advanced_analyzer", return_value=analyzer):
            response = await client.get("/api/v1/analysis/diversification?state=Bihar&year=2020")
        assert response.status_code == 200
        assert response.json()["dominant_crop"] == "wheat"
    finally:
        del client._transport.app.dependency_overrides[deps_get_db]

    # efficiency
    mock_db = AsyncMock()
    mock_db.fetchval.side_effect = [1]
    mock_db.fetchrow.return_value = {"state_name": "Bihar", "yield_val": 2050.0}
    mock_db.fetch.side_effect = [
        [{"yield_val": 1800.0}, {"yield_val": 2200.0}, {"yield_val": 2500.0}],
        [{"yield_val": 1800.0}, {"yield_val": 1950.0}],
    ]
    client._transport.app.dependency_overrides[deps_get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.analysis.get_advanced_analyzer", return_value=analyzer):
            response = await client.get("/api/v1/analysis/efficiency?cdk=101&crop=wheat&year=2020")
        assert response.status_code == 200
        assert response.json()["relative_efficiency"]["efficiency_score"] == 0.82
    finally:
        del client._transport.app.dependency_overrides[deps_get_db]

    # risk profile
    mock_db = AsyncMock()
    mock_db.fetchval.side_effect = [1]
    mock_db.fetch.return_value = [
        {"year": 2018, "value": 1800.0},
        {"year": 2019, "value": 2000.0},
        {"year": 2020, "value": 2050.0},
    ]
    client._transport.app.dependency_overrides[deps_get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.analysis.get_advanced_analyzer", return_value=analyzer):
            response = await client.get("/api/v1/analysis/risk-profile?cdk=101&crop=wheat&metric=yield")
        assert response.status_code == 200
        assert response.json()["risk_profile"]["risk_category"] == "medium"
        assert response.json()["growth_matrix"]["matrix_quadrant"] == "Star"
    finally:
        del client._transport.app.dependency_overrides[deps_get_db]


@pytest.mark.asyncio
async def test_quality_and_health_endpoints(client):
    # quality routes
    mock_db = AsyncMock()
    client._transport.app.dependency_overrides[database_get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.quality.DataQualityScorer") as scorer_cls, patch(
            "app.api.v1.quality.get_state_quality_summary",
            AsyncMock(return_value={"state": "Bihar", "districts_analyzed": 2, "average_quality_score": 0.82, "quality_distribution": {"good": 2}, "top_issues": ["Low data coverage"]}),
        ):
            scorer_cls.return_value.score_district = AsyncMock(
                return_value=type(
                    "QualityReport",
                    (),
                    {
                        "to_dict": lambda self: {
                            "cdk": "101",
                            "completeness_score": 0.8,
                            "consistency_score": 0.9,
                            "timeliness_score": 0.7,
                            "accuracy_score": 0.95,
                            "overall_score": 0.84,
                            "quality_level": "good",
                            "issues": [],
                            "recommendations": [],
                        }
                    },
                )()
            )
            mock_db.fetchval.return_value = 1
            district_response = await client.get("/api/v1/quality/district/101")
            state_response = await client.get("/api/v1/quality/state/Bihar")

        assert district_response.status_code == 200
        assert district_response.json()["overall_score"] == 0.84
        assert state_response.status_code == 200
        assert state_response.json()["districts_analyzed"] == 2
    finally:
        del client._transport.app.dependency_overrides[database_get_db]

    # health routes
    mock_db = AsyncMock()
    mock_db.fetchval.side_effect = [1, 10, 100, 5, 20, 2, 0]
    mock_db.fetchrow.return_value = {"min_year": 1966, "max_year": 2020, "year_count": 55}
    client._transport.app.dependency_overrides[database_get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.health.metrics.get_all_metrics", return_value={"requests_total": 10}):
            live_response = await client.get("/api/v1/health/live")
            ready_response = await client.get("/api/v1/health/ready")
            metrics_response = await client.get("/api/v1/health/metrics")
            app_metrics_response = await client.get("/api/v1/health/app-metrics")

        assert live_response.status_code == 200
        assert ready_response.status_code == 200
        assert ready_response.json()["checks"]["database"] == "connected"
        assert metrics_response.status_code == 200
        assert metrics_response.json()["data_coverage"]["districts"] == 10
        assert app_metrics_response.status_code == 200
        assert app_metrics_response.json()["requests_total"] == 10
    finally:
        del client._transport.app.dependency_overrides[database_get_db]


@pytest.mark.asyncio
async def test_spatial_contagion_endpoint(client):
    mock_db = AsyncMock()
    mock_db.fetchval.return_value = 101
    client._transport.app.dependency_overrides[deps_get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.spatial.SpatialService") as service_cls:
            service_cls.return_value.get_spatial_contagion = AsyncMock(
                return_value={
                    "target": {"cdk": "101", "name": "Patna", "cagr": 2.4},
                    "regional_avg_cagr": 1.9,
                    "spillover_category": "Outperformer",
                    "period": "2000-2020",
                    "crop": "wheat",
                    "neighbors": [{"cdk": "102", "name": "Nalanda", "state": "Bihar", "cagr": 1.5}],
                }
            )
            response = await client.get("/api/v1/spatial/contagion?cdk=101&crop=wheat&start_year=2000&end_year=2020")

        assert response.status_code == 200
        assert response.json()["spillover_category"] == "Outperformer"
    finally:
        del client._transport.app.dependency_overrides[deps_get_db]


@pytest.mark.asyncio
async def test_simulation_endpoints(client):
    # base simulation
    mock_db = AsyncMock()
    service = AsyncMock()
    service.get_simulation_response.return_value = {
        "district": "Patna",
        "state": "Bihar",
        "crop": "wheat",
        "result": {
            "baseline_yield": 1200.0,
            "slope": 1.5,
            "intercept": 0.0,
            "r_squared": 0.7,
            "correlation": 0.8,
            "confidence_interval": 50.0,
            "data_points": [{"rain": 900.0, "yield": 1000.0}],
            "model_equation": "yield = 1.5 * rain + 0",
        },
        "note": "Spatial Regression Proxy: Sensitivity derived from cross-district comparison within state.",
        "validity": {
            "climate_assumption": "stationary",
            "baseline_period": "1951-2000",
            "warning": "Simulation based on historic climate normals. Not valid for real-time weather impact.",
        },
    }

    client._transport.app.dependency_overrides[deps_get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.simulation.SimulationService", return_value=service):
            response = await client.get("/api/v1/simulation/?district=Patna&crop=wheat&year=2020&state=Bihar")

        assert response.status_code == 200
        assert response.json()["result"]["baseline_yield"] == 1200.0
        service.get_simulation_response.assert_awaited_once_with("Patna", "wheat", 2020, "Bihar")
    finally:
        del client._transport.app.dependency_overrides[deps_get_db]

    # prediction v2
    mock_db = AsyncMock()
    service = AsyncMock()
    service.get_prediction_v2_response.return_value = {
        "district": "Patna",
        "state": "Bihar",
        "crop": "wheat",
        "year": 2020,
        "prediction": {
            "predicted_yield": 1250.0,
            "baseline_yield": 1200.0,
            "confidence_lower": 1100.0,
            "confidence_upper": 1400.0,
            "slope_rain": 1.5,
            "mean_rain": 920.0,
            "r_squared": 0.7,
            "adjusted_r_squared": 0.65,
            "rmse": 40.0,
            "sample_size": 5,
            "feature_count": 3,
            "method": "multi_factor_ridge",
            "factors": [],
            "model_equation": "y = a + bx",
            "methodology": "ridge",
            "data_quality_notes": [],
            "data_points": [{"rain": 900.0, "yield": 1000.0, "district": "Patna"}],
            "regression_line": [{"x": 900.0, "y": 1000.0}],
        },
        "validity": {
            "climate_assumption": "stationary",
            "baseline_period": "1951-2000",
            "warning": "Prediction based on historic climate normals and cross-sectional spatial regression. Not valid for real-time weather impact.",
        },
    }

    client._transport.app.dependency_overrides[deps_get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.simulation.SimulationService", return_value=service):
            response = await client.get("/api/v1/simulation/v2?district=Patna&crop=wheat&year=2020&state=Bihar")

        assert response.status_code == 200
        assert response.json()["prediction"]["predicted_yield"] == 1250.0
        service.get_prediction_v2_response.assert_awaited_once_with("Patna", "wheat", 2020, "Bihar")
    finally:
        del client._transport.app.dependency_overrides[deps_get_db]
