"""004 — disaggregation packet, source, and weight tables

Revision ID: 004
Revises: 003
Create Date: 2026-04-20
"""

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
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
            created_at       TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(parent_cdk, split_year)
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS split_event_sources (
            id           SERIAL PRIMARY KEY,
            event_id     TEXT NOT NULL REFERENCES split_event_packets(event_id) ON DELETE CASCADE,
            source_url   TEXT NOT NULL,
            source_label TEXT,
            source_type  TEXT,
            is_primary   BOOLEAN NOT NULL DEFAULT FALSE,
            created_at   TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS split_event_weights (
            id                SERIAL PRIMARY KEY,
            event_id          TEXT NOT NULL REFERENCES split_event_packets(event_id) ON DELETE CASCADE,
            child_cdk         TEXT NOT NULL,
            child_name        TEXT,
            metric_basis      TEXT NOT NULL,
            weight_value      DOUBLE PRECISION NOT NULL CHECK (weight_value >= 0.0 AND weight_value <= 1.0),
            weight_method     TEXT NOT NULL,
            weight_confidence DOUBLE PRECISION NOT NULL CHECK (weight_confidence >= 0.0 AND weight_confidence <= 1.0),
            source_year       INTEGER,
            basis             TEXT NOT NULL,
            is_fallback       BOOLEAN NOT NULL DEFAULT FALSE,
            created_at        TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(event_id, child_cdk, metric_basis)
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_split_event_packets_state ON split_event_packets(state);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_split_event_packets_tier ON split_event_packets(readiness_tier);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_split_event_weights_event ON split_event_weights(event_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_split_event_sources_event ON split_event_sources(event_id);")


def downgrade():
    op.execute("DROP TABLE IF EXISTS split_event_weights CASCADE;")
    op.execute("DROP TABLE IF EXISTS split_event_sources CASCADE;")
    op.execute("DROP TABLE IF EXISTS split_event_packets CASCADE;")
