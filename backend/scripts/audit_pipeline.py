import json
import asyncio
import asyncpg
from pathlib import Path
import sys

# Connect to database
async def main():
    import os
    from dotenv import load_dotenv
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is not set")
    conn = await asyncpg.connect(db_url)
    
    # 1. Get GeoJSON features
    with open("../frontend/public/data/districts.json", "r") as f:
        geojson = json.load(f)
        
    geo_features = []
    for f in geojson["features"]:
        props = f["properties"]
        d = props.get("DISTRICT") or props.get("district_name") or props.get("district")
        s = props.get("STATE") or props.get("ST_NM") or props.get("state_name") or props.get("state")
        if d and s:
            geo_features.append((d, s))
            
    # 2. Get map_bridge keys
    with open("data/map_bridge.json", "r") as f:
        bridge = json.load(f)
        
    # 3. Get database districts
    rows = await conn.fetch("SELECT cdk, district_name, state_name FROM districts")
    db_districts = {(r["district_name"].lower(), r["state_name"].lower()): r["cdk"] for r in rows}
    
    # A. District Key Matching
    print("--- A. DISTRICT KEY MATCHING ---")
    unmatched_geo = []
    for d, s in geo_features:
        key = f"{d}|{s}"
        if key not in bridge:
            unmatched_geo.append(key)
    print(f"Unmatched GeoJSON districts ({len(unmatched_geo)}):")
    for u in unmatched_geo[:10]: print(f"  {u}")
    
    db_names_in_bridge = set()
    for k in bridge.keys():
        d, s = k.split("|", 1)
        db_names_in_bridge.add((d.lower(), s.lower()))
        
    unmatched_db = []
    for (d, s), cdk in db_districts.items():
        if (d, s) not in db_names_in_bridge:
            unmatched_db.append(f"{d}|{s} ({cdk})")
            
    print(f"Unmatched Dataset districts ({len(unmatched_db)}):")
    for u in unmatched_db[:10]: print(f"  {u}")
    
    # Check duplicates in bridge
    cdk_to_keys = {}
    for k, v in bridge.items():
        cdk_to_keys.setdefault(v, []).append(k)
        
    duplicates = {k: v for k, v in cdk_to_keys.items() if len(v) > 1}
    print(f"Duplicate mappings (1 CDK -> Many Map Keys): {len(duplicates)}")
    for k, v in list(duplicates.items())[:5]: print(f"  {k}: {v}")
    
if __name__ == "__main__":
    asyncio.run(main())
