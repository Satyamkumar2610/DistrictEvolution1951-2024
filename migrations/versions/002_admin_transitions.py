"""002 — admin_transitions table with typed edges

Revision ID: 002
Revises: 001
Create Date: 2026-04-13
"""
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TYPE transition_type AS ENUM (
            'SPLIT', 'MERGE', 'RENAME', 'BOUNDARY_ADJUST'
        );
    """)
    op.execute("""
        CREATE TABLE admin_transitions (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            from_unit_id     UUID NOT NULL REFERENCES admin_units(id),
            to_unit_id       UUID NOT NULL REFERENCES admin_units(id),
            transition_type  transition_type NOT NULL,
            effective_date   DATE NOT NULL,
            area_weight      FLOAT NOT NULL CHECK (area_weight > 0 AND area_weight <= 1),
            confidence       FLOAT NOT NULL DEFAULT 1.0
                             CHECK (confidence > 0 AND confidence <= 1)
        );
    """)
    # For a clean SPLIT, all to_unit rows from the same from_unit
    # must have area_weights summing to 1.0. Enforce in application layer.
    op.execute(
        "CREATE INDEX admin_transitions_from_idx ON admin_transitions(from_unit_id);"
    )
    op.execute(
        "CREATE INDEX admin_transitions_to_idx ON admin_transitions(to_unit_id);"
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS admin_transitions CASCADE;")
    op.execute("DROP TYPE IF EXISTS transition_type;")
