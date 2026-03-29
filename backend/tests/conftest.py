"""
Shared test fixtures for I-ASCAP backend tests.

Provides:
- An async FastAPI test client (httpx.AsyncClient)
- A real database connection for integration tests (when DB is available)
- Mock database helpers for unit tests
"""
import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Ensure test environment
# ---------------------------------------------------------------------------
os.environ.setdefault("DATABASE_URL", "postgresql://user:password@localhost:5432/i_ascap")


# ---------------------------------------------------------------------------
# FastAPI Test Client (integration tests)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def client() -> AsyncGenerator:
    """Async test client that talks to the real FastAPI app."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Mock Database Connection (unit tests)
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_db():
    """
    Returns a mock asyncpg.Connection with common methods stubbed.
    Use this for unit-testing services without a real database.
    """
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    return conn


# ---------------------------------------------------------------------------
# Sample Data Factories
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_split_event():
    """A minimal split event record."""
    return {
        "parent_cdk": "MP_madhyapradesh_1951",
        "child_cdks": ["CG_chhattisgarh_2000", "MP_madhyapradesh_2000"],
        "split_year": 2000,
    }


@pytest.fixture
def sample_agri_metric():
    """A minimal agri_metrics record."""
    return {
        "cdk": "UP_lucknow_2000",
        "crop": "wheat",
        "year": 2015,
        "yield": 3200.0,
        "area": 15000.0,
        "production": 48000000.0,
    }
