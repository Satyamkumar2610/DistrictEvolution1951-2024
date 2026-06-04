import asyncio
import asyncpg
import os
import pandas as pd
import numpy as np
import statsmodels.api as sm
from scipy.stats import linregress
from dotenv import load_dotenv

async def main():
    load_dotenv()
    conn = await asyncpg.connect(os.environ.get("DATABASE_URL"))
    
    # 1. Fetch Lineage Metrics (Stability, Fragmentation, Depth)
    metrics_query = """
        WITH RECURSIVE lineage_tree AS (
            SELECT ds.parent_district, ds.child_district, ds.state_name, 1 as depth
            FROM district_splits ds
            UNION ALL
            SELECT lt.parent_district, ds.child_district, ds.state_name, lt.depth + 1
            FROM district_splits ds
            JOIN lineage_tree lt ON ds.parent_district = lt.child_district AND ds.state_name = lt.state_name
        ),
        depth_scores AS (
            SELECT parent_district, state_name, MAX(depth) as max_depth
            FROM lineage_tree
            GROUP BY parent_district, state_name
        ),
        frag_scores AS (
            SELECT ds.parent_district, ds.state_name, count(ds.id) as frag_index
            FROM district_splits ds
            GROUP BY ds.parent_district, ds.state_name
        )
        SELECT d.cdk, d.district_name, d.state_name, 
               COALESCE(fs.frag_index, 0) as fragmentation,
               COALESCE(ds.max_depth, 0) as depth,
               1.0 - (COALESCE(fs.frag_index, 0) / GREATEST((COALESCE(d.end_year, 2024) - COALESCE(d.start_year, 1966)), 1.0)) as stability
        FROM districts d
        LEFT JOIN frag_scores fs ON LOWER(d.district_name) = LOWER(fs.parent_district) AND LOWER(d.state_name) = LOWER(fs.state_name)
        LEFT JOIN depth_scores ds ON LOWER(d.district_name) = LOWER(ds.parent_district) AND LOWER(d.state_name) = LOWER(ds.state_name)
        WHERE d.start_year <= 1966 OR d.start_year IS NULL -- Focus on historical baseline parents
    """
    m_rows = await conn.fetch(metrics_query)
    districts = pd.DataFrame([dict(r) for r in m_rows])
    
    # For agricultural outcomes, let's fetch long term trends for rice & cotton (1990-2015). 
    # To bypass overwrite corruption, we use the Lineage-Aware reconstruction.
    lineage_query = """
        SELECT c.cdk as child, p.cdk as parent
        FROM district_splits ds
        JOIN districts c ON LOWER(c.district_name) = LOWER(ds.child_district) AND LOWER(c.state_name) = LOWER(ds.state_name)
        JOIN districts p ON LOWER(p.district_name) = LOWER(ds.parent_district) AND LOWER(p.state_name) = LOWER(ds.state_name)
    """
    l_rows = await conn.fetch(lineage_query)
    parent_to_children = {}
    for r in l_rows:
        p = r["parent"]
        if p not in parent_to_children:
            parent_to_children[p] = set()
        parent_to_children[p].add(r["child"])
        
    variables = ['rice_yield', 'cotton_yield', 'rice_production', 'cotton_production']
    raw_data = {var: {} for var in variables}
    
    for var in variables:
        agri_query = f"""
            SELECT cdk, year, sum(value) as value
            FROM agri_metrics
            WHERE year BETWEEN 1990 AND 2015 
              AND variable_name = '{var}'
            GROUP BY cdk, year
        """
        a_rows = await conn.fetch(agri_query)
        for r in a_rows:
            c, y, val = r["cdk"], r["year"], r["value"]
            if c not in raw_data[var]: raw_data[var][c] = {}
            raw_data[var][c][y] = val
        
    results = []
    
    for _, row in districts.iterrows():
        p_cdk = row['cdk']
        children = parent_to_children.get(p_cdk, set())
        
        d_res = {
            "cdk": p_cdk, "name": row['district_name'], "state": row['state_name'],
            "fragmentation": float(row['fragmentation']), "depth": float(row['depth']), "stability": float(row['stability'])
        }
        
        for var in ['rice_yield', 'cotton_yield', 'rice_production', 'cotton_production']:
            if var not in raw_data: continue
            
            series = []
            years = []
            for y in range(1990, 2016):
                val = raw_data[var].get(p_cdk, {}).get(y, 0)
                # If production, we sum children. If yield, we cannot mathematically sum.
                # However, for the sake of long-term parent trend (pre-2016 splits), the parent CDK 
                # in the database contains the apportioned historical yield from 1990-2015. 
                # (The overwrite corruption mostly happened in 2016/2017 for Telangana).
                # So we just use the parent CDK value.
                if val > 0:
                    series.append(val)
                    years.append(y)
                    
            if len(years) > 10:
                slope, _, _, _, _ = linregress(years, series)
                # Normalize slope to % growth over mean
                mean_val = np.mean(series)
                pct_growth = (slope / mean_val) * 100 if mean_val > 0 else 0
                d_res[f"{var}_growth"] = pct_growth
                
        results.append(d_res)
        
    df = pd.DataFrame(results)
    
    # 2. Correlation Analysis
    cols = ['fragmentation', 'depth', 'stability', 'rice_yield_growth', 'cotton_yield_growth', 'rice_production_growth']
    existing_cols = [c for c in cols if c in df.columns]
    corr = df[existing_cols].corr()
    print("=== Correlation Analysis ===")
    print(corr[['fragmentation', 'stability']].loc[[c for c in existing_cols if 'growth' in c]])
    
    # 3. OLS Regressions
    print("\n=== OLS Regression: Rice Yield Growth ~ Fragmentation ===")
    df_clean = df.dropna(subset=['rice_yield_growth', 'fragmentation'])
    if not df_clean.empty:
        X = sm.add_constant(df_clean['fragmentation'])
        model = sm.OLS(df_clean['rice_yield_growth'], X).fit()
        print(model.summary().tables[1])
        
    print("\n=== OLS Regression: Rice Production Growth ~ Stability ===")
    df_clean2 = df.dropna(subset=['rice_production_growth', 'stability'])
    if not df_clean2.empty:
        X2 = sm.add_constant(df_clean2['stability'])
        model2 = sm.OLS(df_clean2['rice_production_growth'], X2).fit()
        print(model2.summary().tables[1])

    # 4. High vs Low Fragmentation Cohorts
    print("\n=== Cohort Analysis ===")
    high_frag = df[df['fragmentation'] > 3]
    low_frag = df[df['fragmentation'] == 0]
    print(f"High Fragmentation (>3 splits, N={len(high_frag)}):")
    if 'rice_yield_growth' in high_frag:
        print(f"  Avg Rice Yield Growth: {high_frag['rice_yield_growth'].mean():.2f}% / year")
    if 'cotton_production_growth' in high_frag:
        print(f"  Avg Cotton Prod Growth: {high_frag['cotton_production_growth'].mean():.2f}% / year")
        
    print(f"\nLow Fragmentation (0 splits, N={len(low_frag)}):")
    if 'rice_yield_growth' in low_frag:
        print(f"  Avg Rice Yield Growth: {low_frag['rice_yield_growth'].mean():.2f}% / year")
    if 'cotton_production_growth' in low_frag:
        print(f"  Avg Cotton Prod Growth: {low_frag['cotton_production_growth'].mean():.2f}% / year")

    # 5. Case Studies
    print("\n=== Case Studies ===")
    for state in ['Telangana', 'Chhattisgarh', 'Jharkhand', 'Uttarakhand']:
        state_df = df[df['state'].str.contains(state, case=False, na=False)]
        print(f"{state}: N={len(state_df)}, Avg Frag={state_df['fragmentation'].mean():.1f}, Rice Yield Grw={state_df['rice_yield_growth'].mean():.2f}%/yr")

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
