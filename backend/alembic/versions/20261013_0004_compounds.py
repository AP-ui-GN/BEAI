"""Compound table and optional analysis link.

Revision ID: 0004_compounds
Revises: 0003_sequences
Create Date: 2026-10-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_compounds"
down_revision: str | None = "0003_sequences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "compounds",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("input_smiles", sa.String(), nullable=False),
        sa.Column("canonical_smiles", sa.String(), nullable=False),
        sa.Column("inchikey", sa.String(length=27), nullable=False),
        sa.Column("source_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_compounds_inchikey", "compounds", ["inchikey"], unique=True)
    with op.batch_alter_table("analyses") as batch:
        batch.add_column(sa.Column("compound_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_analyses_compound_id", "compounds", ["compound_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("analyses") as batch:
        batch.drop_constraint("fk_analyses_compound_id", type_="foreignkey")
        batch.drop_column("compound_id")
    op.drop_index("ix_compounds_inchikey", table_name="compounds")
    op.drop_table("compounds")
