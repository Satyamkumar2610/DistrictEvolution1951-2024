"""
Artifact builders and loaders for disaggregation packet datasets.
"""

from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_ARTIFACT_DIR = PROJECT_ROOT / "data" / "processed" / "disaggregation" / "v1"
DEFAULT_PACKET_PATH = DEFAULT_ARTIFACT_DIR / "split_event_packets.jsonl"
DEFAULT_WEIGHT_PATH = DEFAULT_ARTIFACT_DIR / "split_event_weights.csv"
DEFAULT_ALIAS_PATH = DEFAULT_ARTIFACT_DIR / "split_event_aliases.csv"
DEFAULT_QA_PATH = DEFAULT_ARTIFACT_DIR / "split_event_qa.csv"
DEFAULT_LINEAGE_PATH = PROJECT_ROOT / "data" / "v1" / "district_lineage_cleaned.csv"
DEFAULT_RAW_LINEAGE_PATH = PROJECT_ROOT / "data" / "v1" / "district_lineage.csv"
DEFAULT_MASTER_PATH = PROJECT_ROOT / "data" / "v1" / "district_master.csv"
DEFAULT_PANEL_PATH = PROJECT_ROOT / "data" / "v1_5" / "district_year_panel_v1_5.csv"

_AREA_DOUBLE_COUNT_COLUMNS = {"fruits_and_vegetables_area"}
_SEASONAL_FALLBACKS = {
    "rice": ["kharif", "winter", "autumn", "summer"],
    "wheat": ["rabi"],
    "maize": ["kharif"],
    "soyabean": ["kharif"],
    "groundnut": ["kharif"],
    "cotton": ["kharif"],
    "pearl_millet": ["kharif"],
    "sorghum": ["kharif", "rabi"],
    "chickpea": ["rabi"],
}
_OFFICIAL_QUALITY = {"official", "official_compiled", "official_unverified"}


def normalize_alias(name: str) -> str:
    """Normalize a district alias for artifact dedupe and QA."""
    collapsed = re.sub(r"[^a-z0-9]+", " ", name.lower())
    collapsed = re.sub(r"\s+", " ", collapsed).strip()
    return collapsed


def assign_readiness_tier(source_quality: str, weight_method: str | None) -> str:
    """Assign public readiness tier from lineage quality and weights."""
    if source_quality in _OFFICIAL_QUALITY and weight_method in {
        "official_village_subunit_mapping",
        "geometry_overlay_intersection",
    }:
        return "Tier A"
    if source_quality in _OFFICIAL_QUALITY and weight_method:
        return "Tier B"
    return "Tier C"


def collapse_lineage_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Collapse lineage rows into grouped events and capture QA issues."""
    groups: dict[tuple[str, int, str], dict[str, Any]] = {}
    seen_rows: set[tuple[str, str, int, str]] = set()
    qa_rows: list[dict[str, str]] = []

    for row in rows:
        parent = row.get("parent_cdk", "").strip()
        child = row.get("child_cdk", "").strip()
        event_type = row.get("event_type", "SPLIT").strip().upper() or "SPLIT"
        year_raw = row.get("event_year", "").strip()

        if not parent or not child or not year_raw:
            qa_rows.append(
                {
                    "event_id": "",
                    "issue_code": "missing_field",
                    "severity": "high",
                    "message": json.dumps(row, sort_keys=True),
                }
            )
            continue

        try:
            year = int(year_raw)
        except ValueError:
            qa_rows.append(
                {
                    "event_id": f"{parent}:{year_raw}",
                    "issue_code": "invalid_year",
                    "severity": "high",
                    "message": year_raw,
                }
            )
            continue

        row_key = (parent, child, year, event_type)
        if row_key in seen_rows:
            qa_rows.append(
                {
                    "event_id": f"{parent}:{year}",
                    "issue_code": "duplicate_row",
                    "severity": "medium",
                    "message": f"Duplicate lineage row for {child}",
                }
            )
            continue
        seen_rows.add(row_key)

        if parent == child:
            qa_rows.append(
                {
                    "event_id": f"{parent}:{year}",
                    "issue_code": "cycle_rejected",
                    "severity": "high",
                    "message": f"Parent and child are identical ({parent})",
                }
            )
            continue

        key = (parent, year, event_type)
        if key not in groups:
            groups[key] = {
                "parent_cdk": parent,
                "split_year": year,
                "event_type": event_type,
                "child_cdks": [],
            }
        if child not in groups[key]["child_cdks"]:
            groups[key]["child_cdks"].append(child)

    collapsed = sorted(
        groups.values(),
        key=lambda item: (item["split_year"], item["parent_cdk"]),
    )
    return collapsed, qa_rows


def _parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    if math.isnan(number) or number < 0:
        return None
    return number


@lru_cache(maxsize=4)
def load_master_rows(path: str) -> dict[str, dict[str, str]]:
    """Load master district metadata keyed by CDK."""
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            row["cdk"]: {
                "district_name": row.get("district_name", row["cdk"]),
                "state_name": row.get("state_name", ""),
            }
            for row in reader
            if row.get("cdk")
        }


@lru_cache(maxsize=2)
def load_panel_index(path: str) -> dict[str, dict[int, dict[str, Any]]]:
    """Load the harmonized crop panel into a nested index."""
    panel: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            cdk = row.get("cdk", "").strip()
            year_raw = row.get("year", "").strip()
            if not cdk or not year_raw:
                continue
            try:
                year = int(year_raw)
            except ValueError:
                continue

            values: dict[str, Any] = {
                "harmonization_method": row.get("harmonization_method", "Raw") or "Raw",
            }
            for key, raw_value in row.items():
                if key in {"dist_code", "year", "state_code", "state_name", "dist_name", "cdk", "harmonization_method"}:
                    continue
                value = _parse_float(raw_value)
                if value is not None:
                    values[key] = value
            panel[cdk][year] = values
    return panel


def _total_crop_area(row: dict[str, Any]) -> float:
    total = 0.0
    for key, value in row.items():
        if key in _AREA_DOUBLE_COUNT_COLUMNS:
            continue
        if key.endswith("_area") and isinstance(value, (int, float)):
            total += float(value)
    return total


def _build_weight_rows(
    event_id: str,
    child_cdks: list[str],
    split_year: int,
    child_names: list[str],
    panel_index: dict[str, dict[int, dict[str, Any]]],
) -> tuple[list[dict[str, Any]], str, str]:
    proxy_values: dict[str, float] = {}
    for child_cdk in child_cdks:
        child_years = panel_index.get(child_cdk, {})
        area_values = [
            _total_crop_area(child_years[year])
            for year in range(split_year, split_year + 3)
            if year in child_years and _total_crop_area(child_years[year]) > 0
        ]
        if area_values:
            proxy_values[child_cdk] = sum(area_values) / len(area_values)

    rows: list[dict[str, Any]] = []
    if len(proxy_values) == len(child_cdks) and sum(proxy_values.values()) > 0:
        total = sum(proxy_values.values())
        for child_cdk, child_name in zip(child_cdks, child_names, strict=False):
            share = proxy_values[child_cdk] / total
            for metric_basis in ("area", "production"):
                rows.append(
                    {
                        "event_id": event_id,
                        "child_cdk": child_cdk,
                        "child_name": child_name,
                        "metric_basis": metric_basis,
                        "weight_value": round(share, 6),
                        "weight_method": "post_split_crop_area_proxy",
                        "weight_confidence": 0.6,
                        "source_year": split_year,
                        "basis": "average_total_crop_area_next_3_years",
                        "is_fallback": False,
                    }
                )
        return rows, "proxy_ready", "post_split_crop_area_proxy"

    child_count = max(len(child_cdks), 1)
    share = 1.0 / child_count
    for child_cdk, child_name in zip(child_cdks, child_names, strict=False):
        for metric_basis in ("area", "production"):
            rows.append(
                {
                    "event_id": event_id,
                    "child_cdk": child_cdk,
                    "child_name": child_name,
                    "metric_basis": metric_basis,
                    "weight_value": round(share, 6),
                    "weight_method": "equal_split_fallback",
                    "weight_confidence": 0.35,
                    "source_year": split_year,
                    "basis": "equal_split_fallback",
                    "is_fallback": True,
                }
            )
    return rows, "fallback_ready", "equal_split_fallback"


def build_disaggregation_artifacts(
    lineage_path: Path = DEFAULT_LINEAGE_PATH,
    master_path: Path = DEFAULT_MASTER_PATH,
    panel_path: Path = DEFAULT_PANEL_PATH,
    raw_lineage_path: Path = DEFAULT_RAW_LINEAGE_PATH,
) -> dict[str, list[dict[str, Any]]]:
    """Build packet, weight, alias, and QA artifacts from current repo data."""
    with open(lineage_path, newline="") as handle:
        lineage_rows = list(csv.DictReader(handle))
    grouped_events, qa_rows = collapse_lineage_rows(lineage_rows)
    master_rows = load_master_rows(str(master_path))
    panel_index = load_panel_index(str(panel_path))

    if raw_lineage_path.exists():
        with open(raw_lineage_path, newline="") as handle:
            raw_rows = list(csv.DictReader(handle))
        _, raw_qa_rows = collapse_lineage_rows(raw_rows)
        qa_rows.extend(raw_qa_rows)

    packets: list[dict[str, Any]] = []
    weights: list[dict[str, Any]] = []
    aliases: list[dict[str, Any]] = []

    for event in grouped_events:
        parent_cdk = event["parent_cdk"]
        child_cdks = sorted(event["child_cdks"])
        split_year = event["split_year"]
        event_id = f"{parent_cdk}:{split_year}"

        parent_meta = master_rows.get(parent_cdk, {})
        parent_name = parent_meta.get("district_name", parent_cdk)
        state = parent_meta.get("state_name", parent_cdk.split("_")[0])
        child_names = [master_rows.get(child, {}).get("district_name", child) for child in child_cdks]
        weight_rows, weight_status, primary_weight_method = _build_weight_rows(
            event_id,
            child_cdks,
            split_year,
            child_names,
            panel_index,
        )
        readiness_tier = assign_readiness_tier("official_compiled", primary_weight_method)
        packets.append(
            {
                "event_id": event_id,
                "split_event_id": None,
                "parent_cdk": parent_cdk,
                "parent_name": parent_name,
                "child_cdks": child_cdks,
                "child_names": child_names,
                "state": state,
                "split_year": split_year,
                "effective_date": None,
                "event_type": event["event_type"],
                "source_quality": "official_compiled",
                "source_urls": [],
                "source_text_path": None,
                "aliases": [parent_name, *child_names],
                "geometry_status": "unknown",
                "weight_status": weight_status,
                "readiness_tier": readiness_tier,
                "notes": "Built from lineage_cleaned.csv and harmonized district_year_panel_v1_5.csv",
            }
        )
        weights.extend(weight_rows)

        aliases.append(
            {
                "event_id": event_id,
                "role": "parent",
                "cdk": parent_cdk,
                "name": parent_name,
                "normalized_name": normalize_alias(parent_name),
            }
        )
        for child_cdk, child_name in zip(child_cdks, child_names, strict=False):
            aliases.append(
                {
                    "event_id": event_id,
                    "role": "child",
                    "cdk": child_cdk,
                    "name": child_name,
                    "normalized_name": normalize_alias(child_name),
                }
            )

        if primary_weight_method == "equal_split_fallback":
            qa_rows.append(
                {
                    "event_id": event_id,
                    "issue_code": "equal_split_fallback",
                    "severity": "medium",
                    "message": "No post-split crop area proxy was available; equal split weights were used.",
                }
            )

    return {
        "packets": packets,
        "weights": weights,
        "aliases": aliases,
        "qa": qa_rows,
    }


def write_disaggregation_artifacts(artifacts: dict[str, list[dict[str, Any]]], output_dir: Path = DEFAULT_ARTIFACT_DIR) -> None:
    """Write built artifacts to the processed dataset directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "split_event_packets.jsonl", "w", newline="") as handle:
        for packet in artifacts["packets"]:
            handle.write(json.dumps(packet, sort_keys=True) + "\n")

    with open(output_dir / "split_event_weights.csv", "w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
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
        )
        writer.writeheader()
        writer.writerows(artifacts["weights"])

    with open(output_dir / "split_event_aliases.csv", "w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["event_id", "role", "cdk", "name", "normalized_name"],
        )
        writer.writeheader()
        writer.writerows(artifacts["aliases"])

    with open(output_dir / "split_event_qa.csv", "w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["event_id", "issue_code", "severity", "message"],
        )
        writer.writeheader()
        writer.writerows(artifacts["qa"])


@lru_cache(maxsize=4)
def load_packets(path: str) -> dict[str, dict[str, Any]]:
    """Load packet artifacts keyed by event_id."""
    packets: dict[str, dict[str, Any]] = {}
    packet_path = Path(path)
    if not packet_path.exists():
        return packets

    with open(packet_path) as handle:
        for line in handle:
            if not line.strip():
                continue
            packet = json.loads(line)
            packets[packet["event_id"]] = packet
    return packets


@lru_cache(maxsize=4)
def load_weights(path: str) -> dict[str, list[dict[str, Any]]]:
    """Load weight artifacts grouped by event_id."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    weight_path = Path(path)
    if not weight_path.exists():
        return {}

    with open(weight_path, newline="") as handle:
        for row in csv.DictReader(handle):
            grouped[row["event_id"]].append(
                {
                    "event_id": row["event_id"],
                    "child_cdk": row["child_cdk"],
                    "child_name": row.get("child_name"),
                    "metric_basis": row["metric_basis"],
                    "weight_value": float(row["weight_value"]),
                    "weight_method": row["weight_method"],
                    "weight_confidence": float(row["weight_confidence"]),
                    "source_year": int(row["source_year"]) if row.get("source_year") else None,
                    "basis": row["basis"],
                    "is_fallback": str(row.get("is_fallback", "")).lower() == "true",
                }
            )
    return dict(grouped)


def panel_metric_value(
    panel_index: dict[str, dict[int, dict[str, Any]]],
    cdk: str,
    year: int,
    crop: str,
    metric: str,
) -> tuple[float | None, str]:
    """Resolve a metric value from the harmonized panel with seasonal fallback."""
    row = panel_index.get(cdk, {}).get(year)
    if not row:
        return None, "missing"

    direct_key = f"{crop}_{metric}"
    if direct_key in row:
        return float(row[direct_key]), str(row.get("harmonization_method", "Raw"))

    for season in _SEASONAL_FALLBACKS.get(crop, []):
        seasonal_key = f"{crop}_{metric}_{season}"
        if seasonal_key in row:
            return float(row[seasonal_key]), str(row.get("harmonization_method", "Raw"))

    if metric == "yield":
        area_val, method = panel_metric_value(panel_index, cdk, year, crop, "area")
        prod_val, _ = panel_metric_value(panel_index, cdk, year, crop, "production")
        if area_val and prod_val and area_val > 0:
            return round((prod_val / area_val) * 1000.0, 2), method

    return None, str(row.get("harmonization_method", "Raw"))
