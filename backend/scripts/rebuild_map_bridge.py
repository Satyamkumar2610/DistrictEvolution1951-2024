import json
import asyncio
import asyncpg
import re
from pathlib import Path
from difflib import SequenceMatcher

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def normalize_name(name):
    if not name: return ""
    name = str(name).lower()
    name = re.sub(r'[^a-z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

async def main():
    conn = await asyncpg.connect("postgresql://neondb_owner:npg_7AtbCMWo3ksv@ep-purple-butterfly-a18tkuor-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require")
    
    # 1. Get database districts
    rows = await conn.fetch("SELECT cdk, district_name, state_name FROM districts")
    db_districts = []
    for r in rows:
        db_districts.append({
            "cdk": r["cdk"],
            "district": r["district_name"],
            "state": r["state_name"],
            "norm_district": normalize_name(r["district_name"]),
            "norm_state": normalize_name(r["state_name"])
        })
        
    # 2. Get GeoJSON features
    with open("../frontend/public/data/districts.json", "r") as f:
        geojson = json.load(f)
        
    geo_features = []
    for f in geojson["features"]:
        props = f["properties"]
        d = props.get("DISTRICT") or props.get("district_name") or props.get("district")
        s = props.get("STATE") or props.get("ST_NM") or props.get("state_name") or props.get("state")
        if d and s:
            geo_features.append({
                "raw_key": f"{d}|{s}",
                "district": d,
                "state": s,
                "norm_district": normalize_name(d),
                "norm_state": normalize_name(s)
            })

    # Group geo features by normalized state to speed up matching
    geo_by_state = {}
    for g in geo_features:
        geo_by_state.setdefault(g["norm_state"], []).append(g)

    # 3. Match DB districts to Geo features
    bridge = {}
    unmatched = []

    # Map states first (handling edge cases)
    state_aliases = {
        "andaman and nicobar islands": ["andaman nicobar island", "andaman nicobar", "andaman nicobar islands"],
        "jammu and kashmir": ["jammu kashmir"],
        "delhi": ["nct of delhi"],
        "orissa": ["odisha"],
        "pondicherry": ["puducherry"],
        "telangana": ["andhra pradesh", "telangana"], # Telangana districts might be in AP in GeoJSON
        "andhra pradesh": ["andhra pradesh", "telangana"],
    }

    for db in db_districts:
        db_state = db["norm_state"]
        db_dist = db["norm_district"]
        
        # Determine candidate geo states
        candidate_states = [db_state]
        for canonical, aliases in state_aliases.items():
            if db_state == canonical or db_state in aliases:
                candidate_states.extend(aliases)
                candidate_states.append(canonical)
                
        candidate_geo = []
        for s in set(candidate_states):
            candidate_geo.extend(geo_by_state.get(s, []))
            
        best_match = None
        best_score = 0
        
        # Pass 1: Exact match
        for g in candidate_geo:
            if g["norm_district"] == db_dist:
                best_match = g
                best_score = 1.0
                break
                
        # Pass 2: Exact inclusion
        if not best_match:
            for g in candidate_geo:
                if g["norm_district"] in db_dist or db_dist in g["norm_district"]:
                    best_match = g
                    best_score = 0.9
                    break
                    
        # Pass 3: Fuzzy match
        if not best_match:
            for g in candidate_geo:
                score = similar(db_dist, g["norm_district"])
                if score > best_score:
                    best_score = score
                    best_match = g

        if best_match and best_score > 0.7:
            bridge[best_match["raw_key"]] = db["cdk"]
        else:
            unmatched.append(db)

    print(f"Mapped {len(bridge)} keys. Unmatched {len(unmatched)}")
    for u in unmatched[:10]:
        print(f"Unmatched: {u['district']} | {u['state']}")
        
    # Write output to both backend and frontend
    with open("data/map_bridge.json", "w") as f:
        json.dump(bridge, f, indent=2)
    with open("../frontend/public/data/map_bridge.json", "w") as f:
        json.dump(bridge, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
