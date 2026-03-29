import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_list_districts(client):
    """Test getting a list of districts."""
    mock_repo = AsyncMock()
    mock_repo.get_all.return_value = [{"cdk": "D1", "name": "Dist1", "state": "State1"}]
    
    mock_db = AsyncMock()
    from app.api.deps import get_db
    async def override_get_db():
        yield mock_db

    client._transport.app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.api.v1.districts.DistrictRepository", return_value=mock_repo):
            response = await client.get("/api/v1/districts")
            assert response.status_code == 200
            data = response.json()
            assert "total" in data
            assert "items" in data
            assert len(data["items"]) == 1
            assert data["items"][0]["cdk"] == "D1"
    finally:
        del client._transport.app.dependency_overrides[get_db]

@pytest.mark.asyncio
async def test_search_districts(client):
    """Test searching districts."""
    mock_repo = AsyncMock()
    mock_repo.search.return_value = [{"cdk": "D2", "name": "TestDist", "state": "State1"}]
    
    mock_db = AsyncMock()
    from app.api.deps import get_db
    async def override_get_db():
        yield mock_db

    client._transport.app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.api.v1.districts.DistrictRepository", return_value=mock_repo):
            response = await client.get("/api/v1/districts?search=Test")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["items"][0]["name"] == "TestDist"
            mock_repo.search.assert_called_once_with("Test", None)
    finally:
        del client._transport.app.dependency_overrides[get_db]

@pytest.mark.asyncio
async def test_list_states(client):
    """Test getting list of states."""
    mock_repo = AsyncMock()
    mock_repo.get_states.return_value = ["State1", "State2"]
    
    mock_db = AsyncMock()
    from app.api.deps import get_db
    async def override_get_db():
        yield mock_db

    client._transport.app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.api.v1.districts.DistrictRepository", return_value=mock_repo):
            response = await client.get("/api/v1/districts/states")
            assert response.status_code == 200
            data = response.json()
            assert "states" in data
            assert "State1" in data["states"]
    finally:
        del client._transport.app.dependency_overrides[get_db]

@pytest.mark.asyncio
async def test_get_district(client):
    """Test getting single district by CDK."""
    mock_repo = AsyncMock()
    mock_repo.get_by_cdk.return_value = {"cdk": "D1", "name": "Dist1", "state": "State1"}
    
    mock_db = AsyncMock()
    from app.api.deps import get_db
    async def override_get_db():
        yield mock_db

    client._transport.app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.api.v1.districts.DistrictRepository", return_value=mock_repo):
            response = await client.get("/api/v1/districts/D1")
            assert response.status_code == 200
            assert response.json()["cdk"] == "D1"
    finally:
        del client._transport.app.dependency_overrides[get_db]

@pytest.mark.asyncio
async def test_get_district_not_found(client):
    """Test getting missing district."""
    mock_repo = AsyncMock()
    mock_repo.get_by_cdk.return_value = None
    
    mock_db = AsyncMock()
    from app.api.deps import get_db
    async def override_get_db():
        yield mock_db

    client._transport.app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.api.v1.districts.DistrictRepository", return_value=mock_repo):
            response = await client.get("/api/v1/districts/D99")
            assert response.status_code == 404
    finally:
        del client._transport.app.dependency_overrides[get_db]
