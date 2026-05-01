import asyncio
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

async def main():
    conn = await asyncpg.connect(DB_URL)
    events = await conn.fetch("SELECT * FROM split_events WHERE parent_cdk = 'WB_24parg_1961' OR parent_cdk = 'WB_south2_1971'")
    for e in events:
        print(dict(e))
    await conn.close()

asyncio.run(main())
