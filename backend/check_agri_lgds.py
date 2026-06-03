import asyncio
from app.database import get_connection

async def main():
    async with get_connection() as conn:
        print("Checking get_agri_lgds logic...")
        cdks = ["TG_warang_1951", "TG_kumura_2024", 522]
        str_cdks = [str(c) for c in cdks]
        rows = await conn.fetch("""
            SELECT DISTINCT cdk
            FROM agri_metrics
            WHERE cdk = ANY($1::text[])
        """, str_cdks)
        for r in rows:
            print(dict(r))

asyncio.run(main())
