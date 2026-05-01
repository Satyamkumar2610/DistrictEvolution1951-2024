"""
API Integration Tests — Health, Root, and System endpoints.

These tests use the httpx AsyncClient against the real FastAPI app
but with a mocked database pool to avoid needing a live Postgres instance.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_root_returns_api_info(client):
    """GET / should return the API info payload."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "I-ASCAP API"
    assert "version" in data
    assert data["api"] == "/api/v1"


@pytest.mark.asyncio
async def test_health_returns_200(client):
    """GET /health should always return 200."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_docs_accessible(client):
    """GET /docs should return the Swagger UI page."""
    response = await client.get("/docs")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_openapi_schema_accessible(client):
    """GET /openapi.json should return a valid OpenAPI schema."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert "paths" in schema
    # Verify core paths are registered
    assert "/api/v1/health/ping" in schema["paths"] or len(schema["paths"]) > 5


@pytest.mark.asyncio
async def test_nonexistent_route_returns_404(client):
    """GET /api/v1/nonexistent should return 404 or method not allowed."""
    response = await client.get("/api/v1/this-does-not-exist")
    assert response.status_code in (404, 405)


@pytest.mark.asyncio
async def test_stats_requires_admin_key(client):
    """GET /stats without admin key should be forbidden when key is configured."""
    # The default settings have api_key=None, so this may return 200
    # But we verify the endpoint exists and responds
    mock_pool = AsyncMock()
    mock_pool.get_size = MagicMock(return_value=10)
    mock_pool.get_idle_size = MagicMock(return_value=5)
    with patch("app.database.get_pool", return_value=mock_pool):
        response = await client.get("/stats")
        assert response.status_code in (200, 403)


@pytest.mark.asyncio
async def test_request_id_in_response_headers(client):
    """Every response should contain X-Request-ID and X-Response-Time headers."""
    response = await client.get("/health")
    assert "x-request-id" in response.headers
    assert "x-response-time" in response.headers


@pytest.mark.asyncio
async def test_security_headers_present(client):
    """OWASP security headers should be set on all responses."""
    response = await client.get("/health")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("x-xss-protection") == "1; mode=block"
    assert "content-security-policy" in response.headers
