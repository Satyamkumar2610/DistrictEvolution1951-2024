import asyncio, asyncpg, os
from dotenv import load_dotenv

async def main():
    load_dotenv()
    conn = await asyncpg.connect(os.environ.get("DATABASE_URL"))
    
    print("\n=== A. Lineage Completeness Report ===")
    
    total_districts = await conn.fetchval("SELECT count(*) FROM districts")
    parents = await conn.fetchval("SELECT count(DISTINCT parent_lgd) FROM district_splits")
    children = await conn.fetchval("SELECT count(DISTINCT child_lgd) FROM district_splits")
    
    # Orphans: districts not in child_lgd or parent_lgd of district_splits
    orphans = await conn.fetchval("""
        SELECT count(*) FROM districts d
        WHERE d.lgd_code NOT IN (SELECT parent_lgd FROM district_splits)
        AND d.lgd_code NOT IN (SELECT child_lgd FROM district_splits)
    """)
    
    # Missing Temporal Validity (start_year / end_year)
    missing_start = await conn.fetchval("SELECT count(*) FROM districts WHERE start_year IS NULL")
    missing_end = await conn.fetchval("SELECT count(*) FROM districts WHERE end_year IS NULL")
    
    print(f"Total districts: {total_districts}")
    print(f"Districts acting as parents: {parents}")
    print(f"Districts acting as children: {children}")
    print(f"Orphan districts: {orphans}")
    print(f"Districts missing start_year: {missing_start}")
    print(f"Districts missing end_year (valid for active districts but useful for context): {missing_end}")
    
    print("\n=== B. Data Check ===")
    rows = await conn.fetch("""
        SELECT d.district_name, count(m.id) as metric_count
        FROM agri_metrics m
        JOIN districts d ON d.lgd_code = m.district_lgd
        WHERE m.year = 2017 AND d.state_name ILIKE '%Telangana%'
        GROUP BY d.district_name
    """)
    print("Districts in Telangana in 2017 with data:")
    for r in rows:
        print(f"  {r['district_name']}: {r['metric_count']}")
        
    await conn.close()
asyncio.run(main())
