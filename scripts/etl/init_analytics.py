import asyncio
import os
import asyncpg
import sys

# Get DB URL from env
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not set")
    sys.exit(1)

async def init_analytics():
    print("Connecting to database...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    print("Reading SQL file...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sql_path = os.path.join(script_dir, "advanced_analytics.sql")
    with open(sql_path, "r") as f:
        sql_content = f.read()

    print("Executing SQL...")
    try:
        await conn.execute(sql_content)
        print("✅ Successfully created Materialized Views and Indexes")
    except Exception as e:
        print(f"Error executing SQL: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(init_analytics())
