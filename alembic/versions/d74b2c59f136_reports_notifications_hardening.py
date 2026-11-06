"""Durable notifications and shared login rate limiting.

Revision ID: d74b2c59f136
Revises: c63a1b48e025
"""

import sqlalchemy as sa

from alembic import op

revision = "d74b2c59f136"
down_revision = "c63a1b48e025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey("loan_applications.id"),
            nullable=False,
        ),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False, server_default="EMAIL"),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("template", sa.String(60), nullable=False),
        sa.Column("event_key", sa.String(200), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_reference", sa.String(255), nullable=True),
        sa.Column("last_error", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING','PROCESSING','SENT','FAILED')",
            name="ck_notifications_status",
        ),
        sa.CheckConstraint("channel = 'EMAIL'", name="ck_notifications_channel"),
        sa.CheckConstraint("retry_count >= 0", name="ck_notifications_attempts"),
    )
    for column in ("application_id", "event_type", "created_at"):
        op.create_index(f"ix_notifications_{column}", "notifications", [column])
    op.create_index("ix_notifications_due", "notifications", ["status", "available_at"])
    op.create_table(
        "login_rate_limits",
        sa.Column("peer_digest", sa.String(64), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_login_rate_limits_window_start", "login_rate_limits", ["window_start"]
    )


def downgrade() -> None:
    op.drop_table("login_rate_limits")
    op.drop_table("notifications")
