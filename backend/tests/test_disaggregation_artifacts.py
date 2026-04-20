import csv

from app.services.disaggregation_artifacts import (
    assign_readiness_tier,
    build_disaggregation_artifacts,
    collapse_lineage_rows,
    normalize_alias,
)


def _write_csv(path, fieldnames, rows):
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_normalize_alias_and_readiness_assignment():
    assert normalize_alias("North 24-Parganas") == "north 24 parganas"
    assert assign_readiness_tier("official_compiled", "post_split_crop_area_proxy") == "Tier B"
    assert assign_readiness_tier("official", "geometry_overlay_intersection") == "Tier A"
    assert assign_readiness_tier("secondary_compiled", "equal_split_fallback") == "Tier C"


def test_collapse_lineage_rows_flags_duplicates_and_cycles():
    collapsed, qa_rows = collapse_lineage_rows(
        [
            {"parent_cdk": "A", "child_cdk": "B", "event_year": "2000", "event_type": "SPLIT"},
            {"parent_cdk": "A", "child_cdk": "B", "event_year": "2000", "event_type": "SPLIT"},
            {"parent_cdk": "C", "child_cdk": "C", "event_year": "2001", "event_type": "SPLIT"},
        ]
    )

    assert collapsed == [{"parent_cdk": "A", "split_year": 2000, "event_type": "SPLIT", "child_cdks": ["B"]}]
    issue_codes = {row["issue_code"] for row in qa_rows}
    assert "duplicate_row" in issue_codes
    assert "cycle_rejected" in issue_codes


def test_build_disaggregation_artifacts_generates_proxy_weights_that_sum_to_one(tmp_path):
    lineage_path = tmp_path / "lineage.csv"
    master_path = tmp_path / "master.csv"
    panel_path = tmp_path / "panel.csv"
    raw_lineage_path = tmp_path / "raw_lineage.csv"

    _write_csv(
        lineage_path,
        ["parent_cdk", "child_cdk", "event_year", "event_type", "confidence_score", "weight_type"],
        [
            {"parent_cdk": "PARENT", "child_cdk": "CHILD_A", "event_year": "2000", "event_type": "SPLIT", "confidence_score": "1.0", "weight_type": "none"},
            {"parent_cdk": "PARENT", "child_cdk": "CHILD_B", "event_year": "2000", "event_type": "SPLIT", "confidence_score": "1.0", "weight_type": "none"},
        ],
    )
    _write_csv(
        raw_lineage_path,
        ["parent_cdk", "child_cdk", "event_year", "event_type", "confidence_score", "weight_type"],
        [
            {"parent_cdk": "PARENT", "child_cdk": "CHILD_A", "event_year": "2000", "event_type": "SPLIT", "confidence_score": "1.0", "weight_type": "none"},
            {"parent_cdk": "PARENT", "child_cdk": "CHILD_A", "event_year": "2000", "event_type": "SPLIT", "confidence_score": "1.0", "weight_type": "none"},
        ],
    )
    _write_csv(
        master_path,
        ["cdk", "district_name", "state_name"],
        [
            {"cdk": "PARENT", "district_name": "Parent District", "state_name": "State X"},
            {"cdk": "CHILD_A", "district_name": "Child A", "state_name": "State X"},
            {"cdk": "CHILD_B", "district_name": "Child B", "state_name": "State X"},
        ],
    )
    _write_csv(
        panel_path,
        ["year", "cdk", "harmonization_method", "rice_area", "wheat_area"],
        [
            {"year": "2000", "cdk": "CHILD_A", "harmonization_method": "Raw", "rice_area": "20", "wheat_area": "10"},
            {"year": "2001", "cdk": "CHILD_A", "harmonization_method": "Raw", "rice_area": "20", "wheat_area": "10"},
            {"year": "2000", "cdk": "CHILD_B", "harmonization_method": "Raw", "rice_area": "60", "wheat_area": "10"},
            {"year": "2001", "cdk": "CHILD_B", "harmonization_method": "Raw", "rice_area": "60", "wheat_area": "10"},
        ],
    )

    artifacts = build_disaggregation_artifacts(
        lineage_path=lineage_path,
        master_path=master_path,
        panel_path=panel_path,
        raw_lineage_path=raw_lineage_path,
    )

    packet = artifacts["packets"][0]
    assert packet["event_id"] == "PARENT:2000"
    assert packet["weight_status"] == "proxy_ready"
    assert packet["readiness_tier"] == "Tier B"

    area_weights = [row for row in artifacts["weights"] if row["metric_basis"] == "area"]
    assert round(sum(row["weight_value"] for row in area_weights), 6) == 1.0
    assert area_weights[0]["weight_method"] == "post_split_crop_area_proxy"
    assert any(row["issue_code"] == "duplicate_row" for row in artifacts["qa"])
