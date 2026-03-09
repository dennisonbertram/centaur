"""Add api_keys table for multi-key auth with scopes.

Revision ID: 004
Revises: 003
"""

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE api_keys (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name        TEXT NOT NULL,
            key_prefix  TEXT NOT NULL,
            key_hash    TEXT NOT NULL UNIQUE,
            scopes      TEXT[] NOT NULL DEFAULT '{"tools:*"}',
            created_by  TEXT NOT NULL DEFAULT '',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            revoked_at  TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX idx_api_keys_hash ON api_keys (key_hash) WHERE revoked_at IS NULL")
    op.execute("CREATE INDEX idx_api_keys_prefix ON api_keys (key_prefix)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS api_keys CASCADE")
