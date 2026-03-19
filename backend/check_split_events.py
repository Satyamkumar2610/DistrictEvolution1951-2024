import asyncio
import os
import asyncpg

async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    res = await conn.fetch("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='split_events'")
    for r in res:
        print(dict(r))
    await conn.close()
    
asyncio.run(main())
