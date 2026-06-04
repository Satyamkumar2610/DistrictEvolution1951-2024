import asyncio
import json
import os
import asyncpg
from dotenv import load_dotenv

async def main():
    load_dotenv()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is not set")
    
    # We load the extracted lineage we generated earlier
    with open('/tmp/lineage.json') as f:
        lineage = json.load(f)
        
    conn = await asyncpg.connect(db_url)
    
    updates = 0
    errors = 0
    
    # Prepare mapping for legacy CDKs (TG_xxx_2011) to strict lineage codes
    # We can match on name and state
    rows = await conn.fetch("SELECT cdk, district_name, state_name FROM districts")
    db_map = {}
    for r in rows:
        key = (r['district_name'].lower().strip(), r['state_name'].lower().strip())
        db_map[key] = r['cdk']
    
    print(f"Loaded {len(db_map)} districts from DB")
    
    for l_id, l_data in lineage.items():
        name = l_data['name'].lower().strip()
        state = l_data['state'].lower().strip()
        
        # State aliases for legacy mappings
        state_aliases = {
            'orissa': 'odisha',
            'uttaranchal': 'uttarakhand',
        }
        
        db_state = state_aliases.get(state, state)
        
        cdk = db_map.get((name, db_state))
        
        if cdk:
            start_year = l_data.get('first_year')
            end_year = l_data.get('last_year')
            
            # Unapportioned (Modern) dataset ends in 2017 in DB, though ICRISAT goes to 2019
            if end_year and end_year >= 2017:
                end_year = None # Null means currently active
                
            await conn.execute(
                "UPDATE districts SET start_year = $1, end_year = $2 WHERE cdk = $3",
                start_year, end_year, cdk
            )
            updates += 1
        else:
            errors += 1
            
    print(f"Successfully populated temporal validity for {updates} districts.")
    print(f"Could not map {errors} districts from lineage JSON.")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
