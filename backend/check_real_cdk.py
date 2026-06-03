import asyncio
from app.database import get_connection

async def main():
    async with get_connection() as conn:
        print("Checking real CDKs from districts join...")
        rows = await conn.fetch("""
            SELECT
                ds.parent_district,
                ds.child_district,
                ds.split_year,
                pd.cdk as parent_cdk_real,
                cd.cdk as child_cdk_real
            FROM district_splits ds
            LEFT JOIN districts pd ON pd.district_name = ds.parent_district AND pd.state_name = ds.state_name
            LEFT JOIN districts cd ON cd.district_name = ds.child_district AND cd.state_name = ds.state_name
            WHERE ds.state_name = 'Telangana'
            LIMIT 10
        """)
        for r in rows:
            print(dict(r))

asyncio.run(main())
