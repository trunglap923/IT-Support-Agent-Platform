"""Add owner-scoped assistant message feedback.

Revision ID: 0016_message_feedback
Revises: 0015_memory_devices
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_message_feedback"
down_revision: str | None = "0015_memory_devices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "message_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("rating", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=True),
        sa.Column("comment", sa.String(length=500), nullable=True),
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
        sa.CheckConstraint("rating IN ('helpful', 'unhelpful')", name="feedback_rating_allowlist"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "message_id", name="uq_feedback_owner_message"),
    )
    op.create_index("ix_feedback_owner_created", "message_feedback", ["owner_id", "created_at"])
    op.create_index("ix_message_feedback_message_id", "message_feedback", ["message_id"])
    op.create_index("ix_message_feedback_run_id", "message_feedback", ["run_id"])


def downgrade() -> None:
    op.drop_table("message_feedback")
