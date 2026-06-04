import json
import asyncio
import asyncpg
import re
from pathlib import Path
from difflib import SequenceMatcher
import os
from dotenv import load_dotenv

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def normalize_name(name):
    if not name: return ""
    name = str(name).lower()
    name = re.sub(r'[^a-z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

async def main():
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is not set")
    conn = await asyncpg.connect(db_url)
    
    # 1. Get database districts
    # We want to map to districts that existed in 2011. Since our temporal validities might
    # not be perfectly exhaustive yet, we fetch all, but we will prioritize those with matching names.
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
        
    # 2. Get GeoJSON features (which are 2011 boundaries)
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

    # Group db districts by normalized state
    db_by_state = {}
    for d in db_districts:
        db_by_state.setdefault(d["norm_state"], []).append(d)

    # 3. Match Geo features to EXACTLY ONE parent DB district
    bridge = {}
    unmatched = []

    state_aliases = {
        "andaman nicobar island": ["andaman and nicobar islands", "andaman nicobar", "andaman nicobar islands"],
        "jammu kashmir": ["jammu and kashmir"],
        "nct of delhi": ["delhi"],
        "odisha": ["orissa"],
        "puducherry": ["pondicherry"],
        "telangana": ["andhra pradesh", "telangana"],
        "andhra pradesh": ["andhra pradesh", "telangana"],
    }

    for g in geo_features:
        geo_state = g["norm_state"]
        geo_dist = g["norm_district"]
        
        candidate_states = [geo_state]
        for canonical, aliases in state_aliases.items():
            if geo_state == canonical or geo_state in aliases:
                candidate_states.extend(aliases)
                candidate_states.append(canonical)
                
        candidate_db = []
        for s in set(candidate_states):
            candidate_db.extend(db_by_state.get(s, []))
            
        best_match = None
        best_score = 0
        
        # Pass 1: Exact match
        for db in candidate_db:
            if db["norm_district"] == geo_dist:
                # If there are multiple (e.g. TG_adilab_2011 vs AN_adilab_1951), 
                # prefer the one matching the current geo state if possible, or prioritize TG over AN for Telangana
                # Actually, the 2011 census uses "Andhra Pradesh" for Telangana districts, so we need care.
                score = 1.0
                if geo_state == 'telangana' and 'tg_' in db['cdk'].lower():
                    score = 1.1
                if score > best_score:
                    best_match = db
                    best_score = score
                
        # Pass 2: Fuzzy match
        if not best_match:
            for db in candidate_db:
                score = similar(geo_dist, db["norm_district"])
                if score > best_score:
                    best_score = score
                    best_match = db

        if best_match and best_score >= 0.7:
            bridge[g["raw_key"]] = best_match["cdk"]
        else:
            unmatched.append(g)

    print(f"Mapped {len(bridge)} GeoJSON keys to 1 CDK each. Unmatched {len(unmatched)}")
    for u in unmatched[:10]:
        print(f"Unmatched Geo Polygon: {u['district']} | {u['state']}")
        
    with open("data/map_bridge.json", "w") as f:
        json.dump(bridge, f, indent=2)
    with open("../frontend/public/data/map_bridge.json", "w") as f:
        json.dump(bridge, f, indent=2)

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
