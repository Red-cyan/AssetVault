"""add persistent task queue fields

Revision ID: d83fa2b7c104
Revises: a491c78d3e12
Create Date: 2026-07-10 14:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d83fa2b7c104"
down_revision: str | Sequence[str] | None = "a491c78d3e12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "tasks",
        sa.Column("max_attempts", sa.Integer(), server_default="2", nullable=False),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "available_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.add_column("tasks", sa.Column("heartbeat_at", sa.DateTime(), nullable=True))
    op.add_column("tasks", sa.Column("worker_id", sa.String(length=80), nullable=True))
    op.create_index(op.f("ix_tasks_available_at"), "tasks", ["available_at"], unique=False)
    op.create_index(op.f("ix_tasks_heartbeat_at"), "tasks", ["heartbeat_at"], unique=False)
    op.create_index(op.f("ix_tasks_worker_id"), "tasks", ["worker_id"], unique=False)
    op.alter_column("tasks", "attempts", server_default=None)
    op.alter_column("tasks", "max_attempts", server_default=None)
    op.alter_column("tasks", "available_at", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_tasks_worker_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_heartbeat_at"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_available_at"), table_name="tasks")
    op.drop_column("tasks", "worker_id")
    op.drop_column("tasks", "heartbeat_at")
    op.drop_column("tasks", "available_at")
    op.drop_column("tasks", "max_attempts")
    op.drop_column("tasks", "attempts")
