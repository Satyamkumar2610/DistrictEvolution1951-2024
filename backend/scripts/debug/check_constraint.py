import asyncio
import os

import asyncpg


async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    res = await conn.fetch("SELECT conname, pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid WHERE t.relname = 'area_transfers'")
    for r in res:
        print(dict(r))
    await conn.close()

asyncio.run(main())
