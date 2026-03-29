from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.deps import get_db
from app.services.rainfall_service import RainfallData


def _override_db(mock_db):
    async def _override():
        yield mock_db

    return _override


def _rainfall(state: str = "Bihar", district: str = "Patna") -> RainfallData:
    return RainfallData(
        state=state,
        district=district,
        jan=10,
        feb=12,
        mar=15,
        apr=20,
        may=30,
        jun=120,
        jul=200,
        aug=220,
        sep=180,
        oct=60,
        nov=20,
        dec=8,
        annual=895,
        monsoon_jjas=720,
        winter_jf=22,
        pre_monsoon_mam=65,
        post_monsoon_ond=88,
    )


@pytest.mark.asyncio
async def test_rainfall_stats_and_lookup_endpoints(client):
    mock_db = AsyncMock()
    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.climate.get_rainfall_count", AsyncMock(return_value=123)), patch(
            "app.api.v1.climate.get_rainfall_by_district", AsyncMock(return_value=_rainfall())
        ):
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
        with patch(
            "app.api.v1.climate.get_all_rainfall",
            AsyncMock(return_value=[{"state": "Bihar", "district": "Patna", "annual": 895.0, "monsoon": 720.0}]),
        ), patch(
            "app.api.v1.climate.get_state_rainfall_stats",
            AsyncMock(return_value={"state": "Bihar", "district_count": 2, "avg_annual_mm": 900.0, "min_annual_mm": 850.0, "max_annual_mm": 950.0, "avg_monsoon_mm": 700.0}),
        ):
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
    payload = [
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
    ]
    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.climate.get_water_stress_index", AsyncMock(return_value=payload)):
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
    mock_db.fetch.return_value = [
        {"district_name": "Patna", "yield_val": 1000.0},
        {"district_name": "Gaya", "yield_val": 1100.0},
        {"district_name": "Nalanda", "yield_val": 1200.0},
        {"district_name": "Munger", "yield_val": 1300.0},
        {"district_name": "Bhagalpur", "yield_val": 1400.0},
    ]
    analyzer = SimpleNamespace(
        pearson_correlation=lambda x, y: SimpleNamespace(value=0.65 if len(x) == 5 else 0.0)
    )

    async def rainfall_side_effect(_db, state, district):
        return _rainfall(state, district)

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.climate.get_analyzer", return_value=analyzer), patch(
            "app.api.v1.climate.get_rainfall_by_district",
            AsyncMock(side_effect=rainfall_side_effect),
        ):
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
    mock_db.fetch.return_value = []
    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.climate.get_rainfall_by_district", AsyncMock(return_value=None)), patch(
            "app.api.v1.climate.get_state_rainfall_stats",
            AsyncMock(return_value={"error": "No data for state: Bihar"}),
        ), patch("app.api.v1.climate.get_water_stress_index", AsyncMock(return_value=[])):
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
