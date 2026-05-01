import asyncio
import os

import asyncpg


async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    res = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    for r in res:
        print(r['table_name'])
    await conn.close()

asyncio.run(main())
