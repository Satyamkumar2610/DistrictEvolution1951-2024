-- Phase 1a: District Split Area Transfer Schema
-- Core tables for longitudinal district geometries and high-precision split mapping

-- -----------------------------------------------------------------------------
-- ENUMs
-- -----------------------------------------------------------------------------

CREATE TYPE geometry_source_type AS ENUM (
    'shrug_union',      -- ST_Union of SHRUG village polygons (confidence: 0.9)
    'bhuvan_wfs',       -- Fetched from ISRO Bhuvan OGC WFS (confidence: 0.95)
    'datameet',         -- Community-curated GeoJSON from Datameet/GADM (confidence: 0.8)
    'gadm',             -- GADM global admin boundaries (confidence: 0.8)
    'manual_upload',    -- User-uploaded GeoJSON via API (confidence: 0.7)
    'inferred',         -- Computed via ST_Difference from known siblings (confidence: 0.6)
    'unknown'           -- No polygon available (confidence: 0.0)
);

CREATE TYPE geometry_status_type AS ENUM (
    'complete',   -- All parent + child geometries are known
    'partial',    -- Some geometries are known, some inferred or unknown
    'unknown'     -- No geometries available for this event
);

CREATE TYPE transfer_type AS ENUM (
    'inherited',         -- Area cleanly inherited from parent
    'transferred_in',    -- Area acquired from a neighboring district
    'transferred_out',   -- Area that left the parent''s successor
    'overlap',           -- Overlapping area between children (digitization error)
    'gap'                -- Area in parent not covered by any child
);


-- -----------------------------------------------------------------------------
-- Table: district_snapshots
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS district_snapshots (
    id                  SERIAL PRIMARY KEY,
    district_cdk        TEXT NOT NULL REFERENCES districts(cdk) ON DELETE CASCADE,
    snapshot_year       INTEGER NOT NULL,
    district_name       TEXT NOT NULL,
    geometry            GEOMETRY(MultiPolygon, 4326),     -- Nullable for unknowns
    area_sqkm           DOUBLE PRECISION,                 

    geometry_source     geometry_source_type NOT NULL DEFAULT 'unknown',
    geometry_confidence FLOAT NOT NULL DEFAULT 0.0
        CHECK (geometry_confidence >= 0.0 AND geometry_confidence <= 1.0),
    source_url          TEXT,  -- Provenance link

    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),

    UNIQUE(district_cdk, snapshot_year)
);

CREATE INDEX idx_snapshots_geom ON district_snapshots USING GIST (geometry);
CREATE INDEX idx_snapshots_cdk ON district_snapshots (district_cdk);
CREATE INDEX idx_snapshots_year ON district_snapshots (snapshot_year);


-- -----------------------------------------------------------------------------
-- Table: split_events
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS split_events (
    id                      SERIAL PRIMARY KEY,
    parent_cdk              TEXT NOT NULL,
    child_cdks              TEXT[] NOT NULL,
    split_year              INTEGER NOT NULL,
    
    event_type              TEXT DEFAULT 'SPLIT',
    geometry_status         geometry_status_type NOT NULL DEFAULT 'unknown',
    source_notes            TEXT,
    
    area_conservation_error DOUBLE PRECISION,  -- Stored formula
    composite_confidence    FLOAT,             -- Stored calculated confidence

    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW(),

    UNIQUE(parent_cdk, split_year)
);

CREATE INDEX idx_split_parent ON split_events (parent_cdk);
CREATE INDEX idx_split_year ON split_events (split_year);


-- -----------------------------------------------------------------------------
-- Table: area_transfers
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS area_transfers (
    id                  SERIAL PRIMARY KEY,
    split_event_id      INTEGER NOT NULL REFERENCES split_events(id) ON DELETE CASCADE,
    source_cdk          TEXT NOT NULL,
    dest_cdk            TEXT NOT NULL,
    transfer_type       transfer_type NOT NULL,
    
    area_sqkm           DOUBLE PRECISION NOT NULL,
    confidence_score    FLOAT NOT NULL DEFAULT 0.0
        CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),

    geometry            GEOMETRY(MultiPolygon, 4326), -- nullable

    CONSTRAINT geometry_required_for_high_confidence
    CHECK (
        confidence_score <= 0.5 OR geometry IS NOT NULL
    ),

    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_transfers_geom ON area_transfers USING GIST (geometry);
CREATE INDEX idx_transfers_event ON area_transfers (split_event_id);


-- -----------------------------------------------------------------------------
-- Table: split_enrichment
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS split_enrichment (
    id                  SERIAL PRIMARY KEY,
    transfer_id         INTEGER NOT NULL REFERENCES area_transfers(id) ON DELETE CASCADE,
    dataset_name        TEXT NOT NULL,
    metric_name         TEXT NOT NULL,
    value               DOUBLE PRECISION NOT NULL,
    metadata            JSONB,

    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),

    UNIQUE(transfer_id, dataset_name, metric_name)
);

CREATE INDEX idx_enrichment_transfer ON split_enrichment (transfer_id);

-- End of File
