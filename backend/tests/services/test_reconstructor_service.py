"""
Unit tests for the Reconstructor Service.
We use a mocked asyncpg DB connection.
"""
from unittest.mock import AsyncMock

import pytest

from app.core.lineage_graph import LineageGraph
from app.services.reconstructor_service import ReconstructorService


@pytest.mark.asyncio
async def test_fetch_lineage_graph(mock_db, sample_split_event):
    """It should construct a LineageGraph from the recursive CTE."""
    mock_db.fetch = AsyncMock(return_value=[sample_split_event])

    svc = ReconstructorService(mock_db)
    graph = await svc._fetch_lineage_graph("MP_madhyapradesh_1951")

    assert isinstance(graph, LineageGraph)
    # The edges should map parent to child
    assert "CG_chhattisgarh_2000" in graph._forward["MP_madhyapradesh_1951"][0].target_cdks

@pytest.mark.asyncio
async def test_find_lgds_with_data(mock_db):
    """It should return a set of lgds that have data."""
    mock_db.fetch = AsyncMock(return_value=[{"district_lgd": 123}])

    svc = ReconstructorService(mock_db)
    lgds = await svc._find_lgds_with_data([123, 456], "rice")

    # 456 was not returned by DB mock
    assert 123 in lgds
    assert 456 not in lgds
    assert len(lgds) == 1
