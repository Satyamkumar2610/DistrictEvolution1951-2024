"""003 — district_metrics table with provenance tracking

Revision ID: 003
Revises: 002
Create Date: 2026-04-13
"""
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE district_metrics (
            id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            unit_id                UUID NOT NULL REFERENCES admin_units(id),
            year                   SMALLINT NOT NULL,
            metric                 TEXT NOT NULL,
            value                  FLOAT NOT NULL,
            is_harmonized          BOOLEAN NOT NULL DEFAULT FALSE,
            provenance_path        UUID[] NOT NULL DEFAULT '{}',
            cumulative_confidence  FLOAT NOT NULL DEFAULT 1.0
        );
    """)
    op.execute("""
        CREATE UNIQUE INDEX district_metrics_lookup
            ON district_metrics(unit_id, metric, year);
    """)
    op.execute("""
        CREATE INDEX district_metrics_metric_year
            ON district_metrics(metric, year);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS district_metrics CASCADE;")
