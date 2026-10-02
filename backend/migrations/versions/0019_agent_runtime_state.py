"""Persist resumable OpenAI Agents SDK run state.

Revision ID: 0019_agent_runtime_state
Revises: 0018_always_on_memory
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_agent_runtime_state"
down_revision: str | None = "0018_always_on_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runtime_states",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("runtime", sa.String(length=40), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("serialized_state", sa.Text(), nullable=True),
        sa.Column("approval_call_id", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="paused", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('paused', 'active', 'completed')",
            name="agent_runtime_state_status_allowlist",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id"),
    )


def downgrade() -> None:
    op.drop_table("agent_runtime_states")
