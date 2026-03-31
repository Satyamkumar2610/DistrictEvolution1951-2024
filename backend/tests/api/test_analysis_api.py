from unittest.mock import AsyncMock, patch

import pytest

from app.api.deps import get_db


def _override_db(mock_db):
    async def _override():
        yield mock_db

    return _override


def _analysis_payload() -> dict:
    return {
        "data": [
            {"year": 1999, "parent": 1000.0, "combined_children": None},
            {"year": 2000, "parent": None, "combined_children": 1100.0},
        ],
        "series": [
            {"id": "parent", "label": "Parent", "style": "solid"},
            {"id": "combined_children", "label": "Children", "style": "dashed"},
        ],
        "advanced_stats": {
            "pre": {
                "mean": 1000.0,
                "variance": 25.0,
                "cv": 5.0,
                "cagr": 1.2,
                "n_observations": 5,
            },
            "post": {
                "mean": 1100.0,
                "variance": 36.0,
                "cv": 4.5,
                "cagr": 2.1,
                "n_observations": 5,
            },
            "impact": {
                "absolute_change": 100.0,
                "pct_change": 10.0,
                "uncertainty": {
                    "lower": 4.0,
                    "upper": 16.0,
                    "method": "bootstrap_95",
                    "confidence": 0.95,
                },
            },
            "insights": None,
        },
        "meta": {
            "split_year": 2000,
            "mode": "before_after",
            "metric": "yield",
            "variable": "wheat_yield",
            "parent_cdk": "101",
            "children_cdks": ["201", "202"],
        },
        "provenance": {
            "dataset_version": "v1.5",
            "boundary_version": "2024.01",
            "query_hash": "sha256:testhash",
            "generated_at": "2025-01-01T00:00:00Z",
            "harmonization_method": "panel_v1",
            "warnings": [],
        },
    }


@pytest.mark.asyncio
async def test_get_summary_returns_typed_state_stats(client):
    mock_db = AsyncMock()
    mock_db.fetch.side_effect = [
        [
            {"state_name": "Bihar", "total_districts": 38},
            {"state_name": "Punjab", "total_districts": 23},
        ],
        [
            {"state_name": "BIHAR", "boundary_changes": 7},
        ],
    ]

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        response = await client.get("/api/v1/analysis/split-impact/summary")
        assert response.status_code == 200

        data = response.json()
        assert data["states"] == ["Bihar", "Punjab"]
        assert data["stats"]["Bihar"]["total"] == 38
        assert data["stats"]["Bihar"]["total_districts"] == 38
        assert data["stats"]["Bihar"]["changed"] == 7
        assert data["stats"]["Bihar"]["boundary_changes"] == 7
        assert data["stats"]["Punjab"]["comparability"] == "N/A"
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_get_split_impact_districts_returns_response_model_shape(client):
    mock_db = AsyncMock()
    mock_db.fetch.side_effect = [
        [
            {
                "parent_district": "Old District",
                "child_district": "North District",
                "split_year": 2000,
                "state_name": "Bihar",
                "parent_lgd": 101,
                "child_lgd": 201,
            },
            {
                "parent_district": "Old District",
                "child_district": "South District",
                "split_year": 2000,
                "state_name": "Bihar",
                "parent_lgd": 101,
                "child_lgd": None,
            },
        ],
        [
            {
                "cdk": "101",
                "dn": "old district",
                "sn": "bihar",
            },
            {
                "cdk": "201",
                "dn": "north district",
                "sn": "bihar",
            },
        ],
        [
            {"district_lgd": 101},
            {"district_lgd": 201},
        ],
    ]

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.services.name_resolver.resolve_lgd", return_value=None):
            response = await client.get("/api/v1/analysis/split-impact/districts?state=Bihar")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "Old District_2000"
        assert data[0]["parent_name"] == "Old District"
        assert data[0]["children_names"] == ["North District", "South District"]
        assert data[0]["children_cdks"] == ["201", None]
        assert data[0]["resolved_count"] == 1
        assert data[0]["total_count"] == 2
        assert data[0]["parent_has_agri"] is True
        assert data[0]["children_has_agri"] == [True, False]
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_analyze_split_impact_returns_cached_result_when_present(client):
    mock_db = AsyncMock()
    mock_cache = AsyncMock()
    mock_cache.get.return_value = _analysis_payload()

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.cache.get_cache", return_value=mock_cache), patch(
            "app.api.v1.analysis.AnalysisService"
        ) as analysis_service:
            response = await client.get(
                "/api/v1/analysis/split-impact/analysis"
                "?parent=101&children=201,202&splitYear=2000&crop=wheat&metric=yield&mode=before_after"
            )

        assert response.status_code == 200
        assert response.json()["meta"]["parent_cdk"] == "101"
        analysis_service.assert_not_called()
        mock_cache.set.assert_not_called()
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_analyze_split_impact_computes_and_caches_result(client):
    mock_db = AsyncMock()
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None
    mock_service = AsyncMock()
    mock_service.analyze_split_impact.return_value = _analysis_payload()

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.cache.get_cache", return_value=mock_cache), patch(
            "app.api.v1.analysis.AnalysisService", return_value=mock_service
        ):
            response = await client.get(
                "/api/v1/analysis/split-impact/analysis"
                "?parent=101&children=201,202&splitYear=2000&crop=wheat&metric=yield&mode=before_after"
            )

        assert response.status_code == 200
        body = response.json()
        assert body["advanced_stats"]["impact"]["pct_change"] == 10.0
        mock_service.analyze_split_impact.assert_awaited_once()
        mock_cache.set.assert_awaited_once()
    finally:
        del client._transport.app.dependency_overrides[get_db]
