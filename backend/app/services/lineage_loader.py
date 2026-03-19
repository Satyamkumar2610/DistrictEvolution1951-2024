"""
Lineage Loader — Batch import district lineage from CSV files into split_events.

Reads:
  - district_lineage_cleaned.csv  (parent_cdk, child_cdk, event_year, event_type)
  - district_changes.csv          (source_district, dest_district, source_year, dest_year, state)

Groups children by parent + year and inserts into split_events table.
"""

import csv
import logging
from pathlib import Path
from collections import defaultdict
from typing import Optional

import asyncpg

logger = logging.getLogger("app.services.lineage_loader")

# Data file paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
LINEAGE_CSV = PROJECT_ROOT / "data/v1/district_lineage_cleaned.csv"
CHANGES_CSV = PROJECT_ROOT / "data/processed/district_changes.csv"


async def load_lineage_csv(
    db: asyncpg.Connection,
    csv_path: Optional[Path] = None,
    dry_run: bool = False,
) -> dict:
    """
    Load district_lineage_cleaned.csv into split_events.

    CSV columns: parent_cdk, child_cdk, event_year, event_type, confidence_score, weight_type

    Returns a summary dict.
    """
    path = csv_path or LINEAGE_CSV
    if not path.exists():
        return {"error": f"File not found: {path}", "loaded": 0}

    # Group children by (parent_cdk, event_year)
    events: dict[tuple[str, int], list[str]] = defaultdict(list)
    total_rows = 0

    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            parent = row.get("parent_cdk", "").strip()
            child = row.get("child_cdk", "").strip()
            year_str = row.get("event_year", "").strip()
            event_type = row.get("event_type", "SPLIT").strip()

            if not parent or not child or not year_str:
                continue

            try:
                year = int(year_str)
            except ValueError:
                continue

            if event_type.upper() in ("SPLIT", "BIFURCATION"):
                events[(parent, year)].append(child)
                total_rows += 1

    # Deduplicate children per event
    for key in events:
        events[key] = list(dict.fromkeys(events[key]))

    if dry_run:
        return {
            "dry_run": True,
            "total_csv_rows": total_rows,
            "unique_events": len(events),
            "sample_events": [
                {"parent": k[0], "year": k[1], "children": v}
                for k, v in list(events.items())[:5]
            ],
        }

    # Insert into split_events
    inserted = 0
    skipped = 0

    for (parent_cdk, year), child_cdks in events.items():
        try:
            await db.execute("""
                INSERT INTO split_events
                    (parent_cdk, child_cdks, split_year, event_type,
                     geometry_status, source_notes)
                VALUES ($1, $2, $3, 'split', 'unknown',
                        'Batch import from district_lineage_cleaned.csv')
                ON CONFLICT (parent_cdk, split_year) DO UPDATE SET
                    child_cdks = EXCLUDED.child_cdks,
                    source_notes = EXCLUDED.source_notes
            """, parent_cdk, child_cdks, year)
            inserted += 1
        except Exception as e:
            logger.warning(f"Skip {parent_cdk}/{year}: {e}")
            skipped += 1

    logger.info(f"Lineage CSV loaded: {inserted} events inserted, {skipped} skipped")

    return {
        "source": str(path),
        "total_csv_rows": total_rows,
        "unique_events": len(events),
        "inserted": inserted,
        "skipped": skipped,
    }


async def load_changes_csv(
    db: asyncpg.Connection,
    csv_path: Optional[Path] = None,
    dry_run: bool = False,
) -> dict:
    """
    Load district_changes.csv into split_events.

    CSV columns: source_district, dest_district, source_year, dest_year,
                 filter_state, confidence_score, census_code_2011,
                 split_type, notification_date

    Since this CSV uses district NAMES (not CDKs), we try to resolve CDKs
    from the districts table first.

    Returns a summary dict.
    """
    path = csv_path or CHANGES_CSV
    if not path.exists():
        return {"error": f"File not found: {path}", "loaded": 0}

    # Group by (source_district, dest_year, state)
    events: dict[tuple[str, int, str], list[str]] = defaultdict(list)
    total_rows = 0

    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            source = row.get("source_district", "").strip()
            dest = row.get("dest_district", "").strip()
            dest_year_str = row.get("dest_year", "").strip()
            state = row.get("filter_state", "").strip()

            if not source or not dest or not dest_year_str:
                continue

            try:
                dest_year = int(dest_year_str)
            except ValueError:
                continue

            events[(source, dest_year, state)].append(dest)
            total_rows += 1

    # Deduplicate children
    for key in events:
        events[key] = list(dict.fromkeys(events[key]))

    if dry_run:
        return {
            "dry_run": True,
            "total_csv_rows": total_rows,
            "unique_events": len(events),
            "sample_events": [
                {"parent": k[0], "year": k[1], "state": k[2], "children": v}
                for k, v in list(events.items())[:5]
            ],
        }

    # For each event, try to resolve CDKs
    inserted = 0
    skipped = 0
    unresolved = 0

    for (source_name, year, state), dest_names in events.items():
        # Try to find parent CDK
        parent_cdk = await db.fetchval("""
            SELECT cdk FROM districts
            WHERE district_name ILIKE $1
            ORDER BY start_year DESC LIMIT 1
        """, source_name)

        if not parent_cdk:
            # Try fuzzy match
            parent_cdk = await db.fetchval("""
                SELECT cdk FROM districts
                WHERE district_name ILIKE $1
                ORDER BY start_year DESC LIMIT 1
            """, f"%{source_name}%")

        if not parent_cdk:
            unresolved += 1
            continue

        # Resolve child CDKs
        child_cdks = []
        for dest_name in dest_names:
            child_cdk = await db.fetchval("""
                SELECT cdk FROM districts
                WHERE district_name ILIKE $1
                ORDER BY start_year DESC LIMIT 1
            """, dest_name)

            if not child_cdk:
                child_cdk = await db.fetchval("""
                    SELECT cdk FROM districts
                    WHERE district_name ILIKE $1
                    ORDER BY start_year DESC LIMIT 1
                """, f"%{dest_name}%")

            if child_cdk:
                child_cdks.append(child_cdk)

        if not child_cdks:
            unresolved += 1
            continue

        try:
            await db.execute("""
                INSERT INTO split_events
                    (parent_cdk, child_cdks, split_year, event_type,
                     geometry_status, source_notes)
                VALUES ($1, $2, $3, 'split', 'unknown',
                        $4)
                ON CONFLICT (parent_cdk, split_year) DO NOTHING
            """, parent_cdk, child_cdks, year,
                f"Batch import from district_changes.csv (state={state})")
            inserted += 1
        except Exception as e:
            logger.warning(f"Skip {parent_cdk}/{year}: {e}")
            skipped += 1

    logger.info(
        f"Changes CSV loaded: {inserted} inserted, {skipped} skipped, "
        f"{unresolved} unresolved"
    )

    return {
        "source": str(path),
        "total_csv_rows": total_rows,
        "unique_events": len(events),
        "inserted": inserted,
        "skipped": skipped,
        "unresolved_parents": unresolved,
    }
