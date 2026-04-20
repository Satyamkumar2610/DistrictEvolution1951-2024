import asyncio
import os
import asyncpg

async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    
    # Drop old tables
    await conn.execute("DROP VIEW IF EXISTS v_lineage_tree CASCADE;")
    await conn.execute("DROP TABLE IF EXISTS split_enrichment CASCADE;")
    await conn.execute("DROP TABLE IF EXISTS area_transfers CASCADE;")
    await conn.execute("DROP TABLE IF EXISTS split_events CASCADE;")
    
    # Recreate split_events correctly
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS split_events (
            id                      SERIAL PRIMARY KEY,
            parent_cdk              TEXT NOT NULL,
            child_cdks              TEXT[] NOT NULL,
            split_year              INTEGER NOT NULL,
            event_type              TEXT DEFAULT 'SPLIT',
            geometry_status         geometry_status_type NOT NULL DEFAULT 'unknown',
            source_notes            TEXT,
            area_conservation_error DOUBLE PRECISION,  
            composite_confidence    FLOAT,             

            created_at              TIMESTAMP DEFAULT NOW(),
            updated_at              TIMESTAMP DEFAULT NOW(),

            UNIQUE(parent_cdk, split_year)
        );
        CREATE INDEX idx_split_parent ON split_events (parent_cdk);
        CREATE INDEX idx_split_year ON split_events (split_year);
    """)

    # Recreate area_transfers correctly
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS area_transfers (
            id                  SERIAL PRIMARY KEY,
            split_event_id      INTEGER NOT NULL REFERENCES split_events(id) ON DELETE CASCADE,
            source_cdk          TEXT NOT NULL,
            dest_cdk            TEXT NOT NULL,
            transfer_type       transfer_type NOT NULL,
            
            area_sqkm           DOUBLE PRECISION NOT NULL,
            confidence_score    FLOAT NOT NULL DEFAULT 0.0 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),

            geometry            GEOMETRY(MultiPolygon, 4326),

            CONSTRAINT geometry_required_for_high_confidence
            CHECK (confidence_score <= 0.5 OR geometry IS NOT NULL),

            created_at          TIMESTAMP DEFAULT NOW(),
            updated_at          TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX idx_transfers_geom ON area_transfers USING GIST (geometry);
        CREATE INDEX idx_transfers_event ON area_transfers (split_event_id);
    """)

    # Recreate split_enrichment correctly
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS split_enrichment (
            id                  SERIAL PRIMARY KEY,
            transfer_id         INTEGER NOT NULL REFERENCES area_transfers(id) ON DELETE CASCADE,
            dataset_name        TEXT NOT NULL,    
            metric_name         TEXT NOT NULL,    
            apportioned_value   DOUBLE PRECISION NOT NULL,  
            provenance_method   TEXT NOT NULL,    
            
            created_at          TIMESTAMP DEFAULT NOW(),
            UNIQUE(transfer_id, dataset_name, metric_name)
        );
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS split_event_packets (
            event_id         TEXT PRIMARY KEY,
            split_event_id   INTEGER REFERENCES split_events(id) ON DELETE SET NULL,
            parent_cdk       TEXT NOT NULL,
            parent_name      TEXT,
            child_cdks       TEXT[] NOT NULL,
            child_names      TEXT[] NOT NULL DEFAULT '{}',
            state            TEXT NOT NULL,
            split_year       INTEGER NOT NULL,
            effective_date   DATE,
            event_type       TEXT NOT NULL DEFAULT 'SPLIT',
            source_quality   TEXT NOT NULL DEFAULT 'unknown',
            source_urls      TEXT[] NOT NULL DEFAULT '{}',
            source_text_path TEXT,
            aliases          JSONB NOT NULL DEFAULT '[]'::jsonb,
            geometry_status  TEXT NOT NULL DEFAULT 'unknown',
            weight_status    TEXT NOT NULL DEFAULT 'none',
            readiness_tier   TEXT NOT NULL DEFAULT 'Tier C',
            notes            TEXT,
            created_at       TIMESTAMP DEFAULT NOW(),
            updated_at       TIMESTAMP DEFAULT NOW(),
            UNIQUE(parent_cdk, split_year)
        );
        CREATE INDEX IF NOT EXISTS idx_split_event_packets_state ON split_event_packets (state);
        CREATE INDEX IF NOT EXISTS idx_split_event_packets_tier ON split_event_packets (readiness_tier);
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS split_event_sources (
            id           SERIAL PRIMARY KEY,
            event_id     TEXT NOT NULL REFERENCES split_event_packets(event_id) ON DELETE CASCADE,
            source_url   TEXT NOT NULL,
            source_label TEXT,
            source_type  TEXT,
            is_primary   BOOLEAN NOT NULL DEFAULT FALSE,
            created_at   TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_split_event_sources_event ON split_event_sources (event_id);
    """)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS split_event_weights (
            id                SERIAL PRIMARY KEY,
            event_id          TEXT NOT NULL REFERENCES split_event_packets(event_id) ON DELETE CASCADE,
            child_cdk         TEXT NOT NULL,
            child_name        TEXT,
            metric_basis      TEXT NOT NULL,
            weight_value      DOUBLE PRECISION NOT NULL CHECK (weight_value >= 0.0 AND weight_value <= 1.0),
            weight_method     TEXT NOT NULL,
            weight_confidence FLOAT NOT NULL DEFAULT 0.0 CHECK (weight_confidence >= 0.0 AND weight_confidence <= 1.0),
            source_year       INTEGER,
            basis             TEXT NOT NULL,
            is_fallback       BOOLEAN NOT NULL DEFAULT FALSE,
            created_at        TIMESTAMP DEFAULT NOW(),
            UNIQUE(event_id, child_cdk, metric_basis)
        );
        CREATE INDEX IF NOT EXISTS idx_split_event_weights_event ON split_event_weights (event_id);
    """)
    
    print("Dropped old tables and successfully recreated split analyzer and disaggregation schema.")
    await conn.close()
    
asyncio.run(main())
