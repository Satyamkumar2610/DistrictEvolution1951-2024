import asyncio
import os
import asyncpg

async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    res = await conn.fetch("SELECT parent_cdk, child_cdks FROM split_events LIMIT 5")
    for r in res:
        print(dict(r))
    await conn.close()
asyncio.run(main())
