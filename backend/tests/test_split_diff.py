import pytest
import asyncpg
import os
from fastapi.testclient import TestClient

@pytest.mark.asyncio
async def test_adilabad_split_diff():
    # 1. Connect to DB
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set")
        
    conn = await asyncpg.connect(db_url)
    
    # Check if Adilabad (TG_adilab_2011) event exists for 2024
    event = await conn.fetchrow("""
        SELECT id, parent_cdk, child_cdks, split_year 
        FROM split_events 
        WHERE parent_cdk = 'TG_adilab_2011' AND split_year = 2024
    """)
    if not event:
        await conn.close()
        # Debug: list all events to see what's there
        all_e = await conn.fetch("SELECT parent_cdk, split_year FROM split_events LIMIT 5")
        pytest.skip(f"Adilabad split event not found. Found: {all_e}")
        
    split_event_id = event["id"]
    
    # 2. Call the harmonizer.compute_split_diff
    from app.analytics.harmonizer import BoundaryHarmonizer
    harmonizer = BoundaryHarmonizer() 
    
    # Clean previous transfers for idempotent testing
    await conn.execute("DELETE FROM area_transfers WHERE split_event_id = $1", split_event_id)
    
    # The actual method signature is: async def compute_split_diff(self, db: asyncpg.Connection, split_event_id: int)
    await harmonizer.compute_split_diff(conn, split_event_id)
    
    # 3. Assertions
    transfers = await conn.fetch("""
        SELECT dest_cdk, area_sqkm, confidence_score 
        FROM area_transfers 
        WHERE split_event_id = $1
    """, split_event_id)
    
    assert len(transfers) > 0, "No area transfers were calculated."
    
    # Check that it calculated areas for the child districts
    child_cdks = event["child_cdks"]
    for t in transfers:
        assert t["dest_cdk"] in child_cdks
        assert t["area_sqkm"] > 0
        
    print(f"Computed {len(transfers)} area transfers for {event['parent_cdk']} successfully.")
    
    await conn.close()
