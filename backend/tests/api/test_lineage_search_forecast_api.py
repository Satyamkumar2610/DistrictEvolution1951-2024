from unittest.mock import AsyncMock, patch

import pytest

from app.api.deps import get_db as deps_get_db
from app.database import get_db as database_get_db
from app.exceptions import NotFoundError


def _override_db(mock_db):
    async def _override():
        yield mock_db

    return _override


@pytest.mark.asyncio
async def test_search_endpoint_combines_district_and_state_results(client):
    mock_db = AsyncMock()
    mock_db.fetch.side_effect = [
        [
            {"cdk": "101", "name": "Patna", "state": "Bihar", "start_year": 1956, "end_year": None, "result_type": "district", "sort_order": 0},
        ],
        [
            {"name": "Bihar", "state": "Bihar", "district_count": 38, "result_type": "state"},
        ],
    ]

    client._transport.app.dependency_overrides[database_get_db] = _override_db(mock_db)
    try:
        response = await client.get("/api/v1/search?q=Bi&type=all&limit=20")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert body["results"][0]["result_type"] == "district"
        assert body["results"][1]["district_count"] == 38
    finally:
        del client._transport.app.dependency_overrides[database_get_db]


@pytest.mark.asyncio
async def test_forecast_endpoints_return_forecast_and_recommendations(client):
    mock_db = AsyncMock()
    service = AsyncMock()
    service.get_yield_forecast_response.return_value = {
        "cdk": "101",
        "crop": "wheat",
        "historical_years": 5,
        "method": "linear_fallback",
        "trend_direction": "mild_increase",
        "forecasts": [
            {
                "year": 2023,
                "predicted_yield": 1350.0,
                "lower_bound": 1250.0,
                "upper_bound": 1450.0,
                "confidence": 0.9,
            }
        ],
        "model_stats": {"slope": 50.0},
    }

    client._transport.app.dependency_overrides[database_get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.forecast.ForecastService", return_value=service):
            response = await client.get("/api/v1/forecast/101/wheat?horizon=1")

        assert response.status_code == 200
        assert response.json()["forecasts"][0]["year"] == 2023
        service.get_yield_forecast_response.assert_awaited_once_with("101", "wheat", 1)
    finally:
        del client._transport.app.dependency_overrides[database_get_db]

    mock_db = AsyncMock()
    service = AsyncMock()
    service.get_crop_recommendations_response.return_value = {
        "cdk": "101",
        "district": "Patna",
        "state": "Bihar",
        "recommendations": [
            {
                "crop": "rice",
                "score": 1.2,
                "efficiency": 1.1,
                "current_yield": 1000.0,
                "state_average": 900.0,
                "current_area": 200.0,
                "trend_pct": 12.5,
                "recommendation": "expand",
            }
        ],
    }

    client._transport.app.dependency_overrides[database_get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.forecast.ForecastService", return_value=service):
            response = await client.get("/api/v1/forecast/101/recommend?top_n=1")

        assert response.status_code == 200
        assert response.json()["recommendations"][0]["crop"] == "rice"
        service.get_crop_recommendations_response.assert_awaited_once_with("101", 1)
    finally:
        del client._transport.app.dependency_overrides[database_get_db]


@pytest.mark.asyncio
async def test_lineage_history_events_tracking_and_coverage(client):
    mock_db = AsyncMock()
    service = AsyncMock()
    service.get_district_history_response.return_value = [
        {
            "state_name": "Bihar",
            "split_year": 2000,
            "parent_district": "Patna",
            "child_district": "Nalanda",
            "parent_cdk": "101",
            "child_cdk": "201",
            "source": "gazette",
        }
    ]
    service.get_lineage_events_response.return_value = {
        "total_events": 1,
        "events": [
            {
                "id": "E1",
                "parent_cdk": "101",
                "parent_name": "Patna",
                "children_cdks": ["201"],
                "children_names": ["Nalanda"],
                "children_count": 1,
                "event_year": 2000,
                "event_type": "split",
                "coverage_ratios": {"201": 1.0},
                "legal_reference": None,
                "confidence": 1.0,
            }
        ],
    }
    service.get_data_tracking_response.return_value = {
        "district": {
            "cdk": "101",
            "district_name": "Patna",
            "state_name": "Bihar",
            "start_year": 1956,
            "end_year": None,
        },
        "data_coverage": {
            "years_with_data": 10,
            "first_year": 2000,
            "last_year": 2009,
            "variables": 3,
            "total_records": 100,
        },
        "data_sources": [
            {
                "source": "ICRISAT/DES",
                "record_count": 100,
                "from_year": 2000,
                "to_year": 2009,
            }
        ],
        "lineage": {"split_into": [], "created_from": []},
    }
    service.get_state_coverage_response.return_value = {
        "state": "Bihar",
        "districts": 1,
        "coverage": [
            {
                "cdk": "101",
                "district_name": "Patna",
                "start_year": 1956,
                "end_year": None,
                "years_with_data": 10,
                "record_count": 100,
                "lineage_status": "original",
            }
        ],
    }

    client._transport.app.dependency_overrides[deps_get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.lineage.LineageService", return_value=service):
            history_response = await client.get("/api/v1/lineage/history?state=Bihar")
            events_response = await client.get("/api/v1/lineage/events?state=Bihar")
            tracking_response = await client.get("/api/v1/lineage/tracking?cdk=101")
            coverage_response = await client.get("/api/v1/lineage/coverage?state=Bihar")

        assert history_response.status_code == 200
        assert history_response.json()[0]["parent_district"] == "Patna"
        assert events_response.status_code == 200
        assert events_response.json()["total_events"] == 1
        assert tracking_response.status_code == 200
        assert tracking_response.json()["data_coverage"]["total_records"] == 100
        assert coverage_response.status_code == 200
        assert coverage_response.json()["districts"] == 1
        service.get_district_history_response.assert_awaited_once_with("Bihar")
        service.get_lineage_events_response.assert_awaited_once_with("Bihar")
        service.get_data_tracking_response.assert_awaited_once_with("101")
        service.get_state_coverage_response.assert_awaited_once_with("Bihar")
    finally:
        del client._transport.app.dependency_overrides[deps_get_db]


@pytest.mark.asyncio
async def test_lineage_tracking_not_found_and_unmapped(client):
    mock_db = AsyncMock()
    service = AsyncMock()
    service.get_data_tracking_response.side_effect = NotFoundError("District", "404")
    service.get_unmapped_splits_response.return_value = [
        {
            "district": "New Patna",
            "state": "Bihar",
            "year": 2000,
            "role": "Child",
        }
    ]

    client._transport.app.dependency_overrides[deps_get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.lineage.LineageService", return_value=service):
            tracking_response = await client.get("/api/v1/lineage/tracking?cdk=404")
            unmapped_response = await client.get("/api/v1/lineage/unmapped")

        assert tracking_response.status_code == 404
        assert unmapped_response.status_code == 200
        assert unmapped_response.json()[0]["district"] == "New Patna"
        service.get_data_tracking_response.assert_awaited_once_with("404")
        service.get_unmapped_splits_response.assert_awaited_once()
    finally:
        del client._transport.app.dependency_overrides[deps_get_db]
