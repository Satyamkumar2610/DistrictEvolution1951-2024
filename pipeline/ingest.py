"""
Metric ingestion pipeline for I-ASCAP.

Reads raw CSV data (ICRISAT format), harmonizes values through the AdminGraph,
and writes to the district_metrics table with full provenance tracking.

Usage:
    python pipeline/ingest.py --source ./raw_data/icrisat_district_data.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import os
import sys

import asyncpg

from pipeline.lib.admin_graph import build_graph, AdminGraph
from pipeline.lib.harmonizer import harmonize_value, HarmonizedResult

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger("pipeline.ingest")


async def ingest_metrics(source_path: str, dsn: str) -> None:
    """
    Main ingestion entrypoint.

    1. Build the AdminGraph from the database
    2. Read CSV rows
    3. For each row, look up the admin_unit, harmonize if needed
    4. Upsert into district_metrics with provenance
    """
    logger.info("Building AdminGraph from database...")
    graph = await build_graph(dsn)
    logger.info(
        f"Graph loaded: {len(graph.units)} units, {len(graph.transitions)} transitions"
    )

    conn = await asyncpg.connect(dsn)
    try:
        # Build name → unit mapping for CSV lookups
        unit_by_name: dict[str, str] = {}
        for uid, unit in graph.units.items():
            key = f"{unit.name.lower()}|{unit.state.lower()}"
            unit_by_name[key] = uid

        logger.info(f"Reading metrics from {source_path}...")

        inserted = 0
        skipped = 0

        with open(source_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                district_name = row.get("district", row.get("district_name", ""))
                state_name = row.get("state", row.get("state_name", ""))
                year_str = row.get("year", "")
                metric_name = row.get("metric", row.get("variable_name", ""))
                value_str = row.get("value", "")

                if not all([district_name, state_name, year_str, metric_name, value_str]):
                    skipped += 1
                    continue

                try:
                    year = int(year_str)
                    value = float(value_str)
                except (ValueError, TypeError):
                    skipped += 1
                    continue

                # Look up the admin unit
                lookup_key = f"{district_name.lower()}|{state_name.lower()}"
                unit_id = unit_by_name.get(lookup_key)

                if not unit_id:
                    skipped += 1
                    continue

                # Check if harmonization is needed
                unit = graph.units[unit_id]
                raw_unit_id = unit_id  # For direct measurements

                try:
                    harmonized = harmonize_value(
                        graph,
                        unit_id=unit_id,
                        target_year=year,
                        raw_unit_id=raw_unit_id,
                        raw_year=year,
                        raw_value=value,
                    )
                except ValueError:
                    # No apportionment chain — store as direct measurement
                    harmonized = HarmonizedResult(
                        value=value,
                        is_harmonized=False,
                        provenance_path=[],
                        cumulative_confidence=1.0,
                        parent_district_name=None,
                    )

                # Upsert into district_metrics
                await conn.execute(
                    """
                    INSERT INTO district_metrics
                        (unit_id, year, metric, value, is_harmonized,
                         provenance_path, cumulative_confidence)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (unit_id, metric, year) DO UPDATE
                        SET value = EXCLUDED.value,
                            is_harmonized = EXCLUDED.is_harmonized,
                            provenance_path = EXCLUDED.provenance_path,
                            cumulative_confidence = EXCLUDED.cumulative_confidence
                    """,
                    unit_id,
                    year,
                    metric_name,
                    harmonized.value,
                    harmonized.is_harmonized,
                    harmonized.provenance_path,
                    harmonized.cumulative_confidence,
                )
                inserted += 1

                if inserted % 1000 == 0:
                    logger.info(f"  ... {inserted} rows inserted")

        logger.info(f"Ingestion complete: {inserted} inserted, {skipped} skipped")

    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest metrics into I-ASCAP")
    parser.add_argument(
        "--source",
        required=True,
        help="Path to the source CSV file",
    )
    parser.add_argument(
        "--dsn",
        default=os.environ.get(
            "DATABASE_URL", "postgresql://user:password@localhost:5432/i_ascap"
        ),
        help="Database connection string",
    )
    args = parser.parse_args()

    asyncio.run(ingest_metrics(args.source, args.dsn))


if __name__ == "__main__":
    main()
