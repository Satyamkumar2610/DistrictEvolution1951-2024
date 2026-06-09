import asyncio
from app.database import get_connection

async def main():
    async with get_connection() as conn:
        print("Checking if we can join by district name for Telangana splits...")
        rows = await conn.fetch("""
            SELECT c.cdk as child_cdk, c.district_name as child_name, ds.parent_district, p.cdk as parent_cdk
            FROM districts c
            JOIN district_splits ds ON LOWER(c.district_name) = LOWER(ds.child_district) AND c.state_name = ds.state_name
            JOIN districts p ON ds.parent_lgd = p.cdk OR (LOWER(p.district_name) = LOWER(ds.parent_district) AND p.state_name = ds.state_name)
            WHERE c.state_name = 'Telangana'
            LIMIT 10
        """)
        for r in rows:
            print(dict(r))

asyncio.run(main())
