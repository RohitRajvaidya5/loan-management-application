"""Document requirements, review history and immutable replacement revisions.

Revision ID: b52f0a37d914
Revises: a41e9b26c803
"""

import sqlalchemy as sa

from alembic import op

revision = "b52f0a37d914"
down_revision = "a41e9b26c803"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "loan_types",
        sa.Column(
            "document_requirements_configured",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    for column in (
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("document_group_id", sa.Uuid(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("replaces_document_id", sa.Uuid(), nullable=True),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", sa.Uuid(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_remarks", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
    ):
        op.add_column("documents", column)
    op.execute("UPDATE documents SET document_group_id = id")
    op.alter_column("documents", "document_group_id", nullable=False)
    op.create_index(
        "ix_documents_document_group_id", "documents", ["document_group_id"]
    )
    op.create_foreign_key(
        "fk_documents_replaces",
        "documents",
        "documents",
        ["replaces_document_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_documents_replaces", "documents", ["replaces_document_id"]
    )
    for column in ("verified_by", "deleted_by"):
        op.create_foreign_key(
            f"fk_documents_{column}", "documents", "users", [column], ["id"]
        )
    op.create_table(
        "document_requirements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "loan_type_id", sa.Uuid(), sa.ForeignKey("loan_types.id"), nullable=False
        ),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("loan_type_id", "document_type"),
    )
    op.create_index(
        "ix_document_requirements_loan_type_id",
        "document_requirements",
        ["loan_type_id"],
    )
    op.create_table(
        "document_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False
        ),
        sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("previous_status", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_document_reviews_document_id", "document_reviews", ["document_id"]
    )


def downgrade() -> None:
    op.drop_table("document_reviews")
    op.drop_table("document_requirements")
    for column in ("verified_by", "deleted_by"):
        op.drop_constraint(f"fk_documents_{column}", "documents", type_="foreignkey")
    op.drop_constraint("uq_documents_replaces", "documents", type_="unique")
    op.drop_constraint("fk_documents_replaces", "documents", type_="foreignkey")
    op.drop_index("ix_documents_document_group_id", table_name="documents")
    for column in (
        "deleted_by",
        "deleted_at",
        "review_remarks",
        "verified_at",
        "verified_by",
        "replaced_at",
        "replaces_document_id",
        "revision",
        "document_group_id",
        "version",
        "status",
    ):
        op.drop_column("documents", column)
    op.drop_column("loan_types", "document_requirements_configured")
