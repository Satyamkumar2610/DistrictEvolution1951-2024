import asyncio
from dotenv import load_dotenv
import os
import asyncpg
from app.services.reconstructor_service import ReconstructorService
import json

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

async def main():
    conn = await asyncpg.connect(DB_URL)
    svc = ReconstructorService(conn)
    # Test on a known split district, e.g. WB_24parg_1961
    res = await svc.reconstruct("WB_24parg_1961", crop="rice", start_year=1960, end_year=2000)
    print("Leaf descendants:", res["leaf_descendants"])
    
    for t in res["timeline"]:
        if t["year"] in [1961, 1970, 1971, 1990, 1991, 2000]:
            print(f"Year {t['year']}: active={t['active_cdks']}, yield={t['yield_kg_ha']}")
    
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
