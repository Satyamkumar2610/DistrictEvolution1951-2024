import pytest  # type: ignore
import asyncpg  # type: ignore
import os


@pytest.mark.asyncio
async def test_adilabad_split_diff():
    """Integration test for spatial diff — requires live DB with Phase 1a schema."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set")

    conn = await asyncpg.connect(db_url)

    try:
        # Guard: skip if the schema hasn't been applied
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'split_events'
            )
        """)
        if not table_exists:
            pytest.skip("split_events table does not exist — Phase 1a schema not applied")

        # Check if Adilabad (TG_adilab_2011) event exists for 2024
        event = await conn.fetchrow("""
            SELECT id, parent_cdk, child_cdks, split_year
            FROM split_events
            WHERE parent_cdk = 'TG_adilab_2011' AND split_year = 2024
        """)
        if not event:
            pytest.skip("Adilabad split event not found in split_events")

        split_event_id = event["id"]

        # Call the harmonizer.compute_split_diff
        from app.analytics.harmonizer import BoundaryHarmonizer  # type: ignore
        harmonizer = BoundaryHarmonizer()

        # Clean previous transfers for idempotent testing
        await conn.execute(
            "DELETE FROM area_transfers WHERE split_event_id = $1",
            split_event_id,
        )

        await harmonizer.compute_split_diff(conn, split_event_id)

        # Assertions
        transfers = await conn.fetch("""
            SELECT dest_cdk, area_sqkm, confidence_score
            FROM area_transfers
            WHERE split_event_id = $1
        """, split_event_id)

        assert len(transfers) > 0, "No area transfers were calculated."

        child_cdks = list(event["child_cdks"])  # type: ignore
        for t in transfers:
            assert t["dest_cdk"] in child_cdks
            assert t["area_sqkm"] > 0

        print(
            f"Computed {len(transfers)} area transfers "
            f"for {event['parent_cdk']} successfully."
        )
    finally:
        await conn.close()
