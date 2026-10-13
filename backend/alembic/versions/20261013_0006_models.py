"""Model registry rows. Weight files are not stored in SQLite.

Revision ID: 0006_models
Revises: 0005_safety
Create Date: 2026-10-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_models"
down_revision: str | None = "0005_safety"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "registered_models",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("task", sa.String(length=200), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("licence", sa.String(), nullable=False),
        sa.Column("dependencies_json", sa.JSON(), nullable=False),
        sa.Column("hardware_json", sa.JSON(), nullable=False),
        sa.Column("input_format", sa.String(), nullable=False),
        sa.Column("output_format", sa.String(), nullable=False),
        sa.Column("benchmark_json", sa.JSON(), nullable=True),
        sa.Column("known_limitations", sa.String(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("weights_relative", sa.String(), nullable=True),
        sa.Column("loader_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_registered_models_name_version"),
    )


def downgrade() -> None:
    op.drop_table("registered_models")
