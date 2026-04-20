"""
Load generated disaggregation artifacts into database tables.
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
from pathlib import Path
import sys

import asyncpg

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT / "backend"))

from app.services.disaggregation_artifacts import (
    DEFAULT_PACKET_PATH,
    DEFAULT_WEIGHT_PATH,
)


async def load_packets(conn: asyncpg.Connection, packet_path: Path) -> int:
    inserted = 0
    with open(packet_path) as handle:
        for line in handle:
            if not line.strip():
                continue
            packet = json.loads(line)
            await conn.execute(
                """
                INSERT INTO split_event_packets (
                    event_id, split_event_id, parent_cdk, parent_name, child_cdks, child_names,
                    state, split_year, effective_date, event_type, source_quality, source_urls,
                    source_text_path, aliases, geometry_status, weight_status, readiness_tier, notes
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9::date, $10, $11, $12,
                    $13, $14::jsonb, $15, $16, $17, $18
                )
                ON CONFLICT (event_id) DO UPDATE SET
                    split_event_id = EXCLUDED.split_event_id,
                    parent_name = EXCLUDED.parent_name,
                    child_cdks = EXCLUDED.child_cdks,
                    child_names = EXCLUDED.child_names,
                    state = EXCLUDED.state,
                    split_year = EXCLUDED.split_year,
                    effective_date = EXCLUDED.effective_date,
                    event_type = EXCLUDED.event_type,
                    source_quality = EXCLUDED.source_quality,
                    source_urls = EXCLUDED.source_urls,
                    source_text_path = EXCLUDED.source_text_path,
                    aliases = EXCLUDED.aliases,
                    geometry_status = EXCLUDED.geometry_status,
                    weight_status = EXCLUDED.weight_status,
                    readiness_tier = EXCLUDED.readiness_tier,
                    notes = EXCLUDED.notes,
                    updated_at = NOW()
                """,
                packet["event_id"],
                packet.get("split_event_id"),
                packet["parent_cdk"],
                packet.get("parent_name"),
                packet.get("child_cdks", []),
                packet.get("child_names", []),
                packet["state"],
                packet["split_year"],
                packet.get("effective_date"),
                packet.get("event_type", "SPLIT"),
                packet.get("source_quality", "unknown"),
                packet.get("source_urls", []),
                packet.get("source_text_path"),
                json.dumps(packet.get("aliases", [])),
                packet.get("geometry_status", "unknown"),
                packet.get("weight_status", "none"),
                packet.get("readiness_tier", "Tier C"),
                packet.get("notes"),
            )
            inserted += 1
    return inserted


async def load_weights(conn: asyncpg.Connection, weight_path: Path) -> int:
    inserted = 0
    with open(weight_path, newline="") as handle:
        for row in csv.DictReader(handle):
            await conn.execute(
                """
                INSERT INTO split_event_weights (
                    event_id, child_cdk, child_name, metric_basis, weight_value,
                    weight_method, weight_confidence, source_year, basis, is_fallback
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (event_id, child_cdk, metric_basis) DO UPDATE SET
                    child_name = EXCLUDED.child_name,
                    weight_value = EXCLUDED.weight_value,
                    weight_method = EXCLUDED.weight_method,
                    weight_confidence = EXCLUDED.weight_confidence,
                    source_year = EXCLUDED.source_year,
                    basis = EXCLUDED.basis,
                    is_fallback = EXCLUDED.is_fallback
                """,
                row["event_id"],
                row["child_cdk"],
                row.get("child_name"),
                row["metric_basis"],
                float(row["weight_value"]),
                row["weight_method"],
                float(row["weight_confidence"]),
                int(row["source_year"]) if row.get("source_year") else None,
                row["basis"],
                str(row.get("is_fallback", "")).lower() == "true",
            )
            inserted += 1
    return inserted


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is required")

    conn = await asyncpg.connect(db_url)
    try:
        packets = await load_packets(conn, DEFAULT_PACKET_PATH)
        weights = await load_weights(conn, DEFAULT_WEIGHT_PATH)
        print(f"Loaded {packets} packets and {weights} weights into database tables.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
