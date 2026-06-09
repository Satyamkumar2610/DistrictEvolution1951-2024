import asyncio
import os
from app.database import get_connection
import asyncpg

async def main():
    try:
        async with get_connection() as conn:
            print("--- Telangana Districts in Database ---")
            districts = await conn.fetch("SELECT cdk, district_name FROM districts WHERE state_name = 'Telangana'")
            for d in districts:
                print(f"{d['cdk']} - {d['district_name']}")
                
            print("\n--- Split Table Entries involving Telangana ---")
            splits = await conn.fetch("""
                SELECT ds.*, c.district_name as child_name, p.district_name as parent_name
                FROM district_splits ds
                JOIN districts c ON ds.child_lgd = c.cdk
                JOIN districts p ON ds.parent_lgd = p.cdk
                WHERE c.state_name = 'Telangana' OR p.state_name = 'Telangana'
            """)
            for s in splits:
                print(f"Child: {s['child_lgd']} ({s['child_name']}) -> Parent: {s['parent_lgd']} ({s['parent_name']})")
                
            print("\n--- Dataset Metrics Format ---")
            metrics = await conn.fetch("SELECT cdk, year, variable_name FROM agri_metrics LIMIT 5")
            for m in metrics:
                print(dict(m))
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
