import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_get_state_overview(client):
    """Test getting a state overview."""
    mock_db = AsyncMock()
    mock_db.fetchval = AsyncMock()
    mock_db.fetchval.side_effect = [
        1, # state_check
        38, # total_districts
        2500.5, # avg_yield
        30, # districts_with_data
    ]
    
    mock_db.fetchrow = AsyncMock()
    mock_db.fetchrow.side_effect = [
        {"min_year": 1990, "max_year": 2020}, # year_range
        {"total_area": 10000, "total_production": 50000}, # totals
    ]
    
    mock_db.fetch = AsyncMock()
    mock_db.fetch.side_effect = [
        [{"district_name": "Dist1", "cdk": "D1", "yield_value": 3000}], # top
        [{"district_name": "Dist2", "cdk": "D2", "yield_value": 1000}], # bottom
        [{"crop_name": "wheat"}] # available crops
    ]

    from app.database import get_db as real_get_db
    async def mock_get_db_gen():
        yield mock_db

    app_dependency_overrides = client._transport.app.dependency_overrides
    client._transport.app.dependency_overrides[real_get_db] = mock_get_db_gen
    
    try:
        response = await client.get("/api/v1/states/BIHAR/overview?crop=wheat&year=2020")
        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "BIHAR"
        assert data["total_districts"] == 38
    finally:
        client._transport.app.dependency_overrides = app_dependency_overrides

@pytest.mark.asyncio
async def test_list_states(client):
    """Test listing all states endpoint."""
    mock_db = AsyncMock()
    mock_db.fetch.return_value = [
        {"state_name": "State1", "district_count": 10},
        {"state_name": "State2", "district_count": 20}
    ]

    from app.database import get_db as real_get_db
    
    async def mock_get_db_gen():
        yield mock_db

    app_dependency_overrides = client._transport.app.dependency_overrides
    client._transport.app.dependency_overrides[real_get_db] = mock_get_db_gen
    
    try:
        response = await client.get("/api/v1/states/list")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["state"] == "State1"
        assert data[0]["district_count"] == 10
    finally:
        client._transport.app.dependency_overrides = app_dependency_overrides
