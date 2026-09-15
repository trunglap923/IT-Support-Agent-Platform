"""Align run terminal states and add idempotent event keys.

Revision ID: 0005_run_state_events
Revises: 0004_conversation_runs
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_run_state_events"
down_revision: str | Sequence[str] | None = "0004_conversation_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_agent_runs_run_status", "agent_runs", type_="check")
    op.execute("UPDATE agent_runs SET status = 'completed' WHERE status = 'succeeded'")
    op.create_check_constraint(
        "run_status",
        "agent_runs",
        "status IN ('queued', 'running', 'waiting_approval', 'resume_queued', "
        "'completed', 'failed', 'cancelled')",
    )
    op.create_check_constraint(
        "terminal_run_has_finished_at",
        "agent_runs",
        "(status IN ('completed', 'failed', 'cancelled')) = (finished_at IS NOT NULL)",
    )
    op.add_column("run_events", sa.Column("dedupe_key", sa.String(length=120), nullable=True))
    op.create_unique_constraint(
        "uq_run_events_run_dedupe_key",
        "run_events",
        ["run_id", "dedupe_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_run_events_run_dedupe_key", "run_events", type_="unique")
    op.drop_column("run_events", "dedupe_key")
    op.drop_constraint("ck_agent_runs_terminal_run_has_finished_at", "agent_runs", type_="check")
    op.drop_constraint("ck_agent_runs_run_status", "agent_runs", type_="check")
    op.execute("UPDATE agent_runs SET status = 'succeeded' WHERE status = 'completed'")
    op.create_check_constraint(
        "run_status",
        "agent_runs",
        "status IN ('queued', 'running', 'waiting_approval', 'resume_queued', "
        "'succeeded', 'failed', 'cancelled')",
    )
