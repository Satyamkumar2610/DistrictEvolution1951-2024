from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Response

from app.database import get_db
from app.exceptions import NotFoundError


def _override_db(mock_db):
    async def _override():
        yield mock_db

    return _override


@pytest.mark.asyncio
async def test_district_profile_report_returns_json_payload(client):
    mock_db = AsyncMock()
    service = AsyncMock()
    service.get_district_profile_report.return_value = {
        "report_type": "district_profile",
        "district": {"cdk": "101", "name": "Patna", "state": "Bihar"},
        "crop": "wheat",
        "statistics": {
            "mean_yield": 2400.0,
            "max_yield": 2800.0,
            "min_yield": 1800.0,
            "years_with_data": 3,
            "first_year": 2018,
            "last_year": 2020,
            "std_yield": 250.0,
            "cv_yield": 10.42,
            "mean_area": 120.0,
        },
        "state_benchmark": {"avg_yield": 2200.0, "efficiency": 1.091},
        "yearly_data": [
            {"year": 2018, "yield": 1800.0, "area": 100.0, "production": 180.0},
            {"year": 2019, "yield": 2600.0, "area": 120.0, "production": 312.0},
            {"year": 2020, "yield": 2800.0, "area": 140.0, "production": 392.0},
        ],
    }

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.reports.ReportService", return_value=service):
            response = await client.get("/api/v1/reports/district-profile?cdk=101&crop=wheat")

        assert response.status_code == 200
        body = response.json()
        assert body["district"]["name"] == "Patna"
        assert body["state_benchmark"]["efficiency"] == 1.091
        assert body["yearly_data"][0]["year"] == 2018
        service.get_district_profile_report.assert_awaited_once_with("101", "wheat", "json")
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_district_profile_report_returns_csv_export(client):
    mock_db = AsyncMock()
    service = AsyncMock()
    service.get_district_profile_report.return_value = Response(
        content="year,yield\n2020,2800.0\n",
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="Patna_wheat_profile.csv"'},
    )

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.reports.ReportService", return_value=service):
            response = await client.get("/api/v1/reports/district-profile?cdk=101&crop=wheat&format=csv")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "Patna_wheat_profile.csv" in response.headers["content-disposition"]
        service.get_district_profile_report.assert_awaited_once_with("101", "wheat", "csv")
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_district_profile_report_returns_not_found(client):
    mock_db = AsyncMock()
    service = AsyncMock()
    service.get_district_profile_report.side_effect = NotFoundError("District", "404")

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.reports.ReportService", return_value=service):
            response = await client.get("/api/v1/reports/district-profile?cdk=404&crop=wheat")

        assert response.status_code == 404
    finally:
        del client._transport.app.dependency_overrides[get_db]
