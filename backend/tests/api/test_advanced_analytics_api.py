from unittest.mock import AsyncMock, patch

import pytest

from app.api.deps import get_db


def _override_db(mock_db):
    async def _override():
        yield mock_db

    return _override


@pytest.mark.asyncio
async def test_crop_diversification_endpoint_returns_typed_payload(client):
    mock_db = AsyncMock()
    service = AsyncMock()
    service.get_crop_diversification_response.return_value = {
        "cdk": "123",
        "year": 2020,
        "cdi": 0.58,
        "herfindahl_index": 0.42,
        "simpson_diversity_index": 0.58,
        "interpretation": "moderately diverse",
        "crop_count": 3,
        "num_crops": 3,
        "dominant_crop": "wheat",
        "dominant_share": 0.55,
        "dominant_share_percent": 55.0,
        "breakdown": {"wheat": 0.55, "rice": 0.3, "maize": 0.15},
    }

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.advanced_analytics.AdvancedAnalyticsFacade", return_value=service):
            response = await client.get("/api/v1/analytics/diversification?cdk=123&year=2020")

        assert response.status_code == 200
        body = response.json()
        assert body["cdi"] == 0.58
        assert body["dominant_crop"] == "wheat"
        assert body["breakdown"]["rice"] == 0.3
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_crop_shift_endpoint_wraps_service_timeline(client):
    mock_db = AsyncMock()
    service = AsyncMock()
    service.get_crop_shift_response.return_value = {
        "cdk": "123",
        "timeline": [
            {
                "year": 2000,
                "total_area": 100.0,
                "shannon_index": 1.2,
                "simpson_index": 0.6,
                "dominant_crop": "wheat",
                "dominant_share": 55.0,
                "crop_mix": {"wheat": 0.55, "rice": 0.45},
            }
        ],
    }

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.advanced_analytics.AdvancedAnalyticsFacade", return_value=service):
            response = await client.get("/api/v1/analytics/crop-shift?cdk=123")

        assert response.status_code == 200
        assert response.json()["timeline"][0]["dominant_crop"] == "wheat"
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_yield_trend_and_split_impact_endpoints(client):
    mock_db = AsyncMock()
    service = AsyncMock()
    service.get_yield_trend_response.return_value = {
        "cdk": "123",
        "crop": "wheat",
        "period": "2000-2020",
        "start_yield_kg_ha": 1000.0,
        "end_yield_kg_ha": 1400.0,
        "cagr_percent": 1.7,
        "volatility_percent": 9.5,
        "trend": "increasing",
        "risk_assessment": "low",
    }
    service.get_split_impact_response.return_value = {
        "parent_cdk": "101",
        "child_cdks": ["201", "202"],
        "split_year": 2000,
        "crop": "wheat",
        "before": {"years": [1998, 1999], "yields": [1000.0, 1100.0], "average": 1050.0},
        "after": {
            "by_child": {
                "201": {"yields": [1200.0, 1250.0], "avg": 1225.0},
                "202": {"yields": [1180.0, 1210.0], "avg": 1195.0},
            },
            "combined_average": 1210.0,
        },
        "impact": {"absolute_change": 160.0, "percent_change": 15.24, "assessment": "positive"},
    }

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.advanced_analytics.AdvancedAnalyticsFacade", return_value=service):
            trend_response = await client.get(
                "/api/v1/analytics/yield-trend?cdk=123&crop=wheat&start_year=2000&end_year=2020"
            )
            split_response = await client.get(
                "/api/v1/analytics/split-impact?parent_cdk=101&child_cdks=201,202&split_year=2000&crop=wheat"
            )

        assert trend_response.status_code == 200
        assert trend_response.json()["risk_assessment"] == "low"
        assert split_response.status_code == 200
        assert split_response.json()["impact"]["assessment"] == "positive"
        service.get_split_impact_response.assert_awaited_once_with("101", ["201", "202"], 2000, "wheat", 5, 5)
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_correlations_rankings_and_seasonal_comparison_endpoints(client):
    mock_db = AsyncMock()
    service = AsyncMock()
    service.get_crop_correlations_response.return_value = {
        "state": "Bihar",
        "year": 2020,
        "crops": ["wheat", "rice"],
        "correlations": {"wheat": {"wheat": 1.0, "rice": 0.25}, "rice": {"wheat": 0.25, "rice": 1.0}},
    }
    service.get_district_rankings_response.return_value = [{"rank": 1, "cdk": "123", "district": "Patna", "value": 2400.0}]
    service.get_seasonal_comparison_response.return_value = {
        "cdk": "123",
        "crop": "rice",
        "year": 2020,
        "kharif_yield": 2500.0,
        "rabi_yield": 1200.0,
        "dominant_season": "kharif",
    }

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.advanced_analytics.AdvancedAnalyticsFacade", return_value=service):
            corr_response = await client.get("/api/v1/analytics/crop-correlations?state=Bihar&year=2020&crops=wheat,rice")
            rank_response = await client.get("/api/v1/analytics/district-rankings?state=Bihar&crop=wheat&year=2020")
            seasonal_response = await client.get("/api/v1/analytics/seasonal-comparison?cdk=123&crop=rice&year=2020")

        assert corr_response.status_code == 200
        assert corr_response.json()["correlations"]["wheat"]["rice"] == 0.25
        assert rank_response.status_code == 200
        assert rank_response.json()[0]["district"] == "Patna"
        assert seasonal_response.status_code == 200
        assert seasonal_response.json()["dominant_season"] == "kharif"
        service.get_crop_correlations_response.assert_awaited_once_with("Bihar", 2020, ["wheat", "rice"])
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_yoy_growth_and_summary_endpoints(client):
    mock_db = AsyncMock()
    service = AsyncMock()
    service.get_yoy_growth_response.return_value = {
        "cdk": "123",
        "crop": "wheat",
        "period": "2018-2020",
        "data": [
            {"year": 2018, "yield": 1000.0, "yoy_growth": None},
            {"year": 2019, "yield": 1200.0, "yoy_growth": 20.0},
            {"year": 2020, "yield": 1140.0, "yoy_growth": -5.0},
        ],
        "summary": {
            "average_yoy_growth_percent": 7.5,
            "positive_growth_years": 1,
            "negative_growth_years": 1,
        },
    }
    service.get_summary_response.return_value = {
        "cdk": "123",
        "year": 2020,
        "diversification": {
            "index": 0.52,
            "num_crops": 4,
            "dominant_crop": "rice",
        },
        "trends": {
            "crops": {
                "rice": {"cagr": 1.5, "trend": "increasing"},
                "wheat": {"cagr": 0.5, "trend": "stable"},
            }
        },
        "data_source": "Hybrid (ICRISAT 1966-1997 + DES 1998-2021)",
    }

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.advanced_analytics.AdvancedAnalyticsFacade", return_value=service):
            yoy_response = await client.get("/api/v1/analytics/yoy-growth?cdk=123&crop=wheat&start_year=2018&end_year=2020")
            summary_response = await client.get("/api/v1/analytics/summary?cdk=123&year=2020")

        assert yoy_response.status_code == 200
        assert yoy_response.json()["summary"]["positive_growth_years"] == 1
        assert summary_response.status_code == 200
        assert summary_response.json()["diversification"]["dominant_crop"] == "rice"
        assert summary_response.json()["trends"]["crops"]["rice"]["trend"] == "increasing"
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_forecast_resilience_gap_and_specialization_endpoints(client):
    mock_db = AsyncMock()
    service = AsyncMock()
    service.get_yield_forecast_response.return_value = {
        "cdk": "123",
        "crop": "wheat",
        "historical_trend": "increasing",
        "slope": 2.4,
        "forecast": [{"year": 2021, "projected_yield": 1500.0, "confidence_interval_lower": 1400.0, "confidence_interval_upper": 1600.0}],
    }
    service.get_resilience_index_response.return_value = {
        "state": "Bihar",
        "crop": "wheat",
        "total_districts": 1,
        "rankings": [
            {
                "cdk": "123",
                "district_name": "Patna",
                "data_points": 12,
                "avg_yield": 2300.0,
                "avg_shock_drop_pct": 12.0,
                "avg_recovery_years": 2.0,
                "resilience_score": 78.0,
                "rank": 1,
            }
        ],
    }
    service.get_yield_gap_response.return_value = {
        "state": "Bihar",
        "crop": "wheat",
        "period": "2000-2020",
        "convergence_timeline": [{"year": 2020, "frontier_yield": 3000.0, "state_avg_yield": 2200.0, "avg_gap": 800.0}],
        "district_rankings": [{"cdk": "123", "district_name": "Patna", "avg_gap": 800.0, "latest_gap": 700.0, "avg_yield": 2300.0, "gap_trend": -1.2, "status": "Closing", "rank": 1}],
    }
    service.get_split_specialization_response.return_value = {
        "split_year": 2000,
        "crops": ["wheat", "rice"],
        "parent": {"name": "Parent", "cdk": "101", "pre_mix": {"wheat": 60.0, "rice": 40.0}},
        "children": {"Child A": {"cdk": "201", "mix": {"wheat": 70.0, "rice": 30.0}}},
        "divergence_scores": {"Child A": 14.1},
    }

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.advanced_analytics.AdvancedAnalyticsFacade", return_value=service):
            forecast_response = await client.get("/api/v1/analytics/yield-forecast?cdk=123&crop=wheat&forecast_years=1")
            resilience_response = await client.get("/api/v1/analytics/resilience-index?state=Bihar&crop=wheat")
            gap_response = await client.get("/api/v1/analytics/yield-gap?state=Bihar&crop=wheat&start_year=2000&end_year=2020")
            specialization_response = await client.get("/api/v1/analytics/split-specialization?parent_cdk=101&child_cdks=201&split_year=2000")

        assert forecast_response.status_code == 200
        assert resilience_response.status_code == 200
        assert resilience_response.json()["total_districts"] == 1
        assert gap_response.status_code == 200
        assert gap_response.json()["district_rankings"][0]["status"] == "Closing"
        assert specialization_response.status_code == 200
        assert specialization_response.json()["divergence_scores"]["Child A"] == 14.1
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_yield_forecast_and_gap_endpoints_raise_errors(client):
    mock_db = AsyncMock()
    service = AsyncMock()
    from app.exceptions import NotFoundError, ValidationError

    service.get_yield_forecast_response.side_effect = ValidationError(detail="Insufficient data")
    service.get_yield_gap_response.side_effect = NotFoundError(
        "Yield gap data",
        detail="No data found for the given parameters",
    )
    service.get_resilience_index_response.side_effect = NotFoundError("Resilience data", "Bihar")

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.advanced_analytics.AdvancedAnalyticsFacade", return_value=service):
            forecast_response = await client.get("/api/v1/analytics/yield-forecast?cdk=123&crop=wheat")
            gap_response = await client.get("/api/v1/analytics/yield-gap?state=Bihar&crop=wheat")
            resilience_response = await client.get("/api/v1/analytics/resilience-index?state=Bihar&crop=wheat")

        assert forecast_response.status_code == 400
        assert gap_response.status_code == 404
        assert resilience_response.status_code == 404
    finally:
        del client._transport.app.dependency_overrides[get_db]
