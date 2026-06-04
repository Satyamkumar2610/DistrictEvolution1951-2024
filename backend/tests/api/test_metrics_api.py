from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_metrics(client):
    """Test getting metrics for a year."""
    mock_repo = AsyncMock()
    mock_repo.get_by_year_and_variable.return_value = [{
        "state": "Bihar",
        "district": "Dist1",
        "cdk": "D1",
        "value": 100,
        "metric": "wheat_yield",
        "year": 2020,
        "score": None,
        "feature_id": "Dist1|Bihar",
        "geo_key": "Dist1|Bihar",
    }]

    mock_db = AsyncMock()
    from app.api.deps import get_db
    async def override_get_db():
        yield mock_db

    client._transport.app.dependency_overrides[get_db] = override_get_db

    try:
        with patch("app.api.v1.metrics.MetricRepository", return_value=mock_repo):
            response = await client.get("/api/v1/metrics?year=2020&crop=wheat&metric=yield")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["cdk"] == "D1"
            assert data[0]["feature_id"] == "Dist1|Bihar"
            assert data[0]["geo_key"] == "Dist1|Bihar"
            mock_repo.get_by_year_and_variable.assert_called_once_with(2020, "wheat_yield", "historical")
    finally:
        del client._transport.app.dependency_overrides[get_db]

@pytest.mark.asyncio
async def test_get_time_series(client):
    """Test getting time series for a district cdk."""
    mock_repo = AsyncMock()
    mock_repo.get_time_series_pivoted.return_value = [{"year": 2020, "yield": 100}]

    mock_db = AsyncMock()
    from app.api.deps import get_db
    async def override_get_db():
        yield mock_db

    client._transport.app.dependency_overrides[get_db] = override_get_db

    try:
        with patch("app.api.v1.metrics.MetricRepository", return_value=mock_repo), \
             patch("app.api.v1.metrics.DistrictRepository"):
            response = await client.get("/api/v1/metrics/history?cdk=D1")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["year"] == 2020
            mock_repo.get_time_series_pivoted.assert_called_once_with("D1", "wheat")
    finally:
        del client._transport.app.dependency_overrides[get_db]

@pytest.mark.asyncio
async def test_get_state_time_series(client):
    """Test getting time series for a whole state."""
    mock_repo = AsyncMock()
    mock_repo.get_time_series_pivoted.return_value = [{"year": 2020, "yield": 100}]

    mock_db = AsyncMock()
    from app.api.deps import get_db
    async def override_get_db():
        yield mock_db

    client._transport.app.dependency_overrides[get_db] = override_get_db

    try:
        with patch("app.api.v1.metrics.MetricRepository", return_value=mock_repo):
            response = await client.get("/api/v1/metrics/history/state?state=BIHAR")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["year"] == 2020
            mock_repo.get_time_series_pivoted.assert_called_once_with("S_BIHAR", "wheat")
    finally:
        del client._transport.app.dependency_overrides[get_db]

@pytest.mark.asyncio
async def test_get_state_time_series_fallback(client):
    """Test fallback when state cdk fails."""
    mock_repo = AsyncMock()
    mock_repo.get_time_series_pivoted.return_value = []
    mock_repo.get_state_time_series_aggregated.return_value = [{"year": 2020, "yield": 100}]

    mock_db = AsyncMock()
    from app.api.deps import get_db
    async def override_get_db():
        yield mock_db

    client._transport.app.dependency_overrides[get_db] = override_get_db

    try:
        with patch("app.api.v1.metrics.MetricRepository", return_value=mock_repo):
            response = await client.get("/api/v1/metrics/history/state?state=BIHAR")
            assert response.status_code == 200
            data = response.json()
            assert data[0]["year"] == 2020
            mock_repo.get_state_time_series_aggregated.assert_called_once_with("BIHAR", "wheat")
    finally:
        del client._transport.app.dependency_overrides[get_db]
