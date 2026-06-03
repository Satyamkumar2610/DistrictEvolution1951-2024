import asyncio
from app.database import get_connection

async def main():
    async with get_connection() as conn:
        print("--- district_splits for Telangana ---")
        rows = await conn.fetch("""
            SELECT * FROM district_splits 
            WHERE state_name = 'Telangana'
        """)
        for r in rows:
            print(dict(r))
            
        print(f"Total Telangana splits: {len(rows)}")

asyncio.run(main())
