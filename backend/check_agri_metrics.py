import asyncio
from app.database import get_connection

async def main():
    async with get_connection() as conn:
        print("--- agri_metrics for TG_bhadra_2024 ---")
        rows = await conn.fetch("SELECT * FROM agri_metrics WHERE cdk = 'TG_bhadra_2024' LIMIT 2")
        for r in rows:
            print(dict(r))
            
        print("\n--- Any agri_metrics for Telangana ---")
        rows = await conn.fetch("""
            SELECT a.cdk, a.year, a.variable_name, a.value, d.district_name, d.state_name
            FROM agri_metrics a
            JOIN districts d ON a.cdk = d.cdk
            WHERE d.state_name = 'Telangana' LIMIT 5
        """)
        for r in rows:
            print(dict(r))
            
        print("\n--- Any district_splits for Telangana ---")
        rows = await conn.fetch("""
            SELECT * FROM district_splits 
            WHERE state_name = 'Telangana' OR state_name = 'Andhra Pradesh' LIMIT 10
        """)
        for r in rows:
            print(dict(r))

asyncio.run(main())
