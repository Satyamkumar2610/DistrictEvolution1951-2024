"""
Load GeoJSON boundaries into the admin_units table.

Usage:
    python pipeline/load_boundaries.py --source ./raw_data/india_districts.geojson
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from datetime import date

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger("pipeline.load_boundaries")


async def load_boundaries(source_path: str, dsn: str) -> None:
    """Load district boundaries from a GeoJSON file into admin_units."""
    logger.info(f"Loading boundaries from {source_path}...")

    with open(source_path, "r") as f:
        geojson = json.load(f)

    features = geojson.get("features", [])
    if not features:
        logger.error("No features found in GeoJSON file")
        return

    conn = await asyncpg.connect(dsn)
    try:
        inserted = 0
        for feature in features:
            props = feature.get("properties", {})
            geom = feature.get("geometry")

            name = props.get("district", props.get("DISTRICT", props.get("name", "")))
            state = props.get("state", props.get("STATE", props.get("ST_NM", "")))
            valid_from_str = props.get("valid_from", "1950-01-01")
            valid_to_str = props.get("valid_to")

            if not name or not state or not geom:
                continue

            valid_from = date.fromisoformat(valid_from_str)
            valid_to = date.fromisoformat(valid_to_str) if valid_to_str else None

            geom_json = json.dumps(geom)

            await conn.execute(
                """
                INSERT INTO admin_units (name, state, valid_from, valid_to, geometry)
                VALUES ($1, $2, $3, $4, ST_SetSRID(ST_GeomFromGeoJSON($5), 4326))
                """,
                name,
                state,
                valid_from,
                valid_to,
                geom_json,
            )
            inserted += 1

            if inserted % 100 == 0:
                logger.info(f"  ... {inserted} boundaries loaded")

        logger.info(f"Boundary loading complete: {inserted} admin_units inserted")

    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Load district boundaries")
    parser.add_argument("--source", required=True, help="GeoJSON file path")
    parser.add_argument(
        "--dsn",
        default=os.environ.get(
            "DATABASE_URL", "postgresql://user:password@localhost:5432/i_ascap"
        ),
    )
    args = parser.parse_args()
    asyncio.run(load_boundaries(args.source, args.dsn))


if __name__ == "__main__":
    main()
