"""Add application reference sequence and optimistic concurrency version.

Revision ID: a41e9b26c803
Revises: 0cca17cb8963
"""

import sqlalchemy as sa

from alembic import op

revision = "a41e9b26c803"
down_revision = "0cca17cb8963"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "loan_applications",
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.execute("CREATE SEQUENCE loan_application_reference_seq NO CYCLE")
    op.execute(
        """
        SELECT setval(
            'loan_application_reference_seq',
            GREATEST(COALESCE((
                SELECT MAX(split_part(application_number, '-', 3)::bigint)
                FROM loan_applications
                WHERE application_number ~ '^LN-[0-9]{4}-[0-9]{1,19}$'
            ), 0), 1),
            EXISTS (
                SELECT 1 FROM loan_applications
                WHERE application_number ~ '^LN-[0-9]{4}-[0-9]{1,19}$'
                  AND split_part(application_number, '-', 3)::bigint > 0
            )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP SEQUENCE loan_application_reference_seq")
    op.drop_column("loan_applications", "version")
