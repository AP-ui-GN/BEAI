"""Sequence table and optional analysis link.

Revision ID: 0003_sequences
Revises: 0002_jobs
Create Date: 2026-10-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_sequences"
down_revision: str | None = "0002_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sequences",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("header", sa.String(length=500), nullable=False),
        sa.Column("sequence", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_json", sa.JSON(), nullable=True),
        sa.Column("validation_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_sequences_created_at", "sequences", ["created_at"])
    with op.batch_alter_table("analyses") as batch:
        batch.add_column(sa.Column("sequence_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_analyses_sequence_id", "sequences", ["sequence_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("analyses") as batch:
        batch.drop_constraint("fk_analyses_sequence_id", type_="foreignkey")
        batch.drop_column("sequence_id")
    op.drop_index("ix_sequences_created_at", table_name="sequences")
    op.drop_table("sequences")
