import asyncio
from app.db import pool

async def main():
    async with pool.acquire() as conn:
        print("Checking districts table for Telangana...")
        rows = await conn.fetch("SELECT cdk, district_name, state_name FROM districts WHERE state_name = 'Telangana' LIMIT 10")
        for row in rows:
            print(dict(row))
            
        print("\nChecking district_splits table...")
        rows = await conn.fetch("SELECT * FROM district_splits LIMIT 10")
        for row in rows:
            print(dict(row))
            
        print("\nChecking agri_metrics table for TG_...")
        rows = await conn.fetch("SELECT cdk, year FROM agri_metrics LIMIT 1")
        for row in rows:
            print(dict(row))
            print("Type of cdk:", type(row['cdk']))

asyncio.run(main())
