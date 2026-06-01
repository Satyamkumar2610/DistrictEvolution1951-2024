from unittest.mock import AsyncMock, patch

import pytest

from app.api.deps import get_db


def _override_db(mock_db):
    async def _override():
        yield mock_db

    return _override


@pytest.mark.asyncio
async def test_reconstructor_search_returns_typed_results(client):
    mock_db = AsyncMock()
    mock_db.fetch.return_value = [
        {
            "cdk": "BR_patna_1991",
            "display_name": "Patna",
            "era": 1991,
            "is_root": True,
        }
    ]

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        response = await client.get("/api/v1/reconstruct/search?q=Pa")

        assert response.status_code == 200
        assert response.json() == [
            {
                "cdk": "BR_patna_1991",
                "display_name": "Patna",
                "state": "BR",
                "era": 1991,
                "is_root": True,
            }
        ]
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_reconstructor_tree_and_full_reconstruction_routes(client):
    mock_db = AsyncMock()
    service = AsyncMock()
    service.get_lineage_tree.return_value = {
        "cdk": "BR_patna_1991",
        "children": [{"cdk": "BR_nalanda_2000", "split_year": 2000, "children": []}],
    }
    service.reconstruct.return_value = {
        "root_cdk": "BR_patna_1991",
        "root_name": "Patna",
        "crop": "rice",
        "epochs": [
            {
                "epoch_num": 1,
                "year_start": 2000,
                "year_end": 2005,
                "event_label": "Patna split",
                "active_cdks": ["BR_patna_1991"],
                "active_names": ["Patna"],
                "data_cdks": ["BR_patna_1991"],
                "is_fallback": False,
                "data_quality": "direct",
                "confidence_score": 0.95,
                "cdk_resolution": {
                    "BR_patna_1991": {
                        "data_cdk": "BR_patna_1991",
                        "status": "direct",
                    }
                },
                "leaf_cdks": ["BR_patna_1991"],
                "is_virtual": False,
                "reconstructed_geojson": {"type": "Polygon", "coordinates": []},
                "is_contiguous": True,
                "metrics": [
                    {
                        "year": 2000,
                        "data_coverage": 1.0,
                        "collective_yield": 2200.5,
                        "collective_production": 450.0,
                        "collective_area": 204.5,
                        "is_fallback": False,
                        "data_quality": "direct",
                    }
                ],
            }
        ],
    }

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.lineage_reconstructor.ReconstructorService", return_value=service):
            lineage_response = await client.get("/api/v1/reconstruct/BR_patna_1991/lineage")
            reconstruction_response = await client.get(
                "/api/v1/reconstruct/BR_patna_1991?crop=rice&min_year=2000"
            )

        assert lineage_response.status_code == 200
        assert lineage_response.json()["children"][0]["split_year"] == 2000
        assert reconstruction_response.status_code == 200
        body = reconstruction_response.json()
        assert body["root_name"] == "Patna"
        assert body["epochs"][0]["metrics"][0]["collective_yield"] == 2200.5
        service.get_lineage_tree.assert_awaited_once_with("BR_patna_1991")
        service.reconstruct.assert_awaited_once_with("BR_patna_1991", "rice", 2000)
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_reconstructor_ancestors_descendants_and_summary_routes(client):
    mock_db = AsyncMock()

    class _FakeGraph:
        def get_canonical_ancestors(self, cdk, target_year=None):
            assert cdk == "BR_nalanda_2000"
            assert target_year == 1995
            return ["BR_patna_1991"]

        def get_canonical_descendants(self, cdk, from_year=None):
            assert cdk == "BR_patna_1991"
            assert from_year == 2000
            return ["BR_nalanda_2000", "BR_sheikhpura_2000"]

        def get_leaf_descendants(self, cdk):
            assert cdk == "BR_patna_1991"
            return ["BR_nalanda_2000"]

        def summary(self):
            return {
                "total_nodes": 3,
                "total_events": 1,
                "root_nodes": 1,
                "leaf_nodes": 2,
                "event_types": {"SPLIT": 1},
            }

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch(
            "app.api.v1.lineage_reconstructor._build_graph",
            AsyncMock(return_value=_FakeGraph()),
        ):
            ancestors_response = await client.get(
                "/api/v1/reconstruct/BR_nalanda_2000/ancestors?year=1995"
            )
            descendants_response = await client.get(
                "/api/v1/reconstruct/BR_patna_1991/descendants?from_year=2000"
            )
            summary_response = await client.get("/api/v1/reconstruct/graph/summary")

        assert ancestors_response.status_code == 200
        assert ancestors_response.json()["ancestors"] == ["BR_patna_1991"]
        assert descendants_response.status_code == 200
        assert descendants_response.json()["count"] == 2
        assert summary_response.status_code == 200
        assert summary_response.json()["event_types"]["SPLIT"] == 1
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_reconstructor_returns_not_found_when_no_epochs_exist(client):
    mock_db = AsyncMock()
    mock_db.fetchval.return_value = None  # Simulate cdk not found in split_events
    service = AsyncMock()
    service.reconstruct.return_value = {
        "root_cdk": "BR_unknown_1991",
        "crop": "rice",
        "epochs": [],
    }

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.lineage_reconstructor.ReconstructorService", return_value=service):
            response = await client.get("/api/v1/reconstruct/BR_unknown_1991")

        assert response.status_code == 404
    finally:
        del client._transport.app.dependency_overrides[get_db]
