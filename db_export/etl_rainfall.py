#!/usr/bin/env python3
"""
ETL Script: Fetch IMD Rainfall Normals from data.gov.in API and insert into Neon DB.
Run once to populate the database.

Usage:
    python etl_rainfall.py
"""

import os
import sys
import httpx
import asyncio
import asyncpg
from typing import List, Dict, Any

# IMD API Configuration
IMD_API_BASE = "https://api.data.gov.in/resource/d0419b03-b41b-4226-b48b-0bc92bf139f8"
IMD_API_KEY = "579b464db66ec23bdd0000011d0179460bed4f26443f90cf4bee20d0"

# Database URL from environment (required — no hardcoded credentials)
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable is not set.")
    sys.exit(1)


async def fetch_all_records() -> List[Dict[str, Any]]:
    """Fetch all rainfall records from IMD API."""
    all_records = []
    offset = 0
    limit = 100
    total = 641  # Known total
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        while offset < total:
            url = f"{IMD_API_BASE}?api-key={IMD_API_KEY}&format=json&limit={limit}&offset={offset}"
            print(f"Fetching records {offset} to {offset + limit}...")
            
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                
                records = data.get("records", [])
                all_records.extend(records)
                
                if "total" in data:
                    total = int(data["total"])
                
                offset += limit
                
            except httpx.HTTPError as e:
                print(f"Error fetching data: {e}")
                break
    
    print(f"Fetched {len(all_records)} total records")
    return all_records


def parse_float(value: Any) -> float:
    """Safely parse float from API response."""
    try:
        return float(value) if value else 0.0
    except (ValueError, TypeError):
        return 0.0


async def insert_records(conn: asyncpg.Connection, records: List[Dict[str, Any]]) -> int:
    """Insert records into database using UPSERT."""
    inserted: int = 0
    
    for record in records:
        try:
            await conn.execute("""
                INSERT INTO rainfall_normals (
                    state_ut, district, jan, feb, mar, apr, may, jun, jul, aug, sep, oct, nov, dec_month,
                    annual, jjas, mam, ond, jan_feb
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                ON CONFLICT (state_ut, district) DO UPDATE SET
                    jan = EXCLUDED.jan, feb = EXCLUDED.feb, mar = EXCLUDED.mar, apr = EXCLUDED.apr,
                    may = EXCLUDED.may, jun = EXCLUDED.jun, jul = EXCLUDED.jul, aug = EXCLUDED.aug,
                    sep = EXCLUDED.sep, oct = EXCLUDED.oct, nov = EXCLUDED.nov, dec_month = EXCLUDED.dec_month,
                    annual = EXCLUDED.annual, jjas = EXCLUDED.jjas, mam = EXCLUDED.mam, ond = EXCLUDED.ond,
                    jan_feb = EXCLUDED.jan_feb
            """,
                record.get("state_ut", ""),
                record.get("district", ""),
                parse_float(record.get("jan")),
                parse_float(record.get("feb")),
                parse_float(record.get("mar")),
                parse_float(record.get("apr")),
                parse_float(record.get("may")),
                parse_float(record.get("jun")),
                parse_float(record.get("jul")),
                parse_float(record.get("aug")),
                parse_float(record.get("sep")),
                parse_float(record.get("oct")),
                parse_float(record.get("nov")),
                parse_float(record.get("dec")),
                parse_float(record.get("annual")),
                parse_float(record.get("jjas")),
                parse_float(record.get("mam")),
                parse_float(record.get("ond")),
                parse_float(record.get("jan_feb")),
            )
            inserted += 1  # type: ignore[operator]
        except Exception as e:
            print(f"Error inserting {record.get('district')}: {e}")
    
    return inserted


async def main():
    """Main ETL function."""
    print("=" * 60)
    print("IMD Rainfall Normals ETL")
    print("=" * 60)
    
    # Step 1: Fetch from API
    print("\n[1/3] Fetching data from IMD API...")
    records = await fetch_all_records()
    
    if not records:
        print("No records fetched. Exiting.")
        return
    
    # Step 2: Connect to database
    print(f"\n[2/3] Connecting to database...")
    conn = await asyncpg.connect(DATABASE_URL, ssl="require")
    
    # Create table if not exists
    print("Creating table if not exists...")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS rainfall_normals (
            id SERIAL PRIMARY KEY,
            state_ut VARCHAR(100) NOT NULL,
            district VARCHAR(100) NOT NULL,
            jan DECIMAL(10,2),
            feb DECIMAL(10,2),
            mar DECIMAL(10,2),
            apr DECIMAL(10,2),
            may DECIMAL(10,2),
            jun DECIMAL(10,2),
            jul DECIMAL(10,2),
            aug DECIMAL(10,2),
            sep DECIMAL(10,2),
            oct DECIMAL(10,2),
            nov DECIMAL(10,2),
            dec_month DECIMAL(10,2),
            annual DECIMAL(10,2),
            jjas DECIMAL(10,2),
            mam DECIMAL(10,2),
            ond DECIMAL(10,2),
            jan_feb DECIMAL(10,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(state_ut, district)
        )
    """)
    
    # Step 3: Insert records
    print(f"\n[3/3] Inserting {len(records)} records into database...")
    inserted = await insert_records(conn, records)
    
    # Verify
    count = await conn.fetchval("SELECT COUNT(*) FROM rainfall_normals")
    await conn.close()
    
    print("\n" + "=" * 60)
    print(f"✅ ETL Complete!")
    print(f"   Records fetched: {len(records)}")
    print(f"   Records inserted: {inserted}")
    print(f"   Total in database: {count}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
