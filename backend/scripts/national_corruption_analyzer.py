import asyncio, asyncpg, os
from dotenv import load_dotenv
import pandas as pd
import numpy as np

async def main():
    load_dotenv()
    conn = await asyncpg.connect(os.environ.get("DATABASE_URL"))
    
    # 1. Fetch all lineage
    lineage_query = """
        SELECT c.cdk as child, p.cdk as parent, p.district_name as parent_name, p.state_name
        FROM district_splits ds
        JOIN districts c ON LOWER(c.district_name) = LOWER(ds.child_district) AND LOWER(c.state_name) = LOWER(ds.state_name)
        JOIN districts p ON LOWER(p.district_name) = LOWER(ds.parent_district) AND LOWER(p.state_name) = LOWER(ds.state_name)
    """
    l_rows = await conn.fetch(lineage_query)
    
    # parent -> list of children
    parent_to_children = {}
    for r in l_rows:
        p = r["parent"]
        c = r["child"]
        if p not in parent_to_children:
            parent_to_children[p] = {"name": r["parent_name"], "state": r["state_name"], "children": set()}
        parent_to_children[p]["children"].add(c)
        
    print(f"Total parents with active children mappings: {len(parent_to_children)}")

    # 2. We will analyze the year 2015 (a recent year with good coverage) across all states, 
    # measuring the difference between the Parent's raw value and the Sum of Parent + Children
    
    corruption_events = []
    
    # Fetch all area metrics for year 2015
    metrics_query = """
        SELECT cdk, variable_name, sum(value) as value
        FROM agri_metrics 
        WHERE year = 2015 AND variable_name LIKE '%_area'
        GROUP BY cdk, variable_name
    """
    m_rows = await conn.fetch(metrics_query)
    
    # cdk -> { variable_name -> value }
    district_data = {}
    for r in m_rows:
        c = r["cdk"]
        var = r["variable_name"]
        val = r["value"]
        if c not in district_data:
            district_data[c] = {}
        district_data[c][var] = val

    for p_cdk, p_info in parent_to_children.items():
        if p_cdk not in district_data:
            continue
            
        p_data = district_data[p_cdk]
        
        for var, corrupted_parent_val in p_data.items():
            true_sum = corrupted_parent_val
            children_sum = 0
            has_child_data = False
            
            for c_cdk in p_info["children"]:
                if c_cdk in district_data and var in district_data[c_cdk]:
                    val = district_data[c_cdk][var]
                    true_sum += val
                    children_sum += val
                    has_child_data = True
                    
            if has_child_data and true_sum > 0:
                loss_pct = 100 * (1 - (corrupted_parent_val / true_sum))
                if loss_pct > 1.0: # Meaningful corruption
                    corruption_events.append({
                        "parent_cdk": p_cdk,
                        "parent_name": p_info["name"],
                        "state": p_info["state"],
                        "variable": var,
                        "corrupted_val": corrupted_parent_val,
                        "true_val": true_sum,
                        "loss_pct": loss_pct,
                        "abs_loss": true_sum - corrupted_parent_val
                    })
                    
    df = pd.DataFrame(corruption_events)
    
    if df.empty:
        print("No corruption events found in 2015.")
        await conn.close()
        return

    print("\n=== A. National Data Integrity Report (2015 Snapshot) ===")
    print(f"Total affected districts (parents): {df['parent_cdk'].nunique()}")
    print(f"Total affected states: {df['state'].nunique()}")
    print(f"Total data points severely corrupted: {len(df)}")
    
    max_event = df.loc[df['abs_loss'].idxmax()]
    print(f"Maximum corruption event: {max_event['parent_name']} ({max_event['state']}) - {max_event['variable']}")
    print(f"  Lost {max_event['abs_loss']:.2f} 1000ha ({max_event['loss_pct']:.1f}%)")
    
    median_loss_pct = df['loss_pct'].median()
    median_abs_loss = df['abs_loss'].median()
    print(f"Median corruption severity: {median_loss_pct:.1f}% data loss ({median_abs_loss:.2f} 1000ha)")
    
    print("\nDistribution of Corruption Severity (Data Loss %):")
    print(f"  > 90% loss: {len(df[df['loss_pct'] > 90])} metrics")
    print(f"  50-90% loss: {len(df[(df['loss_pct'] <= 90) & (df['loss_pct'] > 50)])} metrics")
    print(f"  10-50% loss: {len(df[(df['loss_pct'] <= 50) & (df['loss_pct'] > 10)])} metrics")

    print("\n=== B. State-Level Impact Rankings ===")
    state_impact = df.groupby('state').agg(
        affected_districts=('parent_cdk', 'nunique'),
        avg_loss_pct=('loss_pct', 'mean'),
        total_abs_loss=('abs_loss', 'sum')
    ).reset_index().sort_values('total_abs_loss', ascending=False)
    
    print(state_impact.to_string(index=False))
    
    print("\n=== C. Temporal Analysis (Decade Fragmentation) ===")
    decade_query = """
        SELECT decade, count(id) as splits
        FROM district_splits
        GROUP BY decade
        ORDER BY decade
    """
    d_rows = await conn.fetch(decade_query)
    for r in d_rows:
        print(f"  {r['decade']}: {r['splits']} splits")

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
