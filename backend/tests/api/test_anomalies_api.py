from unittest.mock import AsyncMock, patch

import pytest

from app.database import get_db
from app.exceptions import NotFoundError


def _override_db(mock_db):
    async def _override():
        yield mock_db

    return _override


@pytest.mark.asyncio
async def test_district_anomaly_endpoint_returns_typed_payload(client):
    mock_db = AsyncMock()
    service = AsyncMock()
    service.scan_district_response.return_value = {
        "cdk": "101",
        "total_anomalies": 2,
        "anomalies_by_type": {"yield_outlier": 1, "yoy_spike": 1},
        "critical_count": 0,
        "high_count": 1,
        "anomalies": [
            {
                "anomaly_type": "yield_outlier",
                "cdk": "101",
                "year": 2020,
                "variable": "wheat_yield",
                "value": 2500.0,
                "expected_range": [1400.0, 2200.0],
                "severity": "high",
                "description": "Outlier detected",
            }
        ],
        "risk_alert": {
            "cdk": "101",
            "district_name": "Patna",
            "risk_level": "medium",
            "risk_score": 35.0,
            "factors": ["Yield values significantly deviate from state average"],
            "recommendation": "Flag for periodic review. Note data limitations in analyses.",
        },
        "scan_timestamp": "2025-01-01T00:00:00Z",
    }

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.anomalies.AnomalyService", return_value=service):
            response = await client.get("/api/v1/anomalies/district/101")

        assert response.status_code == 200
        body = response.json()
        assert body["total_anomalies"] == 2
        assert body["risk_alert"]["district_name"] == "Patna"
        service.scan_district_response.assert_awaited_once_with("101")
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_state_anomaly_endpoint_handles_success_and_not_found(client):
    mock_db = AsyncMock()
    service = AsyncMock()
    service.scan_state_response.return_value = {
        "state": "Bihar",
        "districts_scanned": 2,
        "total_critical_anomalies": 1,
        "total_high_anomalies": 3,
        "high_risk_districts": [
            {
                "cdk": "101",
                "district_name": "Patna",
                "total_anomalies": 3,
                "critical": 1,
                "high": 1,
                "risk_level": "high",
                "risk_score": 45.0,
            }
        ],
        "all_districts": [
            {
                "cdk": "101",
                "district_name": "Patna",
                "total_anomalies": 3,
                "critical": 1,
                "high": 1,
                "risk_level": "high",
                "risk_score": 45.0,
            }
        ],
    }

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.anomalies.AnomalyService", return_value=service):
            success_response = await client.get("/api/v1/anomalies/state/Bihar?limit=5")

        assert success_response.status_code == 200
        assert success_response.json()["high_risk_districts"][0]["risk_level"] == "high"
        service.scan_state_response.assert_awaited_once_with("Bihar", 5)
    finally:
        del client._transport.app.dependency_overrides[get_db]

    mock_db = AsyncMock()
    service = AsyncMock()
    service.scan_state_response.side_effect = NotFoundError("State anomaly scan", "Unknown")

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.anomalies.AnomalyService", return_value=service):
            not_found_response = await client.get("/api/v1/anomalies/state/Unknown")

        assert not_found_response.status_code == 404
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_high_risk_endpoint_returns_ranked_districts(client):
    mock_db = AsyncMock()
    service = AsyncMock()
    service.get_high_risk_districts_response.return_value = {
        "high_risk_districts": [
            {
                "cdk": "101",
                "state": "Bihar",
                "district_name": "Patna",
                "risk_score": 52.0,
                "risk_level": "high",
                "factors": ["Volatile year-over-year yield changes detected"],
            },
            {
                "cdk": "202",
                "state": "Jharkhand",
                "district_name": "Ranchi",
                "risk_score": 35.0,
                "risk_level": "medium",
                "factors": ["Significant data gaps may hide trends"],
            },
        ],
        "total_scanned": 6,
    }

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.anomalies.AnomalyService", return_value=service):
            response = await client.get("/api/v1/anomalies/high-risk?limit=2")

        assert response.status_code == 200
        body = response.json()
        assert body["total_scanned"] == 6
        assert body["high_risk_districts"][0]["risk_score"] == 52.0
        service.get_high_risk_districts_response.assert_awaited_once_with(2)
    finally:
        del client._transport.app.dependency_overrides[get_db]
