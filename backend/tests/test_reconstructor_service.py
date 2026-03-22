import pytest  # type: ignore[import-not-found]
from app.services.reconstructor_service import ReconstructorService  # type: ignore[import-not-found]

from typing import Any, Dict, List, Optional, Tuple


class FakeDB:
    """
    Mock DB that simulates the query pipeline used by ReconstructorService:
    1. split_events  → graph building
    2. district_snapshots → name resolution + geometry
    3. districts → CDK→LGD bridge (name matching)
    4. agri_metrics → yield data (keyed by district_lgd)
    """
    def __init__(
        self,
        metrics: Optional[List[Dict[str, Any]]] = None,
        splits: Optional[List[Dict[str, Any]]] = None,
        geom: Optional[Dict[str, str]] = None,
        lgd_map: Optional[Dict[str, int]] = None,
    ):
        self.metrics: List[Dict[str, Any]] = metrics or []
        self.splits: List[Dict[str, Any]] = splits or []
        self.geom: Dict[str, str] = geom or {"geojson": '{"type": "Polygon"}', "type": "POLYGON"}
        # lgd_map: maps CDK text → LGD code (int), e.g. {"B": 101, "C": 102}
        self.lgd_map: Dict[str, int] = lgd_map or {}
        self.queries: List[Tuple[str, tuple]] = []

    async def fetch(self, query: str, *args: Any) -> List[Dict[str, Any]]:
        self.queries.append((query, args))
        if "split_events" in query:
            return self.splits
        if "agri_metrics" in query:
            # Filter metrics by the requested district_lgd list
            lgd_list = args[0] if args else []
            prod_var = args[1] if len(args) > 1 else ""
            area_var = args[2] if len(args) > 2 else ""
            return [
                m for m in self.metrics
                if m["district_lgd"] in lgd_list
                and m["variable_name"] in (prod_var, area_var)
            ]
        return []

    async def fetchval(self, query: str, *args: Any) -> Any:
        self.queries.append((query, args))
        if "district_snapshots" in query and "district_name" in query:
            # Name resolution: return a name based on CDK
            cdk = args[0] if args else ""
            return cdk  # Just return the CDK as the name for simplicity
        if "districts" in query and "lgd_code" in query:
            # CDK→LGD bridge lookup
            name_pattern: str = str(args[0]).strip("%") if args else ""
            # Find matching LGD code from our map
            for cdk_key, lgd in self.lgd_map.items():
                if name_pattern.lower() in cdk_key.lower():
                    return lgd
            return None
        return 1

    async def fetchrow(self, query, *args):
        self.queries.append((query, args))
        if "district_snapshots" in query and "district_name" in query:
            cdk = args[0] if args else ""
            return {"district_name": cdk}
        if "ST_Union" in query or "ST_AsGeoJSON" in query:
            return self.geom
        return None


@pytest.mark.asyncio
async def test_reconstructor_yield_aggregation():
    # A splits into B & C
    splits = [
        {"parent_cdk": "A", "child_cdks": ["B", "C"], "split_year": 1980}
    ]
    # LGD mapping: B → 101, C → 102
    lgd_map = {"B": 101, "C": 102}
    # In 1980, B(101) produces 100 on 50ha, C(102) produces 300 on 150ha
    metrics = [
        {"district_lgd": 101, "year": 1980, "variable_name": "rice_production", "value": 100},
        {"district_lgd": 101, "year": 1980, "variable_name": "rice_area", "value": 50},
        {"district_lgd": 102, "year": 1980, "variable_name": "rice_production", "value": 300},
        {"district_lgd": 102, "year": 1980, "variable_name": "rice_area", "value": 150},
    ]

    db = FakeDB(metrics=metrics, splits=splits, lgd_map=lgd_map)
    svc = ReconstructorService(db)

    res = await svc.reconstruct("A", crop="rice", min_year=1978)

    # Epoch 2 covers 1980+
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
    # Only B and C have LGD mappings. D has no mapping → no data.
    lgd_map = {"B": 101, "C": 102}
    metrics = [
        {"district_lgd": 101, "year": 1980, "variable_name": "rice_production", "value": 100},
        {"district_lgd": 101, "year": 1980, "variable_name": "rice_area", "value": 50},
        {"district_lgd": 102, "year": 1980, "variable_name": "rice_production", "value": 300},
        {"district_lgd": 102, "year": 1980, "variable_name": "rice_area", "value": 150},
    ]

    db = FakeDB(metrics=metrics, splits=splits, lgd_map=lgd_map)
    svc = ReconstructorService(db)

    res = await svc.reconstruct("A", crop="rice", min_year=1978)

    epoch2 = res["epochs"][1]
    metrics_1980 = [m for m in epoch2["metrics"] if m["year"] == 1980][0]

    # 2 out of 3 active CDKs (B, C, D) have data → 2/3 coverage (rounded to 3dp)
    assert metrics_1980["data_coverage"] == pytest.approx(2 / 3, abs=0.001)
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
    lgd_map = {"A": 100}
    db = FakeDB(metrics=[], splits=[], lgd_map=lgd_map)
    svc = ReconstructorService(db)
    await svc.reconstruct("A", crop="wheat")

    agri_queries = [q for q in db.queries if "agri_metrics" in q[0]]
    # Should have queried agri_metrics with wheat_production and wheat_area
    assert len(agri_queries) > 0
    agri_query = agri_queries[0]
    assert "wheat_production" in agri_query[1]
    assert "wheat_area" in agri_query[1]


@pytest.mark.asyncio
async def test_reconstructor_is_contiguous():
    geom = {"geojson": '{"type": "MultiPolygon"}', "type": "MULTIPOLYGON"}
    db = FakeDB(metrics=[], splits=[], geom=geom)
    svc = ReconstructorService(db)

    res = await svc.reconstruct("A")
    assert res["epochs"][0]["is_contiguous"] is False
