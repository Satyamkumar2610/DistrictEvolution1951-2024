import asyncio
from app.database import get_connection

async def main():
    async with get_connection() as conn:
        print("--- district_splits ---")
        rows = await conn.fetch("SELECT * FROM district_splits LIMIT 15")
        for r in rows:
            print(dict(r))

asyncio.run(main())
