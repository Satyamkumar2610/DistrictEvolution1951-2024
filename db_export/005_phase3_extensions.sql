-- Migration 005: Phase 3 — Add source_notes to split_events
-- Apply: psql -f db_export/005_phase3_extensions.sql

-- Add source_notes column for lineage batch import provenance
ALTER TABLE split_events
ADD COLUMN IF NOT EXISTS source_notes TEXT;

-- Add composite index for quality queries
CREATE INDEX IF NOT EXISTS idx_split_events_status
ON split_events (geometry_status);

CREATE INDEX IF NOT EXISTS idx_split_events_confidence
ON split_events (composite_confidence);

-- Ensure enrichment table has a composite index for analytics
CREATE INDEX IF NOT EXISTS idx_enrichment_dataset
ON split_enrichment (dataset_name, metric_name);
