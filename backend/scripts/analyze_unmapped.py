import json
import asyncio
import asyncpg
import os
from difflib import SequenceMatcher
from dotenv import load_dotenv

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

async def main():
    load_dotenv()
    conn = await asyncpg.connect(os.environ.get("DATABASE_URL"))
    
    rows = await conn.fetch("SELECT cdk, district_name, state_name FROM districts")
    db_districts = [{"cdk": r["cdk"], "district": r["district_name"], "state": r["state_name"]} for r in rows]
    
    with open("/Users/satyamkumar/Desktop/DistrictEvolution/frontend/public/data/districts.json", "r") as f:
        geojson = json.load(f)
        
    with open("/Users/satyamkumar/Desktop/DistrictEvolution/frontend/public/data/map_bridge.json", "r") as f:
        bridge = json.load(f)
        
    unmapped = []
    for f in geojson["features"]:
        props = f["properties"]
        d = props.get("DISTRICT") or props.get("district_name") or props.get("district")
        s = props.get("STATE") or props.get("ST_NM") or props.get("state_name") or props.get("state")
        key = f"{d}|{s}"
        if key not in bridge:
            unmapped.append({"district": d, "state": s, "key": key})
            
    print("Unmapped Count:", len(unmapped))
    
    for u in unmapped:
        ud = str(u["district"]).lower()
        us = str(u["state"]).lower()
        
        best_match = None
        best_score = 0
        state_match = None
        state_score = 0
        
        for db in db_districts:
            db_d = str(db["district"]).lower()
            db_s = str(db["state"]).lower()
            
            if us == db_s or us in db_s or db_s in us:
                score = similar(ud, db_d)
                if score > state_score:
                    state_score = score
                    state_match = db
                    
            score = similar(ud, db_d)
            if score > best_score:
                best_score = score
                best_match = db
                
        print(f"\n--- {u['key']} ---")
        if state_match:
            print(f"State Match: {state_match['district']} ({state_match['state']}) - CDK: {state_match['cdk']} - Score: {state_score:.2f}")
        else:
            print("State Match: None")
        print(f"Global Match: {best_match['district']} ({best_match['state']}) - CDK: {best_match['cdk']} - Score: {best_score:.2f}")
        
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
