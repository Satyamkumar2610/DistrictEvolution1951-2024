import asyncio, asyncpg, os
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from scipy.stats import linregress

async def main():
    load_dotenv()
    conn = await asyncpg.connect(os.environ.get("DATABASE_URL"))
    
    # 1. Fetch lineage map
    lineage_query = """
        SELECT c.cdk as child, p.cdk as parent, p.district_name as parent_name, p.state_name
        FROM district_splits ds
        JOIN districts c ON LOWER(c.district_name) = LOWER(ds.child_district) AND LOWER(c.state_name) = LOWER(ds.state_name)
        JOIN districts p ON LOWER(p.district_name) = LOWER(ds.parent_district) AND LOWER(p.state_name) = LOWER(ds.state_name)
    """
    l_rows = await conn.fetch(lineage_query)
    
    parent_to_children = {}
    for r in l_rows:
        p = r["parent"]
        if p not in parent_to_children:
            parent_to_children[p] = {"name": r["parent_name"], "state": r["state_name"], "children": set()}
        parent_to_children[p]["children"].add(r["child"])
        
    print(f"Total parents with active children mappings: {len(parent_to_children)}")

    # 2. Fetch all rice_area time-series data from 2005 to 2017
    metrics_query = """
        SELECT cdk, year, sum(value) as value
        FROM agri_metrics 
        WHERE year BETWEEN 2005 AND 2017 AND variable_name = 'rice_area'
        GROUP BY cdk, year
        ORDER BY year
    """
    m_rows = await conn.fetch(metrics_query)
    
    # cdk -> { year -> value }
    district_data = {}
    for r in m_rows:
        c = r["cdk"]
        yr = r["year"]
        val = r["value"]
        if c not in district_data:
            district_data[c] = {}
        district_data[c][yr] = val

    results = []
    
    years = list(range(2005, 2018))

    for p_cdk, p_info in parent_to_children.items():
        if p_cdk not in district_data:
            continue
            
        corrupted_series = []
        lineage_series = []
        valid_years = []
        
        for yr in years:
            # Corrupted logic: Just whatever the parent CDK has
            c_val = district_data[p_cdk].get(yr, None)
            
            # Lineage logic: Parent CDK + Children CDKs
            l_val = c_val if c_val is not None else 0
            has_child_data = False
            for child in p_info["children"]:
                if child in district_data and yr in district_data[child]:
                    l_val += district_data[child][yr]
                    has_child_data = True
            
            # We only count if parent actually had data, or if children had data (meaning a split occurred)
            if c_val is not None or has_child_data:
                corrupted_series.append(c_val if c_val is not None else 0)
                lineage_series.append(l_val)
                valid_years.append(yr)
                
        if len(valid_years) >= 5: # Need enough data points for a trend
            # Calculate trends
            slope_corr, _, _, _, _ = linregress(valid_years, corrupted_series)
            slope_lin, _, _, _, _ = linregress(valid_years, lineage_series)
            
            # Calculate 2015 vs 2017 shock (to catch the 2016 splits)
            if 2015 in valid_years and 2017 in valid_years:
                idx_2015 = valid_years.index(2015)
                idx_2017 = valid_years.index(2017)
                
                c_15 = corrupted_series[idx_2015]
                c_17 = corrupted_series[idx_2017]
                l_15 = lineage_series[idx_2015]
                l_17 = lineage_series[idx_2017]
                
                if c_15 > 0:
                    c_shock = (c_17 - c_15) / c_15
                    l_shock = (l_17 - l_15) / l_15
                else:
                    c_shock = 0
                    l_shock = 0
            else:
                c_shock = 0
                l_shock = 0

            results.append({
                "cdk": p_cdk,
                "name": p_info["name"],
                "state": p_info["state"],
                "slope_corrupted": slope_corr,
                "slope_lineage": slope_lin,
                "shock_corrupted": c_shock,
                "shock_lineage": l_shock
            })
            
    df = pd.DataFrame(results)
    
    if df.empty:
        print("No trend data found.")
        await conn.close()
        return

    print("\n=== A. False Trend Report (2005-2017) ===")
    # False Decline: corrupted slope < 0, but lineage slope > 0
    false_declines = df[(df['slope_corrupted'] < 0) & (df['slope_lineage'] > 0)]
    print(f"Districts showing FALSE DECLINE (Negative growth in corrupt DB, Positive growth in reality): {len(false_declines)}")
    if not false_declines.empty:
        print(false_declines[['name', 'state', 'slope_corrupted', 'slope_lineage']].head())
    
    # False Growth: corrupted slope > 0, lineage slope < 0 (Rare but possible if child shrinks but parent got assigned something weird)
    false_growth = df[(df['slope_corrupted'] > 0) & (df['slope_lineage'] < 0)]
    print(f"\nDistricts showing FALSE GROWTH: {len(false_growth)}")
    
    print("\n=== B. False Shock Report (2015 vs 2017) ===")
    # False Collapse: Corrupted drops by >30%, Lineage drops by <10% (or grows)
    false_collapses = df[(df['shock_corrupted'] < -0.30) & (df['shock_lineage'] > -0.10)]
    print(f"Districts showing ARTIFICIAL COLLAPSE (>30% drop due to boundary change): {len(false_collapses)}")
    if not false_collapses.empty:
        print(false_collapses[['name', 'state', 'shock_corrupted', 'shock_lineage']].sort_values('shock_corrupted').head(10))
        
    print("\n=== C. Regression Sensitivity ===")
    avg_corr_slope = df['slope_corrupted'].mean()
    avg_lin_slope = df['slope_lineage'].mean()
    print(f"National Average Trend (Corrupted): {avg_corr_slope:.2f} (1000ha/year)")
    print(f"National Average Trend (Lineage-Aware): {avg_lin_slope:.2f} (1000ha/year)")
    
    print("\n=== E. National Summary ===")
    pct_false_trends = (len(false_declines) + len(false_growth)) / len(df) * 100
    print(f"Percentage of statistical trend analyses that would be WRONG: {pct_false_trends:.1f}%")

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
