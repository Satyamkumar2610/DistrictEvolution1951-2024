from typing import Any

import pytest  # type: ignore[import-not-found]

from app.services.reconstructor_service import ReconstructorService  # type: ignore[import-not-found]


class FakeDB:
    """
    Mock DB that simulates the query pipeline used by ReconstructorService:
    1. split_events  → graph building
    2. districts / district_snapshots → name resolution + geometry
    3. agri_metrics → yield data (keyed by cdk TEXT)
    """
    def __init__(
        self,
        metrics: list[dict[str, Any]] | None = None,
        splits: list[dict[str, Any]] | None = None,
        geom: dict[str, str] | None = None,
        available_cdks: set[str] | None = None,
    ):
        self.metrics: list[dict[str, Any]] = metrics or []
        self.splits: list[dict[str, Any]] = splits or []
        self.geom: dict[str, str] = geom or {"geojson": '{"type": "Polygon"}', "type": "POLYGON"}
        # CDKs that exist in agri_metrics (for _find_cdks_with_data)
        self.available_cdks: set[str] = available_cdks or {m["cdk"] for m in (metrics or [])}
        self.queries: list[tuple[str, tuple]] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.queries.append((query, args))
        if "split_events" in query:
            return self.splits
        if "DISTINCT cdk" in query:
            # _find_cdks_with_data query
            cdk_list = args[0] if args else []
            return [{"cdk": c} for c in cdk_list if c in self.available_cdks]
        if "agri_metrics" in query:
            # Filter metrics by the requested CDK list
            cdk_list = args[0] if args else []
            prod_var = args[1] if len(args) > 1 else ""
            area_var = args[2] if len(args) > 2 else ""
            return [
                m for m in self.metrics
                if m["cdk"] in cdk_list
                and m["variable_name"] in (prod_var, area_var)
            ]
        return []

    async def fetchval(self, query: str, *args: Any) -> Any:
        self.queries.append((query, args))
        if "districts" in query and "district_name" in query:
            return None  # No name found in districts table
        if "district_snapshots" in query and "district_name" in query:
            cdk = args[0] if args else ""
            return cdk  # Return CDK as name for simplicity
        return 1

    async def fetchrow(self, query: str, *args: Any) -> Any:
        self.queries.append((query, args))
        if "district_snapshots" in query and "district_name" in query:
            cdk = args[0] if args else ""
            return {"district_name": cdk}
        if "ST_Union" in query or "ST_AsGeoJSON" in query:
            return self.geom
        return None


@pytest.mark.asyncio
async def test_reconstructor_yield_aggregation():
    """Direct CDK data — no fallback needed."""
    splits = [
        {"parent_cdk": "A", "child_cdks": ["B", "C"], "split_year": 1980}
    ]
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

    assert metrics_1980["collective_yield"] == 2000.0
    assert metrics_1980["collective_production"] == 400.0
    assert metrics_1980["collective_area"] == 200.0
    assert metrics_1980["data_coverage"] == 1.0
    assert epoch2["is_fallback"] is False
    # New fields
    assert epoch2["data_quality"] == "direct"
    assert epoch2["confidence_score"] > 0.7
    assert metrics_1980["data_quality"] == "direct"
    assert "B" in epoch2["cdk_resolution"]
    assert epoch2["cdk_resolution"]["B"]["status"] == "direct"


@pytest.mark.asyncio
async def test_reconstructor_partial_coverage():
    """D has no data → truthful partial coverage (2/3 = 0.667)."""
    splits = [
        {"parent_cdk": "A", "child_cdks": ["B", "C", "D"], "split_year": 1980}
    ]
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

    # Coverage now reflects truthful 2/3 active CDKs
    assert metrics_1980["data_coverage"] == pytest.approx(0.667, abs=0.01)
    assert metrics_1980["collective_yield"] == 2000.0
    assert metrics_1980["collective_production"] == 400.0
    assert metrics_1980["collective_area"] == 200.0
    # Data quality reflects partial coverage
    assert epoch2["data_quality"] == "partial"
    assert epoch2["confidence_score"] < 1.0


@pytest.mark.asyncio
async def test_reconstructor_ancestor_fallback():
    """
    Children B, C have no data. Parent A has data.
    Service should fall back to parent A's data.
    """
    splits = [
        {"parent_cdk": "A", "child_cdks": ["B", "C"], "split_year": 1980}
    ]
    # Only A has data, not B or C
    metrics = [
        {"cdk": "A", "year": 1980, "variable_name": "rice_production", "value": 500},
        {"cdk": "A", "year": 1980, "variable_name": "rice_area", "value": 200},
    ]

    db = FakeDB(metrics=metrics, splits=splits)
    svc = ReconstructorService(db)

    res = await svc.reconstruct("A", crop="rice", min_year=1978)

    # Epoch 2 (1980+): should use A's data as fallback
    epoch2 = res["epochs"][1]
    assert epoch2["is_fallback"] is True
    assert "A" in epoch2["data_cdks"]

    metrics_1980 = [m for m in epoch2["metrics"] if m["year"] == 1980][0]
    assert metrics_1980["collective_yield"] == 2500.0  # 500/200*1000
    assert metrics_1980["collective_production"] == 500.0
    assert metrics_1980["is_fallback"] is True
    # New fields
    assert epoch2["data_quality"] == "ancestor_fallback"
    assert epoch2["confidence_score"] < 0.8
    assert epoch2["cdk_resolution"]["B"]["status"] == "ancestor"
    assert epoch2["cdk_resolution"]["C"]["status"] == "ancestor"


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
    assert metrics_1978["data_quality"] == "no_data"


@pytest.mark.asyncio
async def test_reconstructor_crop_filter():
    """Verify that the correct crop-specific variable names are queried."""
    splits = [
        {"parent_cdk": "A", "child_cdks": ["B", "C"], "split_year": 1980}
    ]
    metrics = [
        {"cdk": "B", "year": 1980, "variable_name": "wheat_production", "value": 100},
        {"cdk": "B", "year": 1980, "variable_name": "wheat_area", "value": 50},
    ]
    db = FakeDB(metrics=metrics, splits=splits)
    svc = ReconstructorService(db)
    await svc.reconstruct("A", crop="wheat")

    agri_queries = [q for q in db.queries if "agri_metrics" in q[0] and "DISTINCT" not in q[0]]
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


@pytest.mark.asyncio
async def test_reconstructor_pre_split_epoch_uses_root():
    """
    Pre-split epoch (before split year) should use root CDK data.
    """
    splits = [
        {"parent_cdk": "ROOT", "child_cdks": ["X", "Y"], "split_year": 1990}
    ]
    metrics = [
        {"cdk": "ROOT", "year": 1985, "variable_name": "rice_production", "value": 100},
        {"cdk": "ROOT", "year": 1985, "variable_name": "rice_area", "value": 50},
    ]

    db = FakeDB(metrics=metrics, splits=splits)
    svc = ReconstructorService(db)

    res = await svc.reconstruct("ROOT", crop="rice", min_year=1980)

    epoch1 = res["epochs"][0]
    assert "ROOT" in epoch1["active_cdks"]
    m_1985 = [m for m in epoch1["metrics"] if m["year"] == 1985][0]
    assert m_1985["collective_yield"] == 2000.0


@pytest.mark.asyncio
async def test_reconstructor_mixed_resolution():
    """
    B has data, C does not but parent A does → mixed resolution.
    """
    splits = [
        {"parent_cdk": "A", "child_cdks": ["B", "C"], "split_year": 1980}
    ]
    metrics = [
        {"cdk": "B", "year": 1980, "variable_name": "rice_production", "value": 100},
        {"cdk": "B", "year": 1980, "variable_name": "rice_area", "value": 50},
        {"cdk": "A", "year": 1980, "variable_name": "rice_production", "value": 500},
        {"cdk": "A", "year": 1980, "variable_name": "rice_area", "value": 200},
    ]

    db = FakeDB(metrics=metrics, splits=splits)
    svc = ReconstructorService(db)

    res = await svc.reconstruct("A", crop="rice", min_year=1978)

    epoch2 = res["epochs"][1]
    # B is direct, C falls back to A
    assert epoch2["cdk_resolution"]["B"]["status"] == "direct"
    assert epoch2["cdk_resolution"]["C"]["status"] == "ancestor"
    assert epoch2["cdk_resolution"]["C"]["data_cdk"] == "A"
    assert epoch2["data_quality"] == "partial"


@pytest.mark.asyncio
async def test_data_quality_classification():
    """Test the static _classify_data_quality method."""
    classify = ReconstructorService._classify_data_quality

    # All direct
    assert classify({"A": ("A", "direct"), "B": ("B", "direct")}) == "direct"

    # Mixed direct + ancestor
    assert classify({"A": ("A", "direct"), "B": ("P", "ancestor")}) == "partial"

    # All ancestor fallback
    assert classify({"A": ("P", "ancestor"), "B": ("P", "ancestor")}) == "ancestor_fallback"

    # All missing with no data
    assert classify({"A": (None, "missing"), "B": (None, "missing")}) == "no_data"

    # Empty
    assert classify({}) == "no_data"

