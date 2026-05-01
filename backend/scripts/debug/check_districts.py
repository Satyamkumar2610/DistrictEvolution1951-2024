import asyncio
import os

import asyncpg


async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    res = await conn.fetch("SELECT * FROM districts LIMIT 1")
    for r in res:
        print(dict(r))
    await conn.close()

asyncio.run(main())
