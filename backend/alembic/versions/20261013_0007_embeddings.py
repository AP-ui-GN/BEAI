"""Sequence embeddings and a token limit on registry rows.

Revision ID: 0007_embeddings
Revises: 0006_models
Create Date: 2026-10-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_embeddings"
down_revision: str | None = "0006_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("registered_models", sa.Column("token_limit", sa.Integer(), nullable=True))
    op.create_table(
        "sequence_embeddings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("sequence_id", sa.String(length=36), sa.ForeignKey("sequences.id"), nullable=False),
        sa.Column("model_id", sa.String(length=36), sa.ForeignKey("registered_models.id"), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("input_sha256", sa.String(length=64), nullable=False),
        sa.Column("vector_json", sa.JSON(), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("sequence_id", "model_id", name="uq_sequence_embeddings_sequence_model"),
    )


def downgrade() -> None:
    op.drop_table("sequence_embeddings")
    op.drop_column("registered_models", "token_limit")
