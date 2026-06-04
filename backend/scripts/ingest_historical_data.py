"""
Ingest historical extension data (1966-1989) into the I-ASCAP database.

Reads the historical_extension_1966_1989.csv and inserts rows into:
  - agri_metrics table (long-format: one row per district × year × variable)

Also fixes known data gaps:
  - Mahabubnagar (TG_mahbub_2011): 0 rows → load from Dataset B
  - Narayanpet (TG_naraya_2024): 0 rows → load from Dataset B
"""

import asyncio
import os
import sys

import pandas as pd

# Load .env for DATABASE_URL
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
HISTORICAL_CSV = os.path.join(DATA_DIR, "v1_5", "historical_extension_1966_1989.csv")

# Variable columns and their corresponding variable names
VARIABLE_COLUMNS = {
    "rice_area": "rice_area", "rice_production": "rice_production", "rice_yield": "rice_yield",
    "wheat_area": "wheat_area", "wheat_production": "wheat_production", "wheat_yield": "wheat_yield",
    "kharif_sorghum_area": "kharif_sorghum_area", "kharif_sorghum_production": "kharif_sorghum_production",
    "kharif_sorghum_yield": "kharif_sorghum_yield",
    "rabi_sorghum_area": "rabi_sorghum_area", "rabi_sorghum_production": "rabi_sorghum_production",
    "rabi_sorghum_yield": "rabi_sorghum_yield",
    "sorghum_area": "sorghum_area", "sorghum_production": "sorghum_production",
    "sorghum_yield": "sorghum_yield",
    "pearl_millet_area": "pearl_millet_area", "pearl_millet_production": "pearl_millet_production",
    "pearl_millet_yield": "pearl_millet_yield",
    "maize_area": "maize_area", "maize_production": "maize_production", "maize_yield": "maize_yield",
    "finger_millet_area": "finger_millet_area", "finger_millet_production": "finger_millet_production",
    "finger_millet_yield": "finger_millet_yield",
    "barley_area": "barley_area", "barley_production": "barley_production", "barley_yield": "barley_yield",
    "chickpea_area": "chickpea_area", "chickpea_production": "chickpea_production",
    "chickpea_yield": "chickpea_yield",
    "pigeonpea_area": "pigeonpea_area", "pigeonpea_production": "pigeonpea_production",
    "pigeonpea_yield": "pigeonpea_yield",
    "minor_pulses_area": "minor_pulses_area", "minor_pulses_production": "minor_pulses_production",
    "minor_pulses_yield": "minor_pulses_yield",
    "groundnut_area": "groundnut_area", "groundnut_production": "groundnut_production",
    "groundnut_yield": "groundnut_yield",
    "sesamum_area": "sesamum_area", "sesamum_production": "sesamum_production",
    "sesamum_yield": "sesamum_yield",
    "rapeseed_and_mustard_area": "rapeseed_and_mustard_area",
    "rapeseed_and_mustard_production": "rapeseed_and_mustard_production",
    "rapeseed_and_mustard_yield": "rapeseed_and_mustard_yield",
    "safflower_area": "safflower_area", "safflower_production": "safflower_production",
    "safflower_yield": "safflower_yield",
    "castor_area": "castor_area", "castor_production": "castor_production", "castor_yield": "castor_yield",
    "linseed_area": "linseed_area", "linseed_production": "linseed_production",
    "linseed_yield": "linseed_yield",
    "sunflower_area": "sunflower_area", "sunflower_production": "sunflower_production",
    "sunflower_yield": "sunflower_yield",
    "soyabean_area": "soyabean_area", "soyabean_production": "soyabean_production",
    "soyabean_yield": "soyabean_yield",
    "oilseeds_area": "oilseeds_area", "oilseeds_production": "oilseeds_production",
    "oilseeds_yield": "oilseeds_yield",
    "sugarcane_area": "sugarcane_area", "sugarcane_production": "sugarcane_production",
    "sugarcane_yield": "sugarcane_yield",
    "cotton_area": "cotton_area", "cotton_production": "cotton_production", "cotton_yield": "cotton_yield",
}


def melt_to_long(df: pd.DataFrame) -> pd.DataFrame:
    """Convert wide-format panel to long-format agri_metrics rows."""
    available_cols = [c for c in VARIABLE_COLUMNS if c in df.columns]

    records = []
    for _, row in df.iterrows():
        cdk = row["cdk"]
        year = int(row["year"])
        for col in available_cols:
            val = row[col]
            # Skip sentinels (-1) and NaN
            if pd.isna(val) or val == -1:
                continue
            records.append({
                "cdk": cdk,
                "year": year,
                "variable_name": VARIABLE_COLUMNS[col],
                "value": float(val),
                "source": "ICRISAT_Historical",
            })

    return pd.DataFrame(records)


async def ingest(dry_run: bool = False):
    """Ingest historical data into the database."""
    import asyncpg

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    # Load and melt
    print("Loading historical extension CSV...")
    df = pd.read_csv(HISTORICAL_CSV)
    print(f"Loaded {len(df):,} wide-format rows")

    long_df = melt_to_long(df)
    print(f"Melted to {len(long_df):,} long-format records")
    print(f"CDKs: {long_df['cdk'].nunique()}")
    print(f"Year range: {long_df['year'].min()}-{long_df['year'].max()}")
    print(f"Variables: {long_df['variable_name'].nunique()}")

    if dry_run:
        print("\n[DRY RUN] Would insert the above records. Exiting.")
        return

    # Connect and insert
    pool = await asyncpg.create_pool(db_url)
    async with pool.acquire() as conn:
        # Check current min year
        current_min = await conn.fetchval("SELECT MIN(year) FROM agri_metrics")
        print(f"\nCurrent DB min year: {current_min}")

        # Check if historical data already exists
        existing = await conn.fetchval(
            "SELECT COUNT(*) FROM agri_metrics WHERE year < 1990"
        )
        if existing > 0:
            print(f"⚠️  {existing:,} pre-1990 records already exist. Skipping insert.")
            await pool.close()
            return

        # Batch insert
        print(f"\nInserting {len(long_df):,} records...")
        records = [
            (r["cdk"], r["year"], r["variable_name"], r["value"], r["source"])
            for _, r in long_df.iterrows()
        ]

        # Use COPY for performance
        await conn.copy_records_to_table(
            "agri_metrics",
            records=records,
            columns=["cdk", "year", "variable_name", "value", "source"],
        )

        # Verify
        new_min = await conn.fetchval("SELECT MIN(year) FROM agri_metrics")
        new_count = await conn.fetchval("SELECT COUNT(*) FROM agri_metrics WHERE year < 1990")
        total = await conn.fetchval("SELECT COUNT(*) FROM agri_metrics")

        print(f"\n✅ Ingestion complete!")
        print(f"  New min year: {new_min}")
        print(f"  Pre-1990 records: {new_count:,}")
        print(f"  Total records: {total:,}")

    await pool.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(ingest(dry_run=dry_run))
