import asyncio
from app.db import pool

async def main():
    async with pool.acquire() as conn:
        print("Checking districts table for Telangana...")
        rows = await conn.fetch("SELECT lgd_code, district_name, state_name FROM districts WHERE state_name = 'Telangana' LIMIT 10")
        for row in rows:
            print(dict(row))
            
        print("\nChecking district_splits table...")
        rows = await conn.fetch("SELECT * FROM district_splits LIMIT 10")
        for row in rows:
            print(dict(row))
            
        print("\nChecking agri_metrics table for TG_...")
        rows = await conn.fetch("SELECT district_lgd, year FROM agri_metrics LIMIT 1")
        for row in rows:
            print(dict(row))
            print("Type of district_lgd:", type(row['district_lgd']))

asyncio.run(main())
