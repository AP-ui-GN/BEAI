"""Safety lookup rows. Payload is retrieved text, not a generated conclusion.

Revision ID: 0005_safety
Revises: 0004_compounds
Create Date: 2026-10-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_safety"
down_revision: str | None = "0004_compounds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "safety_lookups",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("safety_lookups")
