"""add format-aware asset extraction fields

Revision ID: a491c78d3e12
Revises: efe024a2094e
Create Date: 2026-07-10 14:10:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a491c78d3e12"
down_revision: str | Sequence[str] | None = "efe024a2094e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "assets",
        sa.Column("extractor_name", sa.String(length=80), server_default="generic", nullable=False),
    )
    op.add_column(
        "assets",
        sa.Column(
            "extraction_status",
            sa.String(length=32),
            server_default="metadata_only",
            nullable=False,
        ),
    )
    op.add_column(
        "assets",
        sa.Column(
            "extracted_metadata",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
    )
    op.add_column("assets", sa.Column("extracted_text", sa.Text(), nullable=True))
    op.add_column(
        "assets",
        sa.Column("semantic_eligible", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("assets", sa.Column("extraction_error", sa.Text(), nullable=True))
    op.create_index(
        op.f("ix_assets_extraction_status"), "assets", ["extraction_status"], unique=False
    )
    op.create_index(
        op.f("ix_assets_semantic_eligible"), "assets", ["semantic_eligible"], unique=False
    )
    op.alter_column("assets", "extractor_name", server_default=None)
    op.alter_column("assets", "extraction_status", server_default=None)
    op.alter_column("assets", "extracted_metadata", server_default=None)
    op.alter_column("assets", "semantic_eligible", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_assets_semantic_eligible"), table_name="assets")
    op.drop_index(op.f("ix_assets_extraction_status"), table_name="assets")
    op.drop_column("assets", "extraction_error")
    op.drop_column("assets", "semantic_eligible")
    op.drop_column("assets", "extracted_text")
    op.drop_column("assets", "extracted_metadata")
    op.drop_column("assets", "extraction_status")
    op.drop_column("assets", "extractor_name")
