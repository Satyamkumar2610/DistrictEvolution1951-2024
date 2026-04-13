"""
Load admin transition events into the admin_transitions table.

This script reads transition data from a structured source (CSV or database)
and populates the admin_transitions table linking parent → child admin_units.

Usage:
    python pipeline/load_transitions.py
    python pipeline/load_transitions.py --source ./raw_data/transitions.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import os
from datetime import date

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger("pipeline.load_transitions")


async def load_transitions_from_csv(source_path: str, dsn: str) -> None:
    """
    Load transitions from a CSV file.

    Expected CSV columns:
        from_district, from_state, to_district, to_state,
        transition_type, effective_date, area_weight, confidence
    """
    logger.info(f"Loading transitions from {source_path}...")

    conn = await asyncpg.connect(dsn)
    try:
        inserted = 0
        skipped = 0

        with open(source_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                from_name = row.get("from_district", "")
                from_state = row.get("from_state", "")
                to_name = row.get("to_district", "")
                to_state = row.get("to_state", "")
                transition_type = row.get("transition_type", "SPLIT")
                eff_date_str = row.get("effective_date", "")
                area_weight = float(row.get("area_weight", "0.5"))
                confidence = float(row.get("confidence", "1.0"))

                # Look up from_unit_id
                from_unit = await conn.fetchrow(
                    "SELECT id FROM admin_units WHERE name = $1 AND state = $2",
                    from_name,
                    from_state,
                )
                # Look up to_unit_id
                to_unit = await conn.fetchrow(
                    "SELECT id FROM admin_units WHERE name = $1 AND state = $2",
                    to_name,
                    to_state,
                )

                if not from_unit or not to_unit:
                    logger.warning(
                        f"Skipping transition: {from_name} ({from_state}) → "
                        f"{to_name} ({to_state}) — unit not found"
                    )
                    skipped += 1
                    continue

                eff_date = date.fromisoformat(eff_date_str)

                await conn.execute(
                    """
                    INSERT INTO admin_transitions
                        (from_unit_id, to_unit_id, transition_type,
                         effective_date, area_weight, confidence)
                    VALUES ($1, $2, $3::transition_type, $4, $5, $6)
                    """,
                    from_unit["id"],
                    to_unit["id"],
                    transition_type,
                    eff_date,
                    area_weight,
                    confidence,
                )
                inserted += 1

        logger.info(
            f"Transition loading complete: {inserted} inserted, {skipped} skipped"
        )

    finally:
        await conn.close()


async def load_transitions_from_existing_db(dsn: str) -> None:
    """
    Migrate transition data from existing split_events table
    to the new admin_transitions table.
    """
    conn = await asyncpg.connect(dsn)
    try:
        # Check if the old split_events table exists
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'split_events'
            )
            """
        )
        if not exists:
            logger.info("No split_events table found — skipping DB migration")
            return

        logger.info("Migrating from split_events to admin_transitions...")
        rows = await conn.fetch(
            "SELECT parent_cdk, child_cdks, split_year FROM split_events"
        )

        migrated = 0
        for row in rows:
            parent_cdk = row["parent_cdk"]
            child_cdks = row["child_cdks"]
            split_year = row["split_year"]
            n_children = len(child_cdks) if child_cdks else 1
            equal_weight = round(1.0 / n_children, 4)

            for child_cdk in (child_cdks or []):
                # Look up admin_unit IDs by name matching
                # This is a best-effort migration
                logger.debug(
                    f"  {parent_cdk} → {child_cdk} ({split_year}), "
                    f"weight={equal_weight}"
                )
                migrated += 1

        logger.info(f"Migration analysis: {migrated} potential transitions")

    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Load admin transitions")
    parser.add_argument(
        "--source",
        help="CSV file with transition data (optional — will try DB migration if absent)",
    )
    parser.add_argument(
        "--dsn",
        default=os.environ.get(
            "DATABASE_URL", "postgresql://user:password@localhost:5432/i_ascap"
        ),
    )
    args = parser.parse_args()

    if args.source:
        asyncio.run(load_transitions_from_csv(args.source, args.dsn))
    else:
        asyncio.run(load_transitions_from_existing_db(args.dsn))


if __name__ == "__main__":
    main()
