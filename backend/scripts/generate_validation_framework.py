import asyncio, asyncpg, os
from dotenv import load_dotenv

async def main():
    load_dotenv()
    conn = await asyncpg.connect(os.environ.get("DATABASE_URL"))
    
    print("\n=== A. Lineage Completeness Report ===")
    
    total_districts = await conn.fetchval("SELECT count(*) FROM districts")
    
    parents = await conn.fetchval("""
        SELECT count(DISTINCT p.cdk) 
        FROM district_splits ds
        JOIN districts p ON LOWER(p.district_name) = LOWER(ds.parent_district) AND LOWER(p.state_name) = LOWER(ds.state_name)
    """)
    children = await conn.fetchval("""
        SELECT count(DISTINCT c.cdk) 
        FROM district_splits ds
        JOIN districts c ON LOWER(c.district_name) = LOWER(ds.child_district) AND LOWER(c.state_name) = LOWER(ds.state_name)
    """)
    
    orphans = await conn.fetchval("""
        SELECT count(DISTINCT d.cdk) FROM districts d
        LEFT JOIN district_splits p ON LOWER(d.district_name) = LOWER(p.parent_district) AND LOWER(d.state_name) = LOWER(p.state_name)
        LEFT JOIN district_splits c ON LOWER(d.district_name) = LOWER(c.child_district) AND LOWER(d.state_name) = LOWER(c.state_name)
        WHERE p.id IS NULL AND c.id IS NULL
    """)
    
    missing_start = await conn.fetchval("SELECT count(*) FROM districts WHERE start_year IS NULL")
    missing_end = await conn.fetchval("SELECT count(*) FROM districts WHERE end_year IS NULL")
    
    print(f"Total districts: {total_districts}")
    print(f"Districts acting as parents: {parents}")
    print(f"Districts acting as children: {children}")
    print(f"Orphan districts: {orphans}")
    print(f"Districts missing start_year: {missing_start}")
    print(f"Districts missing end_year (valid for active districts but useful for context): {missing_end}")
    
    print("\n=== B. Aggregation Accuracy Report (Sample 2017 Telangana) ===")
    query = """
        SELECT m.cdk, d.state_name, d.district_name, m.variable_name, m.value
        FROM agri_metrics m
        JOIN districts d ON m.cdk = d.cdk
        WHERE m.year = 2017 AND d.state_name ILIKE '%Telangana%'
    """
    rows = await conn.fetch(query)
    
    lineage_query = """
        SELECT c.cdk as child, p.cdk as parent, p.district_name, p.state_name
        FROM district_splits ds
        JOIN districts c ON LOWER(c.district_name) = LOWER(ds.child_district) AND LOWER(c.state_name) = LOWER(ds.state_name)
        JOIN districts p ON LOWER(p.district_name) = LOWER(ds.parent_district) AND LOWER(p.state_name) = LOWER(ds.state_name)
    """
    l_rows = await conn.fetch(lineage_query)
    child_to_parent = {r["child"]: {"cdk": r["parent"], "name": r["district_name"], "state": r["state_name"]} for r in l_rows}
    
    agg_map = {}
    for r in rows:
        c = r["cdk"]
        if c in child_to_parent:
            p = child_to_parent[c]
            p_cdk = p["cdk"]
            var = r["variable_name"]
            
            if p_cdk not in agg_map:
                agg_map[p_cdk] = {}
            if var not in agg_map[p_cdk]:
                agg_map[p_cdk][var] = {"name": p["name"], "sum_children": 0.0, "parent_val": 0.0}
                
            val = r["value"] if r["value"] else 0.0
            if "_yield" not in var:
                agg_map[p_cdk][var]["sum_children"] += val

    # Verify if parent raw data exists (which it should if apportioned data was loaded)
    for p_cdk, vars in agg_map.items():
        for var, data in vars.items():
            p_val = await conn.fetchval("SELECT value FROM agri_metrics WHERE cdk = $1 AND year = 2017 AND variable_name = $2", p_cdk, var)
            if p_val is not None:
                data["parent_val"] = float(p_val)
    
    for p_cdk, vars in agg_map.items():
        for var, data in vars.items():
            if var in ["rice_area", "rice_production", "cotton_area"]:
                err = abs(data['sum_children'] - data['parent_val'])
                print(f"{data['name']} ({var}): Sum(Child) = {data['sum_children']:.2f}, Parent(Apportioned) = {data['parent_val']:.2f} | Diff = {err:.2f}")

    print("\n=== D. Split Impact Quantification (Sample 2016 Split) ===")
    print("Quantifying area differences pre-and-post split for Adilabad...")
    pre_split = await conn.fetchval("SELECT sum(value) FROM agri_metrics WHERE cdk = 'TG_adilab_2011' AND year = 2015 AND variable_name = 'rice_area'")
    post_split_parent = await conn.fetchval("SELECT sum(value) FROM agri_metrics WHERE cdk = 'TG_adilab_2011' AND year = 2017 AND variable_name = 'rice_area'")
    post_split_child = await conn.fetchval("""
        SELECT sum(value) FROM agri_metrics m 
        JOIN districts c ON c.cdk = m.cdk
        JOIN district_splits ds ON LOWER(ds.child_district) = LOWER(c.district_name)
        WHERE ds.parent_district ILIKE 'Adilabad%' AND m.year = 2017 AND m.variable_name = 'rice_area'
    """)
    print(f"Pre-split 2015 Parent Rice Area: {pre_split}")
    print(f"Post-split 2017 Parent Rice Area: {post_split_parent}")
    print(f"Post-split 2017 Children Rice Area (excluding parent): {post_split_child}")
    print(f"Post-split 2017 Total (Parent+Children): {(post_split_parent or 0) + (post_split_child or 0)}")

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
