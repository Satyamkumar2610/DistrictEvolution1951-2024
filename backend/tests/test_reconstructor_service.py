import pytest
import json
from unittest.mock import AsyncMock
from app.services.reconstructor_service import ReconstructorService

class FakeDB:
    def __init__(self, metrics=None, splits=None, geom=None):
        self.metrics = metrics or []
        self.splits = splits or []
        self.geom = geom or {"geojson": '{"type": "Polygon"}', "type": "POLYGON"}
        self.queries = []
        
    async def fetch(self, query, *args):
        self.queries.append((query, args))
        if "split_events" in query:
            return self.splits
        if "agri_metrics" in query:
            return self.metrics
        return []
        
    async def fetchval(self, query, *args):
        return 1
        
    async def fetchrow(self, query, *args):
        return self.geom

@pytest.mark.asyncio
async def test_reconstructor_yield_aggregation():
    # A splits into B & C
    splits = [
        {"parent_cdk": "A", "child_cdks": ["B", "C"], "split_year": 1980}
    ]
    # In 1980, B produces 100 on 50ha (yield 2000), C produces 300 on 150ha (yield 2000). Total: 400 on 200ha = 2000 yield
    metrics = [
        {"cdk": "B", "year": 1980, "variable_name": "rice_production", "value": 100},
        {"cdk": "B", "year": 1980, "variable_name": "rice_area", "value": 50},
        {"cdk": "C", "year": 1980, "variable_name": "rice_production", "value": 300},
        {"cdk": "C", "year": 1980, "variable_name": "rice_area", "value": 150},
    ]
    
    db = FakeDB(metrics=metrics, splits=splits)
    svc = ReconstructorService(db)
    
    res = await svc.reconstruct("A", crop="rice", min_year=1978)
    
    # Epoch 2 covers 1980
    epoch2 = res["epochs"][1]
    metrics_1980 = [m for m in epoch2["metrics"] if m["year"] == 1980][0]
    
    # 400 / 200 * 1000 = 2000 yield
    assert metrics_1980["collective_yield"] == 2000.0
    assert metrics_1980["collective_production"] == 400.0
    assert metrics_1980["collective_area"] == 200.0
    assert metrics_1980["data_coverage"] == 1.0

@pytest.mark.asyncio
async def test_reconstructor_partial_coverage():
    # A splits into B, C, D in 1980
    splits = [
        {"parent_cdk": "A", "child_cdks": ["B", "C", "D"], "split_year": 1980}
    ]
    # Only B and C have data. D is missing.
    metrics = [
        {"cdk": "B", "year": 1980, "variable_name": "rice_production", "value": 100},
        {"cdk": "B", "year": 1980, "variable_name": "rice_area", "value": 50},
        {"cdk": "C", "year": 1980, "variable_name": "rice_production", "value": 300},
        {"cdk": "C", "year": 1980, "variable_name": "rice_area", "value": 150},
    ]
    
    db = FakeDB(metrics=metrics, splits=splits)
    svc = ReconstructorService(db)
    
    res = await svc.reconstruct("A", crop="rice", min_year=1978)
    
    epoch2 = res["epochs"][1]
    metrics_1980 = [m for m in epoch2["metrics"] if m["year"] == 1980][0]
    
    # 2 out of 3 active CDKs (B, C, D) have data -> 2/3 coverage
    assert metrics_1980["data_coverage"] == pytest.approx(2/3)
    assert metrics_1980["collective_yield"] == 2000.0
    assert metrics_1980["collective_production"] == 400.0
    assert metrics_1980["collective_area"] == 200.0


@pytest.mark.asyncio
async def test_reconstructor_zero_data():
    db = FakeDB(metrics=[], splits=[])
    svc = ReconstructorService(db)
    
    res = await svc.reconstruct("A", crop="rice", min_year=1978)
    epoch = res["epochs"][0]
    metrics_1978 = [m for m in epoch["metrics"] if m["year"] == 1978][0]
    
    assert metrics_1978["collective_yield"] is None
    assert metrics_1978["collective_production"] is None
    assert metrics_1978["collective_area"] is None
    assert metrics_1978["data_coverage"] == 0.0


@pytest.mark.asyncio
async def test_reconstructor_crop_filter():
    db = FakeDB(metrics=[], splits=[])
    svc = ReconstructorService(db)
    await svc.reconstruct("A", crop="wheat")
    
    agri_query = [q for q in db.queries if "agri_metrics" in q[0]][0]
    # Verify crop is parameterized correctly 
    # The query args are [list_of_cdks, 'wheat_production', 'wheat_area']
    assert "wheat_production" in agri_query[1]
    assert "wheat_area" in agri_query[1]


@pytest.mark.asyncio
async def test_reconstructor_is_contiguous():
    geom = {"geojson": '{"type": "MultiPolygon"}', "type": "MULTIPOLYGON"}
    db = FakeDB(metrics=[], splits=[], geom=geom)
    svc = ReconstructorService(db)
    
    res = await svc.reconstruct("A")
    assert res["epochs"][0]["is_contiguous"] is False
