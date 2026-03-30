from unittest.mock import AsyncMock, patch

import pytest

from app.api.deps import get_db


def _override_db(mock_db):
    async def _override():
        yield mock_db

    return _override


@pytest.mark.asyncio
async def test_calculate_split_endpoint_uses_spatial_service(client):
    with patch("app.api.v1.spatial.SpatialService") as service_cls:
        service_cls.return_value.calculate_split_areas.return_value = {
            "transferred_area_sqkm": 120.5,
            "remaining_area_sqkm": 340.2,
        }
        response = await client.post(
            "/api/v1/spatial/calculate-split",
            files={
                "parent_geojson": ("parent.geojson", b'{"type":"Feature","geometry":{"type":"Polygon","coordinates":[]}}', "application/json"),
                "child_geojson": ("child.geojson", b'{"type":"Feature","geometry":{"type":"Polygon","coordinates":[]}}', "application/json"),
            },
        )

    assert response.status_code == 200
    assert response.json()["transferred_area_sqkm"] == 120.5
    service_cls.return_value.calculate_split_areas.assert_called_once()


@pytest.mark.asyncio
async def test_spatial_diff_lineage_and_upload_endpoints(client):
    mock_db = AsyncMock()
    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.spatial.SpatialService") as service_cls:
            service = service_cls.return_value
            service.calculate_spatial_diff = AsyncMock(
                return_value={
                    "status": "success",
                    "message": "Calculated split diff for event 7",
                }
            )
            service.get_district_lineage = AsyncMock(
                return_value={
                    "district_id": "101",
                    "split_events": [{"id": 1, "parent_cdk": "101", "child_cdks": ["201"]}],
                    "area_transfers": [{"id": 10, "source_cdk": "101", "dest_cdk": "201", "area_sqkm": 55.4}],
                }
            )
            service.upload_manual_geojson = AsyncMock(
                return_value={
                    "status": "success",
                    "message": "Uploaded manual GeoJSON for 101 (2020)",
                }
            )

            diff_response = await client.post("/api/v1/spatial/diff?split_event_id=7")
            lineage_response = await client.get("/api/v1/spatial/lineage/101")
            upload_response = await client.post(
                "/api/v1/spatial/upload-geojson",
                data={"district_id": "101", "snapshot_year": "2020"},
                files={"geojson_file": ("district.geojson", b'{"type":"Feature","geometry":{"type":"Polygon","coordinates":[]}}', "application/json")},
            )

        assert diff_response.status_code == 200
        assert diff_response.json()["status"] == "success"
        assert lineage_response.status_code == 200
        assert lineage_response.json()["split_events"][0]["parent_cdk"] == "101"
        assert upload_response.status_code == 200
        assert "Uploaded manual GeoJSON" in upload_response.json()["message"]

        service.calculate_spatial_diff.assert_awaited_once_with(7)
        service.get_district_lineage.assert_awaited_once_with("101")
        service.upload_manual_geojson.assert_awaited_once()
    finally:
        del client._transport.app.dependency_overrides[get_db]
