"""Audit request metadata and server-side token invalidation.

Revision ID: c63a1b48e025
Revises: b52f0a37d914
"""

import sqlalchemy as sa

from alembic import op

revision = "c63a1b48e025"
down_revision = "b52f0a37d914"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("deletion_remarks", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("audit_logs", sa.Column("user_agent", sa.String(512), nullable=True))
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_table(
        "revoked_tokens",
        sa.Column("token_digest", sa.String(64), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_revoked_tokens_expires_at", "revoked_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_column("documents", "deletion_remarks")
    op.drop_table("revoked_tokens")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_column("audit_logs", "user_agent")
    op.drop_column("users", "token_version")
