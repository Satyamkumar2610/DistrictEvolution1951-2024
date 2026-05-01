import asyncio

from app.db_compat import get_db_pool


async def main():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        print("Checking agri_metrics for TS/AP...")
        res = await conn.fetch("SELECT variable_name, count(*) as count FROM agri_metrics WHERE district_lgd IN (SELECT lgd_code FROM districts WHERE state_name ILIKE '%Andhra%' OR state_name ILIKE '%Telangana%') AND variable_name LIKE 'rice_%' GROUP BY variable_name")
        for r in res:
            print(dict(r))


if __name__ == '__main__':
    asyncio.run(main())
