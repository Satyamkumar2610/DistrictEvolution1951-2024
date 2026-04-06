#!/usr/bin/env python3
"""
Scraper 3: Minimum Support Price (MSP) Benchmark Data

Loads official MSP rates for major crops (2014-2025) into the database.
MSP is set by the Government of India and published by CACP.

This enables "farmer return" analysis:
    price_vs_msp_ratio = modal_price / msp_price

Usage:
    # Dry run — generate CSV only
    python scrape_msp_data.py

    # Full run — generate CSV and load into database
    python scrape_msp_data.py --load-db
"""

import argparse
import asyncio
import csv
import logging
import os
import sys
from pathlib import Path

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
logger = logging.getLogger("scraper.msp_data")

# ── Official MSP Data ─────────────────────────────────────────────────
# Source: Commission for Agricultural Costs & Prices (CACP)
# https://farmer.gov.in/mspstatements.aspx
# https://da.gov.in
# All prices in ₹ per quintal (100 kg)
#
# Note: These are official government-published rates.
# We hardcode them because MSP is a policy declaration, not API-queryable data.

MSP_DATA: list[dict] = [
    # ─── PADDY (RICE) ────────────────────────────────────────────
    # Common grade
    {"crop": "rice", "season": "kharif", "year": 2014, "msp": 1360, "grade": "Common"},
    {"crop": "rice", "season": "kharif", "year": 2015, "msp": 1410, "grade": "Common"},
    {"crop": "rice", "season": "kharif", "year": 2016, "msp": 1470, "grade": "Common"},
    {"crop": "rice", "season": "kharif", "year": 2017, "msp": 1550, "grade": "Common"},
    {"crop": "rice", "season": "kharif", "year": 2018, "msp": 1750, "grade": "Common"},
    {"crop": "rice", "season": "kharif", "year": 2019, "msp": 1815, "grade": "Common"},
    {"crop": "rice", "season": "kharif", "year": 2020, "msp": 1868, "grade": "Common"},
    {"crop": "rice", "season": "kharif", "year": 2021, "msp": 1940, "grade": "Common"},
    {"crop": "rice", "season": "kharif", "year": 2022, "msp": 2040, "grade": "Common"},
    {"crop": "rice", "season": "kharif", "year": 2023, "msp": 2183, "grade": "Common"},
    {"crop": "rice", "season": "kharif", "year": 2024, "msp": 2300, "grade": "Common"},
    {"crop": "rice", "season": "kharif", "year": 2025, "msp": 2425, "grade": "Common"},

    # ─── WHEAT ────────────────────────────────────────────────────
    {"crop": "wheat", "season": "rabi", "year": 2014, "msp": 1400, "grade": "FAQ"},
    {"crop": "wheat", "season": "rabi", "year": 2015, "msp": 1450, "grade": "FAQ"},
    {"crop": "wheat", "season": "rabi", "year": 2016, "msp": 1525, "grade": "FAQ"},
    {"crop": "wheat", "season": "rabi", "year": 2017, "msp": 1625, "grade": "FAQ"},
    {"crop": "wheat", "season": "rabi", "year": 2018, "msp": 1735, "grade": "FAQ"},
    {"crop": "wheat", "season": "rabi", "year": 2019, "msp": 1840, "grade": "FAQ"},
    {"crop": "wheat", "season": "rabi", "year": 2020, "msp": 1925, "grade": "FAQ"},
    {"crop": "wheat", "season": "rabi", "year": 2021, "msp": 1975, "grade": "FAQ"},
    {"crop": "wheat", "season": "rabi", "year": 2022, "msp": 2015, "grade": "FAQ"},
    {"crop": "wheat", "season": "rabi", "year": 2023, "msp": 2125, "grade": "FAQ"},
    {"crop": "wheat", "season": "rabi", "year": 2024, "msp": 2275, "grade": "FAQ"},
    {"crop": "wheat", "season": "rabi", "year": 2025, "msp": 2425, "grade": "FAQ"},

    # ─── SORGHUM (JOWAR) ─────────────────────────────────────────
    # Hybrid grade
    {"crop": "sorghum", "season": "kharif", "year": 2018, "msp": 2430, "grade": "Hybrid"},
    {"crop": "sorghum", "season": "kharif", "year": 2019, "msp": 2550, "grade": "Hybrid"},
    {"crop": "sorghum", "season": "kharif", "year": 2020, "msp": 2620, "grade": "Hybrid"},
    {"crop": "sorghum", "season": "kharif", "year": 2021, "msp": 2738, "grade": "Hybrid"},
    {"crop": "sorghum", "season": "kharif", "year": 2022, "msp": 2970, "grade": "Hybrid"},
    {"crop": "sorghum", "season": "kharif", "year": 2023, "msp": 3180, "grade": "Hybrid"},
    {"crop": "sorghum", "season": "kharif", "year": 2024, "msp": 3371, "grade": "Hybrid"},

    # ─── PEARL MILLET (BAJRA) ────────────────────────────────────
    {"crop": "pearl_millet", "season": "kharif", "year": 2018, "msp": 1950, "grade": "FAQ"},
    {"crop": "pearl_millet", "season": "kharif", "year": 2019, "msp": 2000, "grade": "FAQ"},
    {"crop": "pearl_millet", "season": "kharif", "year": 2020, "msp": 2150, "grade": "FAQ"},
    {"crop": "pearl_millet", "season": "kharif", "year": 2021, "msp": 2250, "grade": "FAQ"},
    {"crop": "pearl_millet", "season": "kharif", "year": 2022, "msp": 2350, "grade": "FAQ"},
    {"crop": "pearl_millet", "season": "kharif", "year": 2023, "msp": 2500, "grade": "FAQ"},
    {"crop": "pearl_millet", "season": "kharif", "year": 2024, "msp": 2625, "grade": "FAQ"},

    # ─── MAIZE ───────────────────────────────────────────────────
    {"crop": "maize", "season": "kharif", "year": 2018, "msp": 1700, "grade": "FAQ"},
    {"crop": "maize", "season": "kharif", "year": 2019, "msp": 1760, "grade": "FAQ"},
    {"crop": "maize", "season": "kharif", "year": 2020, "msp": 1850, "grade": "FAQ"},
    {"crop": "maize", "season": "kharif", "year": 2021, "msp": 1870, "grade": "FAQ"},
    {"crop": "maize", "season": "kharif", "year": 2022, "msp": 1962, "grade": "FAQ"},
    {"crop": "maize", "season": "kharif", "year": 2023, "msp": 2090, "grade": "FAQ"},
    {"crop": "maize", "season": "kharif", "year": 2024, "msp": 2225, "grade": "FAQ"},

    # ─── CHICKPEA (GRAM) ─────────────────────────────────────────
    {"crop": "chickpea", "season": "rabi", "year": 2018, "msp": 4400, "grade": "Desi"},
    {"crop": "chickpea", "season": "rabi", "year": 2019, "msp": 4620, "grade": "Desi"},
    {"crop": "chickpea", "season": "rabi", "year": 2020, "msp": 4875, "grade": "Desi"},
    {"crop": "chickpea", "season": "rabi", "year": 2021, "msp": 5100, "grade": "Desi"},
    {"crop": "chickpea", "season": "rabi", "year": 2022, "msp": 5230, "grade": "Desi"},
    {"crop": "chickpea", "season": "rabi", "year": 2023, "msp": 5335, "grade": "Desi"},
    {"crop": "chickpea", "season": "rabi", "year": 2024, "msp": 5440, "grade": "Desi"},

    # ─── PIGEONPEA (ARHAR/TUR) ───────────────────────────────────
    {"crop": "pigeonpea", "season": "kharif", "year": 2018, "msp": 5675, "grade": "FAQ"},
    {"crop": "pigeonpea", "season": "kharif", "year": 2019, "msp": 5800, "grade": "FAQ"},
    {"crop": "pigeonpea", "season": "kharif", "year": 2020, "msp": 6000, "grade": "FAQ"},
    {"crop": "pigeonpea", "season": "kharif", "year": 2021, "msp": 6300, "grade": "FAQ"},
    {"crop": "pigeonpea", "season": "kharif", "year": 2022, "msp": 6600, "grade": "FAQ"},
    {"crop": "pigeonpea", "season": "kharif", "year": 2023, "msp": 7000, "grade": "FAQ"},
    {"crop": "pigeonpea", "season": "kharif", "year": 2024, "msp": 7550, "grade": "FAQ"},

    # ─── GROUNDNUT ───────────────────────────────────────────────
    {"crop": "groundnut", "season": "kharif", "year": 2018, "msp": 4890, "grade": "In-shell"},
    {"crop": "groundnut", "season": "kharif", "year": 2019, "msp": 5090, "grade": "In-shell"},
    {"crop": "groundnut", "season": "kharif", "year": 2020, "msp": 5275, "grade": "In-shell"},
    {"crop": "groundnut", "season": "kharif", "year": 2021, "msp": 5550, "grade": "In-shell"},
    {"crop": "groundnut", "season": "kharif", "year": 2022, "msp": 5850, "grade": "In-shell"},
    {"crop": "groundnut", "season": "kharif", "year": 2023, "msp": 6377, "grade": "In-shell"},
    {"crop": "groundnut", "season": "kharif", "year": 2024, "msp": 6783, "grade": "In-shell"},

    # ─── RAPESEED/MUSTARD ────────────────────────────────────────
    {"crop": "rapeseed_and_mustard", "season": "rabi", "year": 2018, "msp": 4200, "grade": "FAQ"},
    {"crop": "rapeseed_and_mustard", "season": "rabi", "year": 2019, "msp": 4200, "grade": "FAQ"},
    {"crop": "rapeseed_and_mustard", "season": "rabi", "year": 2020, "msp": 4425, "grade": "FAQ"},
    {"crop": "rapeseed_and_mustard", "season": "rabi", "year": 2021, "msp": 4650, "grade": "FAQ"},
    {"crop": "rapeseed_and_mustard", "season": "rabi", "year": 2022, "msp": 5050, "grade": "FAQ"},
    {"crop": "rapeseed_and_mustard", "season": "rabi", "year": 2023, "msp": 5450, "grade": "FAQ"},
    {"crop": "rapeseed_and_mustard", "season": "rabi", "year": 2024, "msp": 5650, "grade": "FAQ"},

    # ─── SOYABEAN ────────────────────────────────────────────────
    {"crop": "soyabean", "season": "kharif", "year": 2018, "msp": 3399, "grade": "Yellow"},
    {"crop": "soyabean", "season": "kharif", "year": 2019, "msp": 3710, "grade": "Yellow"},
    {"crop": "soyabean", "season": "kharif", "year": 2020, "msp": 3880, "grade": "Yellow"},
    {"crop": "soyabean", "season": "kharif", "year": 2021, "msp": 3950, "grade": "Yellow"},
    {"crop": "soyabean", "season": "kharif", "year": 2022, "msp": 4300, "grade": "Yellow"},
    {"crop": "soyabean", "season": "kharif", "year": 2023, "msp": 4600, "grade": "Yellow"},
    {"crop": "soyabean", "season": "kharif", "year": 2024, "msp": 4892, "grade": "Yellow"},

    # ─── COTTON ──────────────────────────────────────────────────
    # Medium staple
    {"crop": "cotton", "season": "kharif", "year": 2018, "msp": 5150, "grade": "Medium Staple"},
    {"crop": "cotton", "season": "kharif", "year": 2019, "msp": 5255, "grade": "Medium Staple"},
    {"crop": "cotton", "season": "kharif", "year": 2020, "msp": 5515, "grade": "Medium Staple"},
    {"crop": "cotton", "season": "kharif", "year": 2021, "msp": 5726, "grade": "Medium Staple"},
    {"crop": "cotton", "season": "kharif", "year": 2022, "msp": 6080, "grade": "Medium Staple"},
    {"crop": "cotton", "season": "kharif", "year": 2023, "msp": 6620, "grade": "Medium Staple"},
    {"crop": "cotton", "season": "kharif", "year": 2024, "msp": 7121, "grade": "Medium Staple"},

    # ─── SUGARCANE ───────────────────────────────────────────────
    # FRP (Fair and Remunerative Price)
    {"crop": "sugarcane", "season": "kharif", "year": 2018, "msp": 275, "grade": "FRP"},
    {"crop": "sugarcane", "season": "kharif", "year": 2019, "msp": 275, "grade": "FRP"},
    {"crop": "sugarcane", "season": "kharif", "year": 2020, "msp": 285, "grade": "FRP"},
    {"crop": "sugarcane", "season": "kharif", "year": 2021, "msp": 290, "grade": "FRP"},
    {"crop": "sugarcane", "season": "kharif", "year": 2022, "msp": 305, "grade": "FRP"},
    {"crop": "sugarcane", "season": "kharif", "year": 2023, "msp": 315, "grade": "FRP"},
    {"crop": "sugarcane", "season": "kharif", "year": 2024, "msp": 340, "grade": "FRP"},

    # ─── SUNFLOWER ───────────────────────────────────────────────
    {"crop": "sunflower", "season": "kharif", "year": 2018, "msp": 5388, "grade": "FAQ"},
    {"crop": "sunflower", "season": "kharif", "year": 2019, "msp": 5650, "grade": "FAQ"},
    {"crop": "sunflower", "season": "kharif", "year": 2020, "msp": 5885, "grade": "FAQ"},
    {"crop": "sunflower", "season": "kharif", "year": 2021, "msp": 6015, "grade": "FAQ"},
    {"crop": "sunflower", "season": "kharif", "year": 2022, "msp": 6400, "grade": "FAQ"},
    {"crop": "sunflower", "season": "kharif", "year": 2023, "msp": 6760, "grade": "FAQ"},
    {"crop": "sunflower", "season": "kharif", "year": 2024, "msp": 7280, "grade": "FAQ"},

    # ─── SESAMUM ─────────────────────────────────────────────────
    {"crop": "sesamum", "season": "kharif", "year": 2018, "msp": 6249, "grade": "FAQ"},
    {"crop": "sesamum", "season": "kharif", "year": 2019, "msp": 6485, "grade": "FAQ"},
    {"crop": "sesamum", "season": "kharif", "year": 2020, "msp": 6855, "grade": "FAQ"},
    {"crop": "sesamum", "season": "kharif", "year": 2021, "msp": 7307, "grade": "FAQ"},
    {"crop": "sesamum", "season": "kharif", "year": 2022, "msp": 7830, "grade": "FAQ"},
    {"crop": "sesamum", "season": "kharif", "year": 2023, "msp": 8635, "grade": "FAQ"},
    {"crop": "sesamum", "season": "kharif", "year": 2024, "msp": 9267, "grade": "FAQ"},

    # ─── LENTIL (MASOOR) ─────────────────────────────────────────
    {"crop": "masoor", "season": "rabi", "year": 2018, "msp": 4250, "grade": "FAQ"},
    {"crop": "masoor", "season": "rabi", "year": 2019, "msp": 4475, "grade": "FAQ"},
    {"crop": "masoor", "season": "rabi", "year": 2020, "msp": 4800, "grade": "FAQ"},
    {"crop": "masoor", "season": "rabi", "year": 2021, "msp": 5100, "grade": "FAQ"},
    {"crop": "masoor", "season": "rabi", "year": 2022, "msp": 5500, "grade": "FAQ"},
    {"crop": "masoor", "season": "rabi", "year": 2023, "msp": 6000, "grade": "FAQ"},
    {"crop": "masoor", "season": "rabi", "year": 2024, "msp": 6425, "grade": "FAQ"},

    # ─── BARLEY ──────────────────────────────────────────────────
    {"crop": "barley", "season": "rabi", "year": 2018, "msp": 1410, "grade": "FAQ"},
    {"crop": "barley", "season": "rabi", "year": 2019, "msp": 1440, "grade": "FAQ"},
    {"crop": "barley", "season": "rabi", "year": 2020, "msp": 1525, "grade": "FAQ"},
    {"crop": "barley", "season": "rabi", "year": 2021, "msp": 1600, "grade": "FAQ"},
    {"crop": "barley", "season": "rabi", "year": 2022, "msp": 1635, "grade": "FAQ"},
    {"crop": "barley", "season": "rabi", "year": 2023, "msp": 1735, "grade": "FAQ"},
    {"crop": "barley", "season": "rabi", "year": 2024, "msp": 1850, "grade": "FAQ"},
]


# ── Save Logic ─────────────────────────────────────────────────────────


def save_msp_csv(data: list[dict], path: Path) -> None:
    """Save MSP data as CSV."""
    fieldnames = ["crop", "season", "year", "msp", "grade"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    logger.info(f"📄 Saved MSP CSV: {path} ({len(data)} rows)")


# ── Database Load ──────────────────────────────────────────────────────


async def load_to_database(data: list[dict]) -> None:
    """Create msp_rates table and load data."""
    import asyncpg
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / "backend" / ".env")
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set — skipping database load")
        return

    conn = await asyncpg.connect(db_url, ssl="require")

    try:
        # Create table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS msp_rates (
                id SERIAL PRIMARY KEY,
                crop VARCHAR(50) NOT NULL,
                season VARCHAR(20) NOT NULL,
                year INTEGER NOT NULL,
                msp_price DECIMAL(10,2) NOT NULL,
                grade VARCHAR(50),
                unit VARCHAR(20) DEFAULT 'INR/quintal',
                source VARCHAR(100) DEFAULT 'CACP (Commission for Agricultural Costs & Prices)',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(crop, season, year)
            );

            CREATE INDEX IF NOT EXISTS idx_msp_crop ON msp_rates(crop);
            CREATE INDEX IF NOT EXISTS idx_msp_year ON msp_rates(year);
            CREATE INDEX IF NOT EXISTS idx_msp_crop_year ON msp_rates(crop, year);
        """)
        logger.info("✅ msp_rates table ready")

        # Insert data
        inserted = 0
        for row in data:
            try:
                await conn.execute(
                    """
                    INSERT INTO msp_rates (crop, season, year, msp_price, grade)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (crop, season, year) DO UPDATE SET
                        msp_price = EXCLUDED.msp_price,
                        grade = EXCLUDED.grade
                    """,
                    row["crop"],
                    row["season"],
                    row["year"],
                    float(row["msp"]),
                    row["grade"],
                )
                inserted += 1
            except Exception as e:
                logger.warning(f"  Insert error for {row['crop']}/{row['year']}: {e}")

        logger.info(f"✅ Database load complete: {inserted} MSP rates loaded")

        count = await conn.fetchval("SELECT COUNT(*) FROM msp_rates")
        logger.info(f"   Total msp_rates rows: {count}")

    finally:
        await conn.close()


# ── Main ───────────────────────────────────────────────────────────────


async def main(load_db: bool = False) -> None:
    """Main pipeline."""
    logger.info("=" * 65)
    logger.info("SCRAPER 3: MSP (Minimum Support Price) Benchmark Data")
    logger.info("=" * 65)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    data = MSP_DATA

    # Print summary
    crops = set(d["crop"] for d in data)
    years = set(d["year"] for d in data)

    logger.info(f"\n📊 MSP Dataset Summary:")
    logger.info(f"   Total records:  {len(data)}")
    logger.info(f"   Crops:          {len(crops)} ({', '.join(sorted(crops))})")
    logger.info(f"   Year range:     {min(years)} – {max(years)}")
    logger.info(f"   Source:         CACP / Ministry of Agriculture")

    # Save CSV
    save_msp_csv(data, DATA_DIR / "msp_rates.csv")

    # Database load
    if load_db:
        logger.info("\nLoading into database...")
        await load_to_database(data)
    else:
        logger.info("\nSkipping database load (use --load-db to enable)")

    logger.info("\n" + "=" * 65)
    logger.info("✅ SCRAPER 3 COMPLETE!")
    logger.info("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load MSP benchmark data")
    parser.add_argument("--load-db", action="store_true", help="Load data into PostgreSQL database")
    args = parser.parse_args()

    asyncio.run(main(load_db=args.load_db))
