#!/usr/bin/env python3
"""
Hybrid ETL: Combine ICRISAT (1966-1997) + DES (1998-2021) crop data.

This script loads:
- ICRISAT data for years 1966-1997 (historical coverage)
- DES data for years 1998-2021 (more crops, seasonal breakdown)

Both sources are loaded with a 'source' column for transparency.
"""

import os
import sys
import asyncio
import asyncpg
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "raw"

# Add backend to path to use name_resolver
sys.path.append(str(PROJECT_ROOT / "backend"))
from app.services.name_resolver import resolve_lgd

ICRISAT_FILE = PROJECT_ROOT / "data" / "raw" / "ICRISAT-District Level Data.csv"
DES_FILE = DATA_DIR / "Sheet 1-crop-wise-area-production-yield (1).csv"

# Load environment
load_dotenv(PROJECT_ROOT / "backend" / ".env")
DATABASE_URL = os.getenv("DATABASE_URL")

async def fetch_lgd_lookup(conn) -> dict:
    """Fetch all districts from DB and build a lookup table."""
    lookup = {}
    rows = await conn.fetch("SELECT lgd_code, district_name, state_name FROM districts")
    for row in rows:
        d_name = row["district_name"].lower().strip()
        s_name = row["state_name"].lower().strip()
        lookup[(d_name, s_name)] = row["lgd_code"]
    return lookup


def process_icrisat(lgd_lookup: dict):
    """Generator yielding ICRISAT data records (1966-1997)."""
    print("Streaming ICRISAT data (1966-1997)...")
    
    crops = [
        'rice', 'wheat', 'kharif_sorghum', 'rabi_sorghum', 'sorghum',
        'pearl_millet', 'maize', 'finger_millet', 'barley', 'chickpea',
        'pigeonpea', 'minor_pulses', 'groundnut', 'sesamum', 'rapeseed_and_mustard',
        'safflower', 'castor', 'linseed', 'sunflower', 'soyabean',
        'oilseeds', 'cotton', 'sugarcane', 'potatoes', 'onion',
        'fruits_area', 'vegetables_area', 'fruits_and_vegetables_area', 'fodder_area'
    ]
    
    for df in pd.read_csv(ICRISAT_FILE, chunksize=20000):
        # Rename vital columns instead of dropping everything by index
        df = df.rename(columns={'Year': 'year', 'State Name': 'state_name', 'Dist Name': 'district_name'})
        df = df[(df['year'] >= 1966) & (df['year'] <= 1997)]
        
        for _, row in df.iterrows():
            year = int(row['year'])
            state = row['state_name']
            district = row['district_name']
            
            lgd_code = resolve_lgd(district, state, lgd_lookup)
            if not lgd_code:
                continue
            
            crops_list: list = crops[:22]  # type: ignore
            for crop in crops_list:
                crop_upper = crop.upper().replace('_', ' ')
                try:
                    area_col = f"{crop_upper} AREA (1000 ha)"
                    prod_col = f"{crop_upper} PRODUCTION (1000 tons)"
                    yld_col = f"{crop_upper} YIELD (Kg per ha)"
                    
                    if area_col in df.columns:
                        val = row[area_col]
                        if pd.notna(val) and float(val) >= 0:
                            yield (lgd_code, year, f'{crop}_area', float(val), 'ICRISAT')
                    
                    if prod_col in df.columns:
                        val = row[prod_col]
                        if pd.notna(val) and float(val) >= 0:
                            yield (lgd_code, year, f'{crop}_production', float(val), 'ICRISAT')
                            
                    if yld_col in df.columns:
                        val = row[yld_col]
                        if pd.notna(val) and float(val) >= 0:
                            yield (lgd_code, year, f'{crop}_yield', float(val), 'ICRISAT')
                except (ValueError, TypeError, KeyError):
                    continue


def process_des(lgd_lookup: dict):
    """Generator yielding DES data records (1998-2021)."""
    print("Streaming DES data (1998-2021)...")
    
    crop_mapping = {
        'Rice': 'rice', 'Wheat': 'wheat', 'Jowar': 'sorghum', 'Bajra': 'pearl_millet',
        'Maize': 'maize', 'Ragi': 'finger_millet', 'Barley': 'barley', 'Gram': 'chickpea',
        'Arhar/Tur': 'pigeonpea', 'Groundnut': 'groundnut', 'Sesamum': 'sesamum',
        'Rapeseed & Mustard': 'rapeseed_and_mustard', 'Safflower': 'safflower',
        'Castor Seed': 'castor', 'Linseed': 'linseed', 'Sunflower': 'sunflower',
        'Soyabean': 'soyabean', 'Cotton(Lint)': 'cotton', 'Sugarcane': 'sugarcane',
        'Potato': 'potatoes', 'Onion': 'onion', 'Moong(Green Gram)': 'moong',
        'Urad': 'urad', 'Masoor': 'masoor', 'Other Kharif Pulses': 'other_kharif_pulses',
        'Other Rabi Pulses': 'other_rabi_pulses', 'Niger Seed': 'niger_seed',
        'Tobacco': 'tobacco', 'Dry Chillies': 'chillies', 'Turmeric': 'turmeric',
        'Ginger': 'ginger', 'Garlic': 'garlic', 'Tapioca': 'tapioca',
        'Coriander': 'coriander', 'Banana': 'banana', 'Black Pepper': 'black_pepper',
        'Cardamom': 'cardamom', 'Coconut': 'coconut', 'Arecanut': 'arecanut',
        'Cashewnut': 'cashewnut', 'Mesta': 'mesta', 'Jute': 'jute',
        'Sweet Potato': 'sweet_potato', 'Horse-Gram': 'horse_gram',
        'Small Millets': 'small_millets', 'other oilseeds': 'other_oilseeds',
        'Peas & Beans': 'peas_beans', 'Khesari': 'khesari', 'Moth': 'moth',
        'Kulthi': 'kulthi', 'Lentil': 'lentil', 'Total Pulses': 'total_pulses',
        'Total Foodgrains': 'total_foodgrains',
    }
    
    for df in pd.read_csv(DES_FILE, chunksize=20000):
        df['year_int'] = df['year'].str[:4].astype(int)
        df['crop_normalized'] = df['crop_name'].str.strip().map(
            lambda x: crop_mapping.get(x, x.lower().replace(' ', '_').replace('(', '').replace(')', ''))
        )
        
        for _, row in df.iterrows():
            year = row['year_int']
            state = row['state_name']
            district = row['district_name']
            crop = row['crop_normalized']
            season = row['season'].strip().lower()
            
            lgd_code = resolve_lgd(district, state, lgd_lookup)
            if not lgd_code:
                continue
            
            season_suffix = '' if season == 'whole year' else f'_{season}'
            
            if pd.notna(row['area']) and float(row['area']) >= 0:
                yield (lgd_code, year, f'{crop}_area{season_suffix}', float(row['area']), 'DES')
            
            if pd.notna(row['production']) and float(row['production']) >= 0:
                yield (lgd_code, year, f'{crop}_production{season_suffix}', float(row['production']), 'DES')
            
            if pd.notna(row['yield']) and float(row['yield']) >= 0:
                yield_kg_ha = float(row['yield']) * 1000
                yield (lgd_code, year, f'{crop}_yield{season_suffix}', yield_kg_ha, 'DES')


async def load_to_database(conn: asyncpg.Connection, lgd_lookup: dict):
    """Load streaming data to database via a temporary table."""
    print(f"\nPreparing to stream records for database insertion...")
    
    await conn.execute("ALTER TABLE agri_metrics ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'ICRISAT'")
    
    print("Setting up temporary table...")
    await conn.execute("""
        CREATE TEMP TABLE agri_metrics_temp (
            district_lgd integer,
            year integer,
            variable_name text,
            value real,
            source text
        ) ON COMMIT DROP;
    """)
    
    def record_generator():
        yield from process_icrisat(lgd_lookup)
        yield from process_des(lgd_lookup)
    
    print(f"Executing COPY to temporary table...")
    
    # Needs to be a list/iterable of tuples. It will lazily evaluate the generator
    await conn.copy_records_to_table(
        'agri_metrics_temp',
        records=record_generator(),
        columns=['district_lgd', 'year', 'variable_name', 'value', 'source']
    )
    
    print("Upserting from temporary table to agri_metrics...")
    # Insert from temp table, resolving duplicates by keeping the last value inserted 
    # (achieved by grouping or ON CONFLICT, but ON CONFLICT works well if we distinct the temp table first)
    await conn.execute("""
        INSERT INTO agri_metrics (district_lgd, year, variable_name, value, source)
        SELECT district_lgd, year, variable_name, value, source
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY district_lgd, year, variable_name ORDER BY source DESC) as rn
            FROM agri_metrics_temp
        ) deduped
        WHERE rn = 1
        ON CONFLICT (district_lgd, year, variable_name) DO UPDATE SET
            value = EXCLUDED.value,
            source = EXCLUDED.source;
    """)
    
    # Verify
    count = await conn.fetchval("SELECT COUNT(*) FROM agri_metrics")
    icrisat_count = await conn.fetchval("SELECT COUNT(*) FROM agri_metrics WHERE source = 'ICRISAT'")
    des_count = await conn.fetchval("SELECT COUNT(*) FROM agri_metrics WHERE source = 'DES'")
    
    await conn.close()
    
    print(f"\n✅ Total records in database: {count:,}")
    print(f"   ICRISAT (1966-1997): {icrisat_count:,}")
    print(f"   DES (1998-2021): {des_count:,}")


async def flush_cache():
    """Flush the Redis cache so API serves fresh data."""
    try:
        import redis.asyncio as aioredis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = aioredis.from_url(redis_url, decode_responses=True)
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = await client.scan(cursor, match="iascap:*", count=100)
            if keys:
                await client.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
        print(f"✅ Cleared {deleted} keys from Redis Cache.")
    except Exception as e:
        print(f"⚠️ Could not flush Redis cache: {e}")

async def main():
    print("=" * 60)
    print("HYBRID ETL: ICRISAT (1966-1997) + DES (1998-2021)")
    print("=" * 60)
    
    # Connect database initially to get LGD lookup
    conn = await asyncpg.connect(DATABASE_URL, ssl='require')
    
    try:
        lgd_lookup = await fetch_lgd_lookup(conn)
        print(f"Loaded {len(lgd_lookup)} districts for name resolution")
        
        # Load to database directly from streamed generators
        await load_to_database(conn, lgd_lookup)
        
        # Verify
        count = await conn.fetchval("SELECT COUNT(*) FROM agri_metrics")
        icrisat_count = await conn.fetchval("SELECT COUNT(*) FROM agri_metrics WHERE source = 'ICRISAT'")
        des_count = await conn.fetchval("SELECT COUNT(*) FROM agri_metrics WHERE source = 'DES'")
        
        print(f"\n✅ Total records in database: {count:,}")
        print(f"   ICRISAT (1966-1997): {icrisat_count:,}")
        print(f"   DES (1998-2021): {des_count:,}")
        
    finally:
        await conn.close()
    
    # Flush Cache
    await flush_cache()
    
    print("\n" + "=" * 60)
    print("✅ HYBRID ETL COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
