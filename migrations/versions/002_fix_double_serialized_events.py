"""Fix double-serialized agent_turns.events and artifacts JSONB columns.

Some rows were stored as JSON strings (e.g. '"[{...}]"') instead of
JSON arrays ([{...}]) due to json.dumps() being called before psycopg2
insertion into a JSONB column, causing double-serialization.

This migration unwraps those string-typed JSONB values back to proper arrays.

Revision ID: 002
Revises: 001
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE agent_turns
        SET events = events::text::jsonb
        WHERE jsonb_typeof(events) = 'string'
        """
    )
    op.execute(
        """
        UPDATE agent_turns
        SET artifacts = artifacts::text::jsonb
        WHERE jsonb_typeof(artifacts) = 'string'
        """
    )


def downgrade() -> None:
    pass
