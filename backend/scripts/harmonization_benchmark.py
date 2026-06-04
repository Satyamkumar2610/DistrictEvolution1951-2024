import asyncio
import asyncpg
import os
import pandas as pd
import numpy as np
from dotenv import load_dotenv

async def main():
    load_dotenv()
    conn = await asyncpg.connect(os.environ.get("DATABASE_URL"))
    
    print("=== Harmonization Benchmark Study ===")
    
    # 1. We already have the metrics for Raw Unapportioned (Corrupted) vs Lineage-Aware (I-ASCAP)
    # 2. Fixed-Boundary Apportioned (ICRISAT) is mathematically identical to I-ASCAP Bottom-Up for historical analysis,
    #    BUT Fixed-Boundary permanently destroys modern districts. Let's quantify how many modern districts are lost.
    
    # Total modern districts currently active
    active_districts = await conn.fetchval("SELECT count(*) FROM districts WHERE end_year IS NULL OR end_year >= 2024")
    
    # Total 1966 baseline districts (approximate by parents + orphans)
    parents = await conn.fetchval("SELECT count(DISTINCT parent_district) FROM district_splits")
    orphans = await conn.fetchval("""
        SELECT count(*) FROM districts d
        LEFT JOIN district_splits p ON d.district_name = p.parent_district
        LEFT JOIN district_splits c ON d.district_name = c.child_district
        WHERE p.id IS NULL AND c.id IS NULL
    """)
    baseline_1966 = parents + orphans
    
    print(f"\n[Fixed-Boundary Apportioned Data (ICRISAT approach)]")
    print(f"Modern Districts (2024): {active_districts}")
    print(f"Baseline 1966 Districts: {baseline_1966}")
    print(f"Information Loss: {active_districts - baseline_1966} districts completely erased from modern policy analysis.")
    
    # 3. Area-Weighted Harmonization Failure Mode
    # Area-weighting assumes uniform distribution. What is the variance in yield between children of the same parent?
    # If children have wildly different yields, area-weighting is mathematically invalid.
    
    yield_variance_query = """
        SELECT ds.parent_district, ds.state_name, STDDEV(m.value) as yield_std, AVG(m.value) as yield_mean
        FROM district_splits ds
        JOIN districts c ON LOWER(c.district_name) = LOWER(ds.child_district) AND LOWER(c.state_name) = LOWER(ds.state_name)
        JOIN agri_metrics m ON m.cdk = c.cdk
        WHERE m.year = 2017 AND m.variable_name = 'rice_yield'
        GROUP BY ds.parent_district, ds.state_name
        HAVING count(m.id) > 1 AND AVG(m.value) > 0
        ORDER BY yield_std DESC
        LIMIT 10
    """
    y_rows = await conn.fetch(yield_variance_query)
    
    print(f"\n[Area-Weighted Harmonization Failure Modes]")
    print("Evaluating inter-child Yield variance (Area-weighting assumes homogeneity).")
    for r in y_rows:
        cv = (r['yield_std'] / r['yield_mean']) * 100 if r['yield_mean'] > 0 else 0
        print(f"Parent: {r['parent_district']} | Mean Yield: {r['yield_mean']:.2f} | StdDev: {r['yield_std']:.2f} | Coeff of Variation: {cv:.1f}%")

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
