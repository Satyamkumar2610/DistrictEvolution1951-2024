#!/usr/bin/env python3
"""
Scraper 2: Daily Mandi Market Prices (data.gov.in)

Fetches current daily commodity prices from mandis across India.
Updated every day by the Ministry of Agriculture.

Data fields: state, district, market, commodity, variety, grade,
             arrival_date, min_price, max_price, modal_price

Source: https://data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070

Usage:
    # Dry run — fetch and save CSV only
    python scrape_mandi_prices.py

    # Full run — fetch, save CSV, and insert into database
    python scrape_mandi_prices.py --load-db
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
logger = logging.getLogger("scraper.mandi_prices")

# ── API Configuration ──────────────────────────────────────────────────
API_RESOURCE = "9ef84268-d588-465a-a308-a864a43d0070"
API_BASE = f"https://api.data.gov.in/resource/{API_RESOURCE}"
API_KEY = "579b464db66ec23bdd0000011d0179460bed4f26443f90cf4bee20d0"
PAGE_SIZE = 500
MAX_RETRIES = 3

# Commodity normalization for matching with I-ASCAP crop names
COMMODITY_NORMALIZE: dict[str, str] = {
    "Paddy(Dhan)(Common)": "rice",
    "Paddy(Dhan)(Basmati)": "rice_basmati",
    "Wheat": "wheat",
    "Jowar(Sorghum)": "sorghum",
    "Bajra(Pearl Millet)": "pearl_millet",
    "Maize": "maize",
    "Ragi (Finger Millet)": "finger_millet",
    "Barley (Jau)": "barley",
    "Bengal Gram(Gram)(Whole)": "chickpea",
    "Arhar (Tur/Red Gram)(Whole)": "pigeonpea",
    "Arhar Dal(Tur Dal)": "pigeonpea_dal",
    "Groundnut": "groundnut",
    "Groundnut pods (raw)": "groundnut",
    "Sesamum(Sesame,Gingelly,Til)": "sesamum",
    "Mustard": "rapeseed_and_mustard",
    "Rapeseed": "rapeseed_and_mustard",
    "Safflower": "safflower",
    "Castor Seed": "castor",
    "Linseed": "linseed",
    "Sunflower": "sunflower",
    "Soyabean": "soyabean",
    "Cotton": "cotton",
    "Sugarcane": "sugarcane",
    "Potato": "potatoes",
    "Onion": "onion",
    "Tobacco": "tobacco",
    "Jute": "jute",
    "Banana": "banana",
    "Coconut": "coconut",
    "Black pepper": "black_pepper",
    "Dry Chillies": "chillies",
    "Turmeric": "turmeric",
    "Ginger(Dry)": "ginger",
    "Garlic": "garlic",
    "Tapioca": "tapioca",
    "Coriander(Leaves)": "coriander",
    "Sweet Potato": "sweet_potato",
    "Arecanut(Betel Nut/Supari)": "arecanut",
    "Cashew Kernel Broken": "cashewnut",
    "Moong Dal (Whole)": "moong",
    "Moong(Green Gram)(Whole)": "moong",
    "Urad (Whole)": "urad",
    "Masoor Dal": "masoor",
    "Lentil (Masur)(Whole)": "masoor",
    "Horse Gram": "horse_gram",
    "Niger Seed (Ramtill)": "niger_seed",
    "Cardamom": "cardamom",
    "Tomato": "tomato",
    "Cauliflower": "cauliflower",
    "Cabbage": "cabbage",
    "Brinjal": "brinjal",
    "Green Chilli": "green_chilli",
    "Lemon": "lemon",
    "Pumpkin": "pumpkin",
    "Apple": "apple",
    "Mango": "mango",
    "Papaya": "papaya",
    "Grapes": "grapes",
    "Orange": "orange",
    "Water Melon": "watermelon",
    "Gur(Jaggery)": "jaggery",
}


# ── Fetch Logic ────────────────────────────────────────────────────────


async def fetch_page(
    client: httpx.AsyncClient, offset: int
) -> tuple[list[dict], int]:
    """Fetch a single page of records from the API."""
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
                return [], 0
            await asyncio.sleep(2 ** attempt)

    return [], 0


async def fetch_all_prices() -> list[dict]:
    """Fetch all current daily mandi prices."""
    all_records: list[dict] = []
    offset = 0
    total = 1

    async with httpx.AsyncClient() as client:
        records, total = await fetch_page(client, 0)
        all_records.extend(records)
        offset = PAGE_SIZE
        logger.info(f"API reports {total:,} total price records today. Fetching...")

        while offset < total:
            records, _ = await fetch_page(client, offset)
            all_records.extend(records)

            if len(all_records) % 2000 < PAGE_SIZE:
                logger.info(f"  Fetched {len(all_records):,} / {total:,}...")

            offset += PAGE_SIZE
            await asyncio.sleep(0.15)

    logger.info(f"✅ Fetched {len(all_records):,} price records")
    return all_records


# ── Transform & Save ──────────────────────────────────────────────────


def normalize_commodity(commodity: str) -> str:
    """Normalize commodity name to match I-ASCAP crop variables."""
    stripped = commodity.strip()
    if stripped in COMMODITY_NORMALIZE:
        return COMMODITY_NORMALIZE[stripped]
    return stripped.lower().replace(" ", "_").replace("(", "").replace(")", "")


def parse_price(value) -> float | None:
    """Safely parse a price value."""
    if value is None or value == "":
        return None
    try:
        v = float(value)
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


def transform_records(records: list[dict]) -> list[dict]:
    """Clean and normalize mandi price records."""
    cleaned: list[dict] = []

    for rec in records:
        state = str(rec.get("state", "")).strip()
        district = str(rec.get("district", "")).strip()
        market = str(rec.get("market", "")).strip()
        commodity = str(rec.get("commodity", "")).strip()
        variety = str(rec.get("variety", "")).strip()
        grade = str(rec.get("grade", "")).strip()
        arrival_date = str(rec.get("arrival_date", "")).strip()
        min_price = parse_price(rec.get("min_price"))
        max_price = parse_price(rec.get("max_price"))
        modal_price = parse_price(rec.get("modal_price"))

        if not state or not district or not commodity or modal_price is None:
            continue

        # Parse date
        parsed_date = None
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                parsed_date = datetime.strptime(arrival_date, fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue

        if not parsed_date:
            parsed_date = datetime.now().strftime("%Y-%m-%d")

        cleaned.append({
            "state": state,
            "district": district,
            "market": market,
            "commodity": commodity,
            "commodity_normalized": normalize_commodity(commodity),
            "variety": variety,
            "grade": grade,
            "arrival_date": parsed_date,
            "min_price": min_price,
            "max_price": max_price,
            "modal_price": modal_price,
        })

    logger.info(f"🔄 Cleaned {len(cleaned):,} price records (from {len(records):,} raw)")
    return cleaned


def save_prices_csv(prices: list[dict], path: Path) -> None:
    """Save cleaned prices as CSV."""
    if not prices:
        logger.warning("No prices to save")
        return

    fieldnames = [
        "state", "district", "market", "commodity", "commodity_normalized",
        "variety", "grade", "arrival_date", "min_price", "max_price", "modal_price",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(prices)

    logger.info(f"📄 Saved prices CSV: {path} ({len(prices):,} rows)")


# ── Database Load ──────────────────────────────────────────────────────


async def load_to_database(prices: list[dict]) -> None:
    """Insert price records into mandi_prices table."""
    import asyncpg
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / "backend" / ".env")
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set — skipping database load")
        return

    conn = await asyncpg.connect(db_url, ssl="require")

    try:
        # Create table if not exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS mandi_prices (
                id SERIAL PRIMARY KEY,
                state VARCHAR(100) NOT NULL,
                district VARCHAR(100) NOT NULL,
                market VARCHAR(200),
                commodity VARCHAR(200) NOT NULL,
                commodity_normalized VARCHAR(100),
                variety VARCHAR(200),
                grade VARCHAR(100),
                arrival_date DATE NOT NULL,
                min_price DECIMAL(12,2),
                max_price DECIMAL(12,2),
                modal_price DECIMAL(12,2) NOT NULL,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(state, district, market, commodity, variety, arrival_date)
            );

            CREATE INDEX IF NOT EXISTS idx_mandi_state ON mandi_prices(state);
            CREATE INDEX IF NOT EXISTS idx_mandi_district ON mandi_prices(district);
            CREATE INDEX IF NOT EXISTS idx_mandi_commodity ON mandi_prices(commodity_normalized);
            CREATE INDEX IF NOT EXISTS idx_mandi_date ON mandi_prices(arrival_date);
            CREATE INDEX IF NOT EXISTS idx_mandi_state_commodity ON mandi_prices(state, commodity_normalized);
        """)
        logger.info("✅ mandi_prices table ready")

        # Batch insert
        inserted = 0
        for price in prices:
            try:
                await conn.execute(
                    """
                    INSERT INTO mandi_prices
                        (state, district, market, commodity, commodity_normalized,
                         variety, grade, arrival_date, min_price, max_price, modal_price)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8::date, $9, $10, $11)
                    ON CONFLICT (state, district, market, commodity, variety, arrival_date)
                    DO UPDATE SET
                        min_price = EXCLUDED.min_price,
                        max_price = EXCLUDED.max_price,
                        modal_price = EXCLUDED.modal_price,
                        scraped_at = NOW()
                    """,
                    price["state"],
                    price["district"],
                    price["market"],
                    price["commodity"],
                    price["commodity_normalized"],
                    price["variety"],
                    price["grade"],
                    price["arrival_date"],
                    price["min_price"],
                    price["max_price"],
                    price["modal_price"],
                )
                inserted += 1
            except Exception as e:
                logger.warning(f"  Insert error for {price['market']}/{price['commodity']}: {e}")

        logger.info(f"✅ Database load complete: {inserted:,} rows upserted")

        count = await conn.fetchval("SELECT COUNT(*) FROM mandi_prices")
        logger.info(f"   Total mandi_prices rows: {count:,}")

    finally:
        await conn.close()


# ── Main ───────────────────────────────────────────────────────────────


async def main(load_db: bool = False) -> None:
    """Main pipeline."""
    logger.info("=" * 65)
    logger.info("SCRAPER 2: Daily Mandi Market Prices (data.gov.in)")
    logger.info("=" * 65)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Fetch all current prices
    logger.info("\n[1/3] Fetching today's mandi prices...")
    records = await fetch_all_prices()

    if not records:
        logger.error("No records fetched. Exiting.")
        return

    # Step 2: Transform and save
    logger.info("\n[2/3] Transforming and saving...")
    prices = transform_records(records)
    timestamp = datetime.now().strftime("%Y%m%d")
    save_prices_csv(prices, DATA_DIR / f"mandi_prices_{timestamp}.csv")

    # Print summary
    states = set(p["state"] for p in prices)
    districts = set(p["district"] for p in prices)
    commodities = set(p["commodity_normalized"] for p in prices)
    dates = set(p["arrival_date"] for p in prices)
    avg_modal = sum(p["modal_price"] for p in prices) / len(prices) if prices else 0

    logger.info(f"\n📊 Summary:")
    logger.info(f"   Price records:   {len(prices):,}")
    logger.info(f"   States:          {len(states)}")
    logger.info(f"   Districts:       {len(districts)}")
    logger.info(f"   Commodities:     {len(commodities)}")
    logger.info(f"   Date(s):         {', '.join(sorted(dates))}")
    logger.info(f"   Avg modal price: ₹{avg_modal:,.0f}/quintal")

    # Step 3: Database load (optional)
    if load_db:
        logger.info("\n[3/3] Loading into database...")
        await load_to_database(prices)
    else:
        logger.info("\n[3/3] Skipping database load (use --load-db to enable)")

    logger.info("\n" + "=" * 65)
    logger.info("✅ SCRAPER 2 COMPLETE!")
    logger.info("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape daily mandi prices from data.gov.in")
    parser.add_argument("--load-db", action="store_true", help="Load data into PostgreSQL database")
    args = parser.parse_args()

    asyncio.run(main(load_db=args.load_db))
