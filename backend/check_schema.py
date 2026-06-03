import asyncio
from app.database import get_connection

async def main():
    async with get_connection() as conn:
        print("--- Table Schema ---")
        rows = await conn.fetch("SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_name IN ('districts', 'district_splits', 'agri_metrics') ORDER BY table_name, ordinal_position")
        for r in rows:
            print(f"{r['table_name']}.{r['column_name']} ({r['data_type']})")

asyncio.run(main())
