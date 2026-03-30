from unittest.mock import AsyncMock, patch

import pytest

from app.api.deps import get_db
from app.exceptions import NotFoundError, ValidationError


def _override_db(mock_db):
    async def _override():
        yield mock_db

    return _override


def _mock_climate_service() -> AsyncMock:
    service = AsyncMock()
    service.get_rainfall_stats.return_value = {
        "source": "IMD 1951-2000 Normals (database)",
        "record_count": 123,
        "status": "loaded",
    }
    service.get_rainfall.return_value = {
        "state": "Bihar",
        "district": "Patna",
        "monthly": {
            "jan": 10,
            "feb": 12,
            "mar": 15,
            "apr": 20,
            "may": 30,
            "jun": 120,
            "jul": 200,
            "aug": 220,
            "sep": 180,
            "oct": 60,
            "nov": 20,
            "dec": 8,
        },
        "seasonal": {
            "winter_jf": 22,
            "pre_monsoon_mam": 65,
            "monsoon_jjas": 720,
            "post_monsoon_ond": 88,
        },
        "annual": 895,
        "source": "IMD 1951-2000 Normals",
    }
    service.get_all_rainfall_data.return_value = [
        {"state": "Bihar", "district": "Patna", "annual": 895.0, "monsoon": 720.0}
    ]
    service.get_state_stats.return_value = {
        "state": "Bihar",
        "district_count": 2,
        "avg_annual_mm": 900.0,
        "min_annual_mm": 850.0,
        "max_annual_mm": 950.0,
        "avg_monsoon_mm": 700.0,
    }
    service.get_water_stress.return_value = {
        "state": "Bihar",
        "year": 2020,
        "districts": [
            {
                "district_name": "Patna",
                "cdk": "101",
                "total_area": 100.0,
                "water_intensive_area": 60.0,
                "water_intensive_share": 60.0,
                "annual_rainfall": 900.0,
                "mismatch_score": 44.0,
                "category": "High",
                "crop_breakdown": {"rice": 40.0, "sugarcane": 20.0, "cotton": 0.0},
            }
        ],
        "validity": {
            "climate_assumption": "stationary",
            "baseline_period": "1951-2000",
            "warning": "Water stress mismatch index is based on historic annual rainfall normals. Not valid for current real-time drought assessment.",
        },
    }
    service.get_rainfall_yield_correlation.return_value = {
        "state": "Bihar",
        "crop": "wheat",
        "year": 2020,
        "sample_size": 5,
        "correlations": {
            "annual_rainfall": {"r": 0.65, "interpretation": "strong", "direction": "positive"},
            "monsoon_rainfall": {"r": 0.65, "interpretation": "strong", "direction": "positive"},
        },
        "data_points": [
            {
                "district": "Patna",
                "yield": 1000.0,
                "annual_rainfall": 895.0,
                "monsoon_rainfall": 720.0,
            }
        ]
        * 5,
        "note": "Correlation uses IMD 1951-2000 rainfall normals vs actual yields",
        "validity": {
            "climate_assumption": "stationary",
            "baseline_period": "1951-2000",
            "warning": "Correlation based on historic climate normals. Not valid for real-time weather impact.",
        },
    }
    return service


@pytest.mark.asyncio
async def test_rainfall_stats_and_lookup_endpoints(client):
    mock_db = AsyncMock()
    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        mock_service = _mock_climate_service()
        with patch("app.api.v1.climate.ClimateService", return_value=mock_service):
            stats_response = await client.get("/api/v1/climate/rainfall/stats")
            rainfall_response = await client.get("/api/v1/climate/rainfall?state=Bihar&district=Patna")

        assert stats_response.status_code == 200
        assert stats_response.json()["record_count"] == 123
        assert rainfall_response.status_code == 200
        assert rainfall_response.json()["seasonal"]["monsoon_jjas"] == 720
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_rainfall_collection_and_state_stats_endpoints(client):
    mock_db = AsyncMock()
    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        mock_service = _mock_climate_service()
        with patch("app.api.v1.climate.ClimateService", return_value=mock_service):
            all_response = await client.get("/api/v1/climate/rainfall/all?state=Bihar")
            state_response = await client.get("/api/v1/climate/rainfall/state-stats?state=Bihar")

        assert all_response.status_code == 200
        assert all_response.json()[0]["district"] == "Patna"
        assert state_response.status_code == 200
        assert state_response.json()["district_count"] == 2
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_water_stress_endpoint_returns_validity_block(client):
    mock_db = AsyncMock()
    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        mock_service = _mock_climate_service()
        with patch("app.api.v1.climate.ClimateService", return_value=mock_service):
            response = await client.get("/api/v1/climate/water-stress?state=Bihar&year=2020")

        assert response.status_code == 200
        body = response.json()
        assert body["districts"][0]["category"] == "High"
        assert body["validity"]["baseline_period"] == "1951-2000"
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_rainfall_yield_correlation_endpoint(client):
    mock_db = AsyncMock()
    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        mock_service = _mock_climate_service()
        with patch("app.api.v1.climate.ClimateService", return_value=mock_service):
            response = await client.get("/api/v1/climate/correlation?state=Bihar&crop=wheat&year=2020")

        assert response.status_code == 200
        body = response.json()
        assert body["sample_size"] == 5
        assert body["correlations"]["annual_rainfall"]["r"] == 0.65
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_climate_endpoints_raise_not_found_or_validation(client):
    mock_db = AsyncMock()
    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        mock_service = _mock_climate_service()
        mock_service.get_rainfall.side_effect = NotFoundError("Rainfall data", "Unknown, Bihar")
        mock_service.get_state_stats.side_effect = NotFoundError("Rainfall data", "Bihar")
        mock_service.get_water_stress.side_effect = NotFoundError(
            detail="Insufficient data to compute water stress for Bihar in 2020"
        )
        mock_service.get_rainfall_yield_correlation.side_effect = ValidationError(
            detail="Insufficient yield data (need at least 5 districts)"
        )
        with patch("app.api.v1.climate.ClimateService", return_value=mock_service):
            rainfall_response = await client.get("/api/v1/climate/rainfall?state=Bihar&district=Unknown")
            state_response = await client.get("/api/v1/climate/rainfall/state-stats?state=Bihar")
            stress_response = await client.get("/api/v1/climate/water-stress?state=Bihar&year=2020")
            corr_response = await client.get("/api/v1/climate/correlation?state=Bihar&crop=wheat&year=2020")

        assert rainfall_response.status_code == 404
        assert state_response.status_code == 404
        assert stress_response.status_code == 404
        assert corr_response.status_code == 400
    finally:
        del client._transport.app.dependency_overrides[get_db]
