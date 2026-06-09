import argparse
import asyncio
import csv
import logging
from pathlib import Path

from app.database import get_connection
from app.services.name_resolver import resolve_lgd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
# Assuming script is run from project root
CSV_PATH = Path("data/raw/ICRISAT-District Level Data Unapportioned.csv")
UNMAPPED_REPORT_PATH = Path("data/quarantine/icrisat_unmapped.csv")

# Crop name mapping (CSV header substring -> standard variable name)
CROP_MAP = {
    "RICE": "rice",
    "WHEAT": "wheat",
    "KHARIF SORGHUM": "sorghum_kharif",
    "RABI SORGHUM": "sorghum_rabi",
    "SORGHUM": "sorghum",
    "PEARL MILLET": "pearl_millet",
    "MAIZE": "maize",
    "FINGER MILLET": "finger_millet",
    "BARLEY": "barley",
    "CHICKPEA": "chickpea",
    "PIGEONPEA": "pigeonpea",
    "MINOR PULSES": "minor_pulses",
    "GROUNDNUT": "groundnut",
    "SESAMUM": "sesamum",
    "RAPESEED AND MUSTARD": "rapeseed_mustard",
    "SAFFLOWER": "safflower",
    "CASTOR": "castor",
    "LINSEED": "linseed",
    "SUNFLOWER": "sunflower",
    "SOYABEAN": "soyabean",
    "OILSEEDS": "oilseeds",
    "SUGARCANE": "sugarcane",
    "COTTON": "cotton",
    "FRUITS": "fruits",
    "VEGETABLES": "vegetables",
    "FRUITS AND VEGETABLES": "fruits_vegetables",
    "POTATOES": "potatoes",
    "ONION": "onion",
    "FODDER": "fodder",
}

async def fetch_lgd_lookup() -> dict[tuple[str, str], str]:
    """Fetch all districts from DB and build a lookup table {(district_lower, state_lower): cdk}."""
    lookup = {}
    async with get_connection() as db:
        rows = await db.fetch("SELECT cdk, district_name, state_name FROM districts")
        for row in rows:
            d_name = row["district_name"].lower().strip()
            s_name = row["state_name"].lower().strip()
            lookup[(d_name, s_name)] = row["cdk"]
    return lookup

def parse_value(val: str, is_yield: bool = False) -> float | None:
    """
    Parse float value from string.
    - Handle '-1.0' as None.
    - Convert '1000 ha/tons' to base units (x1000) unless it's yield.
    """
    try:
        f_val = float(val)
        if f_val == -1.0:
            return None
        return f_val * 1000 if not is_yield else f_val
    except ValueError:
        return None

def normalize_header(header: str) -> tuple[str | None, str | None]:
    """
    Parse header like 'RICE AREA (1000 ha)' into (variable_name, type).
    Returns (None, None) if not a metric column.
    """
    header = header.upper()
    if "YEAR" in header or "DIST CODE" in header or "STATE" in header or "DIST NAME" in header:
        return None, None

    metric_type = None
    if "AREA" in header:
        metric_type = "area"
    elif "PRODUCTION" in header:
        metric_type = "production"
    elif "YIELD" in header:
        metric_type = "yield"
    else:
        return None, None

    # Find crop name
    crop_key = None
    for key, val in CROP_MAP.items():
        # strict check to avoid 'SORGHUM' matching 'KHARIF SORGHUM'
        # 'KHARIF SORGHUM' should match 'KHARIF SORGHUM'
        if header.startswith(key + " "):
             crop_key = val
             break

    # If no prefix match, try general containment (careful with overlaps)
    if not crop_key:
        # Sort keys by length desc to match 'KHARIF SORGHUM' before 'SORGHUM'
        sorted_keys = sorted(CROP_MAP.keys(), key=len, reverse=True)
        for key in sorted_keys:
            if key in header:
                crop_key = CROP_MAP[key]
                break

    if crop_key and metric_type:
        return f"{crop_key}_{metric_type}", metric_type

    return None, None

async def import_data(dry_run: bool = False):
    """Main import logic."""
    if not CSV_PATH.exists():
        logger.error(f"File not found: {CSV_PATH}")
        return

    logger.info("Fetching LGD codes from database...")
    lgd_lookup = await fetch_lgd_lookup()
    logger.info(f"Loaded {len(lgd_lookup)} districts from DB.")

    unmapped = set()
    mapped_count = 0
    skipped_count = 0
    metrics_to_insert = []

    with open(CSV_PATH, encoding='utf-8') as f:
        reader = csv.DictReader(f)

        # Pre-process headers
        header_map = {} # CSV Header -> (db_variable, metric_type)
        for h in (reader.fieldnames or []):
             var, mtype = normalize_header(h)
             if var:
                 header_map[h] = (var, mtype)

        logger.info(f"Identified {len(header_map)} metric columns.")

        for _row_idx, row in enumerate(reader):
            # District Mapping
            dist_name = row.get("Dist Name", "").strip()
            state_name = row.get("State Name", "").strip()
            year_str = row.get("Year")
            if not year_str:
                continue
            year = int(year_str)

            cdk = resolve_lgd(dist_name, state_name, lgd_lookup)

            if not cdk:
                unmapped.add((dist_name, state_name))
                skipped_count += 1
                continue

            mapped_count += 1

            # Extract Metrics
            for col, (variable, mtype) in header_map.items():
                raw_val = row.get(col)
                if not raw_val:
                    continue

                # Check for -1.0 validity
                is_yield = (mtype == "yield")
                val = parse_value(raw_val, is_yield)

                if val is not None:
                     metrics_to_insert.append({
                        "cdk": cdk,
                        "year": year,
                        "variable_name": variable,
                        "value": val,
                        "source": "ICRISAT"
                     })

    # Report Unmapped
    if unmapped:
        logger.warning(f"Found {len(unmapped)} unmapped districts.")
        UNMAPPED_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(UNMAPPED_REPORT_PATH, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(["District", "State"])
            writer.writerows(sorted(unmapped))
        logger.info(f"Unmapped districts written to {UNMAPPED_REPORT_PATH}")

    logger.info(f"Summary: Mapped Districts: {mapped_count}, Skipped (Unmapped): {skipped_count}")
    logger.info(f"Total metrics found: {len(metrics_to_insert)}")

    if not dry_run and metrics_to_insert:
        logger.info("Inserting into database...")
        async with get_connection() as db:
            # Batch insert
             batch_size = 5000
             for i in range(0, len(metrics_to_insert), batch_size):
                batch = metrics_to_insert[i:i+batch_size]
                await db.executemany("""
                    INSERT INTO agri_metrics (cdk, year, variable_name, value)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (cdk, year, variable_name)
                    DO UPDATE SET value = EXCLUDED.value
                """, [(m["cdk"], m["year"], m["variable_name"], m["value"]) for m in batch])
                logger.info(f"Inserted batch {i // batch_size + 1}/{(len(metrics_to_insert) - 1) // batch_size + 1}")
        logger.info("Import complete.")
    elif dry_run:
        logger.info("Dry run complete. No data inserted.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import ICRISAT Data")
    parser.add_argument("--dry-run", action="store_true", help="Run without inserting data")
    args = parser.parse_args()

    asyncio.run(import_data(dry_run=args.dry_run))
