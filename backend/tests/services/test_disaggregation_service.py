import csv
import json

import pytest

from app.services.disaggregation_service import DisaggregationService


def _write_csv(path, fieldnames, rows):
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path, rows):
    with open(path, "w") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


@pytest.mark.asyncio
async def test_get_event_series_derives_yield_from_production_and_area(tmp_path):
    packet_path = tmp_path / "packets.jsonl"
    weight_path = tmp_path / "weights.csv"
    panel_path = tmp_path / "panel.csv"

    _write_jsonl(
        packet_path,
        [
            {
                "event_id": "PARENT:2000",
                "split_event_id": None,
                "parent_cdk": "PARENT",
                "parent_name": "Parent",
                "child_cdks": ["CHILD_A", "CHILD_B"],
                "child_names": ["Child A", "Child B"],
                "state": "State X",
                "split_year": 2000,
                "effective_date": None,
                "event_type": "SPLIT",
                "source_quality": "official_compiled",
                "source_urls": [],
                "source_text_path": None,
                "aliases": ["Parent", "Child A", "Child B"],
                "geometry_status": "unknown",
                "weight_status": "proxy_ready",
                "readiness_tier": "Tier B",
                "notes": "test packet",
            }
        ],
    )
    _write_csv(
        weight_path,
        [
            "event_id",
            "child_cdk",
            "child_name",
            "metric_basis",
            "weight_value",
            "weight_method",
            "weight_confidence",
            "source_year",
            "basis",
            "is_fallback",
        ],
        [
            {
                "event_id": "PARENT:2000",
                "child_cdk": "CHILD_A",
                "child_name": "Child A",
                "metric_basis": "area",
                "weight_value": "0.25",
                "weight_method": "post_split_crop_area_proxy",
                "weight_confidence": "0.7",
                "source_year": "2000",
                "basis": "proxy",
                "is_fallback": "false",
            },
            {
                "event_id": "PARENT:2000",
                "child_cdk": "CHILD_A",
                "child_name": "Child A",
                "metric_basis": "production",
                "weight_value": "0.25",
                "weight_method": "post_split_crop_area_proxy",
                "weight_confidence": "0.7",
                "source_year": "2000",
                "basis": "proxy",
                "is_fallback": "false",
            },
            {
                "event_id": "PARENT:2000",
                "child_cdk": "CHILD_B",
                "child_name": "Child B",
                "metric_basis": "area",
                "weight_value": "0.75",
                "weight_method": "post_split_crop_area_proxy",
                "weight_confidence": "0.7",
                "source_year": "2000",
                "basis": "proxy",
                "is_fallback": "false",
            },
            {
                "event_id": "PARENT:2000",
                "child_cdk": "CHILD_B",
                "child_name": "Child B",
                "metric_basis": "production",
                "weight_value": "0.75",
                "weight_method": "post_split_crop_area_proxy",
                "weight_confidence": "0.7",
                "source_year": "2000",
                "basis": "proxy",
                "is_fallback": "false",
            },
        ],
    )
    _write_csv(
        panel_path,
        ["year", "cdk", "harmonization_method", "rice_area", "rice_production", "rice_yield"],
        [
            {"year": "1998", "cdk": "PARENT", "harmonization_method": "Raw", "rice_area": "100", "rice_production": "300", "rice_yield": "3000"},
            {"year": "1999", "cdk": "PARENT", "harmonization_method": "Raw", "rice_area": "120", "rice_production": "360", "rice_yield": "3000"},
            {"year": "2000", "cdk": "PARENT", "harmonization_method": "Raw", "rice_area": "130", "rice_production": "390", "rice_yield": "3000"},
            {"year": "2000", "cdk": "CHILD_A", "harmonization_method": "Raw", "rice_area": "30", "rice_production": "60", "rice_yield": "2000"},
            {"year": "2000", "cdk": "CHILD_B", "harmonization_method": "Raw", "rice_area": "100", "rice_production": "330", "rice_yield": "3300"},
        ],
    )

    service = DisaggregationService(None, packet_path=packet_path, weight_path=weight_path, panel_path=panel_path)
    response = await service.get_event_series("PARENT:2000", "rice", "yield", 1998, 2000)

    child_a = next(series for series in response.child_series if series.child_cdk == "CHILD_A")
    pre_split = {point.year: point for point in child_a.points}[1998]
    split_year = {point.year: point for point in child_a.points}[2000]

    assert response.readiness_status == "ready"
    assert pre_split.method == "derived_from_production_area"
    assert pre_split.value == 3000.0
    assert split_year.method == "Raw"
    assert split_year.value == 2000.0


@pytest.mark.asyncio
async def test_get_event_series_returns_not_ready_for_tier_c(tmp_path):
    packet_path = tmp_path / "packets.jsonl"
    weight_path = tmp_path / "weights.csv"
    panel_path = tmp_path / "panel.csv"

    _write_jsonl(
        packet_path,
        [
            {
                "event_id": "PARENT:2000",
                "split_event_id": None,
                "parent_cdk": "PARENT",
                "parent_name": "Parent",
                "child_cdks": ["CHILD_A"],
                "child_names": ["Child A"],
                "state": "State X",
                "split_year": 2000,
                "effective_date": None,
                "event_type": "SPLIT",
                "source_quality": "secondary_compiled",
                "source_urls": [],
                "source_text_path": None,
                "aliases": ["Parent", "Child A"],
                "geometry_status": "unknown",
                "weight_status": "none",
                "readiness_tier": "Tier C",
                "notes": "test packet",
            }
        ],
    )
    _write_csv(
        weight_path,
        [
            "event_id",
            "child_cdk",
            "child_name",
            "metric_basis",
            "weight_value",
            "weight_method",
            "weight_confidence",
            "source_year",
            "basis",
            "is_fallback",
        ],
        [],
    )
    _write_csv(
        panel_path,
        ["year", "cdk", "harmonization_method", "rice_area", "rice_production", "rice_yield"],
        [{"year": "1999", "cdk": "PARENT", "harmonization_method": "Raw", "rice_area": "100", "rice_production": "300", "rice_yield": "3000"}],
    )

    service = DisaggregationService(None, packet_path=packet_path, weight_path=weight_path, panel_path=panel_path)
    response = await service.get_event_series("PARENT:2000", "rice", "yield", 1999, 1999)

    assert response.readiness_status == "not_ready"
    assert response.child_series == []
