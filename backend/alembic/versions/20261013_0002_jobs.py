"""Job table for the in-process runner.

Revision ID: 0002_jobs
Revises: 0001_initial
Create Date: 2026-10-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_jobs"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Float(), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_json", sa.JSON(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("analysis_id", sa.String(length=36), nullable=True),
        sa.Column("structure_id", sa.String(length=36), nullable=True),
    )
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_created_at", table_name="jobs")
    op.drop_table("jobs")
