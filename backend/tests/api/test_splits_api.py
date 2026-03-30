from unittest.mock import AsyncMock, patch

import pytest

from app.api.deps import get_db
from app.services.drift_detector import DriftResult


def _override_db(mock_db):
    async def _override():
        yield mock_db

    return _override


@pytest.mark.asyncio
async def test_split_enrichment_endpoint_groups_transfer_metrics(client):
    mock_db = AsyncMock()
    mock_db.fetchrow.return_value = {
        "id": 7,
        "parent_cdk": "BR_patna_1991",
        "child_cdks": ["BR_nalanda_2000"],
        "split_year": 2000,
        "parent_area_sqkm": 120.0,
        "total_child_area_sqkm": 119.0,
    }
    mock_db.fetch.return_value = [
        {
            "transfer_id": 11,
            "from_district": "Patna",
            "to_district": "Nalanda",
            "transfer_type": "transferred_in",
            "transfer_area": 35.5,
            "dataset_name": "osm_overpass",
            "metric_name": "school_count",
            "value": 12.0,
            "unit": "count",
            "reference_year": 2000,
            "source_url": "https://example.com/source",
        }
    ]

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        response = await client.get("/api/v1/spatial/enrichment/7")

        assert response.status_code == 200
        body = response.json()
        assert body["event_id"] == 7
        assert body["transfers"][0]["metrics"][0]["metric"] == "school_count"
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_split_trigger_gazette_and_batch_import_routes(client):
    mock_db = AsyncMock()
    mock_db.fetchrow.return_value = {"id": 7}

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.splits._run_enrichment", AsyncMock()), patch(
            "app.api.v1.splits.parse_gazette_text",
            return_value=[
                type(
                    "ParsedEvent",
                    (),
                    {
                        "parent_district": "Patna",
                        "child_districts": ["Nalanda", "Sheikhpura"],
                        "year": 2000,
                        "state": "Bihar",
                        "confidence": 0.82,
                        "raw_text": "Patna split into Nalanda and Sheikhpura.",
                    },
                )()
            ],
        ), patch(
            "app.api.v1.splits.load_lineage_csv",
            AsyncMock(
                return_value={
                    "dry_run": True,
                    "total_csv_rows": 12,
                    "unique_events": 3,
                    "sample_events": [
                        {
                            "parent": "BR_patna_1991",
                            "year": 2000,
                            "children": ["BR_nalanda_2000"],
                        }
                    ],
                }
            ),
        ):
            trigger_response = await client.post("/api/v1/spatial/enrichment/trigger?event_id=7")
            gazette_response = await client.post(
                "/api/v1/spatial/gazette/parse",
                json={"text": "Patna split into Nalanda and Sheikhpura in 2000."},
            )
            batch_response = await client.post(
                "/api/v1/spatial/lineage/batch-import?source=lineage&dry_run=true"
            )

        assert trigger_response.status_code == 200
        assert "running in background" in trigger_response.json()["message"]
        assert gazette_response.status_code == 200
        assert gazette_response.json()["parsed_events"][0]["parent_district"] == "Patna"
        assert batch_response.status_code == 200
        assert batch_response.json()["sample_events"][0]["parent"] == "BR_patna_1991"
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_split_batch_import_rejects_invalid_source(client):
    mock_db = AsyncMock()
    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        response = await client.post("/api/v1/spatial/lineage/batch-import?source=invalid")

        assert response.status_code == 400
        assert "source must be" in response.json()["detail"]
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_split_drift_endpoint_supports_single_comparison_and_timeline(client):
    mock_db = AsyncMock()
    detector = AsyncMock()
    detector.detect_drift.return_value = DriftResult(
        district_cdk="BR_patna_1991",
        year_a=1991,
        year_b=2000,
        hausdorff_km=2.4,
        area_a_sqkm=100.0,
        area_b_sqkm=95.0,
        area_change_pct=-5.0,
        overlap_area_sqkm=90.0,
        jaccard_index=0.88,
        centroid_shift_km=1.2,
        shape_similarity=0.91,
        source_a="survey",
        source_b="survey",
    )
    detector.get_drift_timeline.return_value = [
        DriftResult(
            district_cdk="BR_patna_1991",
            year_a=1991,
            year_b=2000,
            hausdorff_km=2.4,
            area_a_sqkm=100.0,
            area_b_sqkm=95.0,
            area_change_pct=-5.0,
            overlap_area_sqkm=90.0,
            jaccard_index=0.88,
            centroid_shift_km=1.2,
            shape_similarity=0.91,
            source_a="survey",
            source_b="survey",
        )
    ]

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        with patch("app.api.v1.splits.DriftDetector", return_value=detector):
            comparison_response = await client.get("/api/v1/spatial/drift/BR_patna_1991")
            timeline_response = await client.get("/api/v1/spatial/drift/BR_patna_1991?timeline=true")

        assert comparison_response.status_code == 200
        assert comparison_response.json()["shape_similarity"] == 0.91
        assert timeline_response.status_code == 200
        assert timeline_response.json()["total_comparisons"] == 1
    finally:
        del client._transport.app.dependency_overrides[get_db]


@pytest.mark.asyncio
async def test_split_quality_overview_endpoint_returns_aggregate_summary(client):
    mock_db = AsyncMock()
    mock_db.fetchval.side_effect = [100, 80, 12, 35, 5, 20]
    mock_db.fetch.side_effect = [
        [
            {"geometry_status": "resolved", "count": 9},
            {"geometry_status": "unknown", "count": 3},
        ],
        [
            {"bucket": "high", "count": 8},
            {"bucket": "medium", "count": 4},
        ],
        [
            {"transfer_type": "transferred_in", "count": 11, "total_area_sqkm": 42.5},
            {"transfer_type": "gap", "count": 9, "total_area_sqkm": 12.0},
        ],
        [
            {"geometry_source": "manual_upload", "count": 20},
            {"geometry_source": "survey", "count": 60},
        ],
    ]

    client._transport.app.dependency_overrides[get_db] = _override_db(mock_db)
    try:
        response = await client.get("/api/v1/spatial/quality/overview")

        assert response.status_code == 200
        body = response.json()
        assert body["districts"]["geometry_coverage_pct"] == 80.0
        assert body["split_events"]["by_status"]["resolved"] == 9
        assert body["transfers"]["by_type"][0]["type"] == "transferred_in"
        assert body["geometry_sources"]["survey"] == 60
    finally:
        del client._transport.app.dependency_overrides[get_db]
