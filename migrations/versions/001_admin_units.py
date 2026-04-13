"""001 — admin_units table with PostGIS geometry

Revision ID: 001
Revises: None
Create Date: 2026-04-13
"""
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    op.execute("""
        CREATE TABLE admin_units (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name         TEXT NOT NULL,
            state        TEXT NOT NULL,
            valid_from   DATE NOT NULL,
            valid_to     DATE,
            geometry     GEOMETRY(Polygon, 4326) NOT NULL
        );
    """)
    op.execute(
        "CREATE INDEX admin_units_geom_idx ON admin_units USING GIST(geometry);"
    )
    op.execute(
        "CREATE INDEX admin_units_state_idx ON admin_units(state);"
    )
    op.execute(
        "CREATE INDEX admin_units_valid_idx ON admin_units(valid_from, valid_to);"
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS admin_units CASCADE;")
