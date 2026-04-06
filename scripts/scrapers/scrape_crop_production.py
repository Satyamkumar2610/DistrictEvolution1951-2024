#!/usr/bin/env python3
"""
Scraper 1: District-wise Crop Production Statistics (data.gov.in)

Fetches 246,091 records of district-wise, season-wise crop production
data from the Ministry of Agriculture API (1997-2020+).

Data fields: state_name, district_name, crop_year, season, crop, area, production
Source: https://data.gov.in/resource/35be999b-0208-4354-b557-f6ca9a5355de

Usage:
    # Dry run — fetch and save CSV only
    python scrape_crop_production.py

    # Full run — fetch, save CSV, and upsert into database
    python scrape_crop_production.py --load-db
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx

# ── Setup ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "scraped"

sys.path.append(str(PROJECT_ROOT / "backend"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("scraper.crop_production")

# ── API Configuration ──────────────────────────────────────────────────
API_RESOURCE = "35be999b-0208-4354-b557-f6ca9a5355de"
API_BASE = f"https://api.data.gov.in/resource/{API_RESOURCE}"
API_KEY = "579b464db66ec23bdd0000011d0179460bed4f26443f90cf4bee20d0"
PAGE_SIZE = 500  # max records per page (API limit)
MAX_RETRIES = 3

# Crop name normalization: API name → internal variable prefix
CROP_NORMALIZE: dict[str, str] = {
    "Rice": "rice",
    "Wheat": "wheat",
    "Jowar": "sorghum",
    "Bajra": "pearl_millet",
    "Maize": "maize",
    "Ragi": "finger_millet",
    "Barley": "barley",
    "Gram": "chickpea",
    "Arhar/Tur": "pigeonpea",
    "Groundnut": "groundnut",
    "Sesamum": "sesamum",
    "Rapeseed &Mustard": "rapeseed_and_mustard",
    "Rapeseed & Mustard": "rapeseed_and_mustard",
    "Safflower": "safflower",
    "Castor seed": "castor",
    "Linseed": "linseed",
    "Sunflower": "sunflower",
    "Soyabean": "soyabean",
    "Cotton(lint)": "cotton",
    "Cotton (lint)": "cotton",
    "Sugarcane": "sugarcane",
    "Potato": "potatoes",
    "Onion": "onion",
    "Tobacco": "tobacco",
    "Jute": "jute",
    "Mesta": "mesta",
    "Banana": "banana",
    "Coconut ": "coconut",
    "Coconut": "coconut",
    "Black pepper": "black_pepper",
    "Dry chillies": "chillies",
    "Turmeric": "turmeric",
    "Ginger": "ginger",
    "Garlic": "garlic",
    "Tapioca": "tapioca",
    "Coriander": "coriander",
    "Sweet potato": "sweet_potato",
    "Arecanut": "arecanut",
    "Cashewnut": "cashewnut",
    "Moong(Green Gram)": "moong",
    "Urad": "urad",
    "Masoor": "masoor",
    "Peas & beans (Pulses)": "peas_beans",
    "other oilseeds": "other_oilseeds",
    "Other  Rabi pulses": "other_rabi_pulses",
    "Other Kharif pulses": "other_kharif_pulses",
    "Small millets": "small_millets",
    "Horse-gram": "horse_gram",
    "Niger seed": "niger_seed",
    "Cardamom": "cardamom",
    "Total foodgrain": "total_foodgrains",
    "Other Cereals & Millets": "other_cereals_millets",
    "Khesari": "khesari",
    "Moth": "moth",
    "Lemon": "lemon",
    "Dry Ginger": "dry_ginger",
}

SEASON_SUFFIX: dict[str, str] = {
    "Kharif": "_kharif",
    "Rabi": "_rabi",
    "Summer": "_summer",
    "Whole Year": "",
    "Autumn": "_autumn",
    "Winter": "_winter",
}


# ── Fetch Logic ────────────────────────────────────────────────────────


async def fetch_page(
    client: httpx.AsyncClient, offset: int
) -> tuple[list[dict], int]:
    """Fetch a single page of records from the API. Returns (records, total)."""
    params = {
        "api-key": API_KEY,
        "format": "json",
        "limit": PAGE_SIZE,
        "offset": offset,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = await client.get(API_BASE, params=params, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            records = data.get("records", [])
            total = int(data.get("total", 0))
            return records, total
        except (httpx.HTTPError, httpx.TimeoutException, json.JSONDecodeError) as e:
            logger.warning(f"  Attempt {attempt}/{MAX_RETRIES} failed (offset={offset}): {e}")
            if attempt == MAX_RETRIES:
                logger.error(f"  Giving up on offset {offset}")
                return [], 0
            await asyncio.sleep(2 ** attempt)

    return [], 0


async def fetch_all_records() -> list[dict]:
    """Paginate through the entire API and collect all records."""
    all_records: list[dict] = []
    offset = 0
    total = 1  # will be updated on first fetch

    async with httpx.AsyncClient() as client:
        # First fetch to discover total
        records, total = await fetch_page(client, 0)
        all_records.extend(records)
        offset = PAGE_SIZE
        logger.info(f"API reports {total:,} total records. Fetching in pages of {PAGE_SIZE}...")

        while offset < total:
            records, _ = await fetch_page(client, offset)
            all_records.extend(records)

            if len(all_records) % 5000 < PAGE_SIZE:
                logger.info(f"  Fetched {len(all_records):,} / {total:,} records...")

            offset += PAGE_SIZE

            # Polite delay to avoid throttling
            await asyncio.sleep(0.2)

    logger.info(f"✅ Fetched {len(all_records):,} total records from API")
    return all_records


# ── Save Logic ─────────────────────────────────────────────────────────


def save_raw_json(records: list[dict], path: Path) -> None:
    """Save raw API response records as JSON."""
    with open(path, "w") as f:
        json.dump(records, f, indent=2)
    logger.info(f"📄 Saved raw JSON: {path} ({len(records):,} records)")


def normalize_crop(crop_name: str) -> str:
    """Normalize a crop name from the API to an internal variable prefix."""
    stripped = crop_name.strip()
    if stripped in CROP_NORMALIZE:
        return CROP_NORMALIZE[stripped]
    # Fallback: lowercase, replace spaces/special chars
    return stripped.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("&", "and")


def transform_to_metrics(records: list[dict]) -> list[dict]:
    """
    Transform raw API records into agri_metrics format.

    Each API record has: state_name, district_name, crop_year, season, crop, area_, production_
    We transform this into multiple rows:
      - {crop}_area{season_suffix} = area_
      - {crop}_production{season_suffix} = production_
      - {crop}_yield{season_suffix} = (production / area) * 1000  [kg/ha]
    """
    metrics: list[dict] = []

    for rec in records:
        state = str(rec.get("state_name", "")).strip()
        district = str(rec.get("district_name", "")).strip()
        crop_year = rec.get("crop_year")
        season = str(rec.get("season", "")).strip()
        crop_raw = str(rec.get("crop", "")).strip()
        area = rec.get("area_")
        production = rec.get("production_")

        if not state or not district or not crop_year or not crop_raw:
            continue

        try:
            year = int(float(crop_year))
        except (ValueError, TypeError):
            continue

        crop = normalize_crop(crop_raw)
        suffix = SEASON_SUFFIX.get(season, "")

        # Area
        if area is not None and area != "" and area != "0":
            try:
                area_val = float(area)
                if area_val >= 0:
                    metrics.append({
                        "state_name": state,
                        "district_name": district,
                        "year": year,
                        "variable_name": f"{crop}_area{suffix}",
                        "value": area_val,
                        "source": "GOV_API",
                    })
            except (ValueError, TypeError):
                pass

        # Production
        if production is not None and production != "" and production != "0":
            try:
                prod_val = float(production)
                if prod_val >= 0:
                    metrics.append({
                        "state_name": state,
                        "district_name": district,
                        "year": year,
                        "variable_name": f"{crop}_production{suffix}",
                        "value": prod_val,
                        "source": "GOV_API",
                    })
            except (ValueError, TypeError):
                pass

        # Yield (computed)
        if area is not None and production is not None:
            try:
                a = float(area)
                p = float(production)
                if a > 0 and p >= 0:
                    yield_val = (p / a) * 1000  # kg/ha
                    metrics.append({
                        "state_name": state,
                        "district_name": district,
                        "year": year,
                        "variable_name": f"{crop}_yield{suffix}",
                        "value": round(yield_val, 2),
                        "source": "GOV_API",
                    })
            except (ValueError, TypeError, ZeroDivisionError):
                pass

    logger.info(f"🔄 Transformed into {len(metrics):,} metric rows")
    return metrics


def save_metrics_csv(metrics: list[dict], path: Path) -> None:
    """Save transformed metrics as CSV."""
    if not metrics:
        logger.warning("No metrics to save")
        return

    fieldnames = ["state_name", "district_name", "year", "variable_name", "value", "source"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(metrics)

    logger.info(f"📄 Saved metrics CSV: {path} ({len(metrics):,} rows)")


# ── Database Load ──────────────────────────────────────────────────────


async def load_to_database(metrics: list[dict]) -> None:
    """Upsert metric rows into the agri_metrics table."""
    import asyncpg
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / "backend" / ".env")
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set — skipping database load")
        return

    # Import name resolver
    from app.services.name_resolver import resolve_lgd

    conn = await asyncpg.connect(db_url, ssl="require")

    try:
        # Build LGD lookup from districts table
        rows = await conn.fetch("SELECT lgd_code, district_name, state_name FROM districts")
        lgd_lookup: dict[tuple, int] = {}
        for row in rows:
            d = row["district_name"].lower().strip()
            s = row["state_name"].lower().strip()
            lgd_lookup[(d, s)] = row["lgd_code"]

        logger.info(f"Loaded {len(lgd_lookup)} districts from database for name resolution")

        # Ensure source column exists
        await conn.execute(
            "ALTER TABLE agri_metrics ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'ICRISAT'"
        )

        # Prepare batch insert
        inserted = 0
        skipped = 0
        batch_size = 1000
        batch: list[tuple] = []

        for m in metrics:
            lgd_code = resolve_lgd(m["district_name"], m["state_name"], lgd_lookup)
            if not lgd_code:
                skipped += 1
                continue

            batch.append((lgd_code, m["year"], m["variable_name"], m["value"], m["source"]))

            if len(batch) >= batch_size:
                await _insert_batch(conn, batch)
                inserted += len(batch)
                batch = []

                if inserted % 10000 < batch_size:
                    logger.info(f"  Inserted {inserted:,} rows...")

        # Final batch
        if batch:
            await _insert_batch(conn, batch)
            inserted += len(batch)

        logger.info(f"✅ Database load complete: {inserted:,} inserted, {skipped:,} skipped (unresolved)")

        # Verify
        count = await conn.fetchval("SELECT COUNT(*) FROM agri_metrics WHERE source = 'GOV_API'")
        logger.info(f"   Total GOV_API rows in database: {count:,}")

    finally:
        await conn.close()


async def _insert_batch(conn, batch: list[tuple]) -> None:
    """Insert a batch of rows using ON CONFLICT DO NOTHING (preserve existing data)."""
    await conn.executemany(
        """
        INSERT INTO agri_metrics (district_lgd, year, variable_name, value, source)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (district_lgd, year, variable_name) DO NOTHING
        """,
        batch,
    )


# ── Main ───────────────────────────────────────────────────────────────


async def main(load_db: bool = False) -> None:
    """Main ETL pipeline."""
    logger.info("=" * 65)
    logger.info("SCRAPER 1: District-wise Crop Production Statistics (data.gov.in)")
    logger.info("=" * 65)

    # Ensure output directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Fetch all records from the API
    logger.info("\n[1/4] Fetching records from data.gov.in API...")
    records = await fetch_all_records()

    if not records:
        logger.error("No records fetched. Exiting.")
        return

    # Step 2: Save raw JSON
    logger.info("\n[2/4] Saving raw JSON...")
    timestamp = datetime.now().strftime("%Y%m%d")
    save_raw_json(records, DATA_DIR / f"crop_production_raw_{timestamp}.json")

    # Step 3: Transform to metrics format
    logger.info("\n[3/4] Transforming to metrics format...")
    metrics = transform_to_metrics(records)
    save_metrics_csv(metrics, DATA_DIR / "crop_production_gov.csv")

    # Print summary stats
    states = set(m["state_name"] for m in metrics)
    years = set(m["year"] for m in metrics)
    crops = set(m["variable_name"].rsplit("_", 1)[0] for m in metrics)
    logger.info(f"\n📊 Summary:")
    logger.info(f"   Raw records:   {len(records):,}")
    logger.info(f"   Metric rows:   {len(metrics):,}")
    logger.info(f"   States:        {len(states)}")
    logger.info(f"   Year range:    {min(years)} – {max(years)}")
    logger.info(f"   Crop variables: {len(crops)}")

    # Step 4: Database load (optional)
    if load_db:
        logger.info("\n[4/4] Loading into database...")
        await load_to_database(metrics)
    else:
        logger.info("\n[4/4] Skipping database load (use --load-db to enable)")

    logger.info("\n" + "=" * 65)
    logger.info("✅ SCRAPER 1 COMPLETE!")
    logger.info("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape crop production data from data.gov.in")
    parser.add_argument("--load-db", action="store_true", help="Load data into PostgreSQL database")
    args = parser.parse_args()

    asyncio.run(main(load_db=args.load_db))
