import asyncio
import os
import asyncpg
from pathlib import Path

async def main():
    db_url = os.getenv("DATABASE_URL")
    sql_path = Path(__file__).parent.parent / "db_export" / "004_split_analyzer.sql"
    
    with open(sql_path, "r") as f:
        sql = f.read()

    # The SQL has REFERENCES districts(cdk) which will fail because districts doesn't have cdk.
    # So I need to read the sql and fix it first in memory!
    # Wait, in the SQL file:
    # district_cdk        TEXT NOT NULL REFERENCES districts(cdk) ON DELETE CASCADE,
    sql = sql.replace("REFERENCES districts(cdk) ON DELETE CASCADE", "")

    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute(sql)
        print("Migration executed successfully.")
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        await conn.close()
    
asyncio.run(main())
