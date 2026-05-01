import asyncio
import os

import asyncpg


async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name='districts'")
    print([c['column_name'] for c in cols])
    await conn.close()
asyncio.run(main())
