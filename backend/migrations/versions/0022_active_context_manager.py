"""Add auditable active-context builds and short-lived summary artifacts.

Revision ID: 0022_active_context_manager
Revises: 0021_durable_working_memory
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_active_context_manager"
down_revision: str | None = "0021_durable_working_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "context_builds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("call_sequence", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=24), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("bundle_hash", sa.String(length=64), nullable=False),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=False),
        sa.Column("input_token_limit", sa.Integer(), nullable=False),
        sa.Column("selected_count", sa.Integer(), nullable=False),
        sa.Column("excluded_count", sa.Integer(), nullable=False),
        sa.Column("conflict_count", sa.Integer(), nullable=False),
        sa.Column(
            "selections",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "conflicts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("call_sequence >= 1", name="context_build_call_sequence_positive"),
        sa.CheckConstraint(
            "purpose IN ('plan', 'tool_selection', 'answer', 'verify', 'memory_decision')",
            name="context_build_purpose_allowlist",
        ),
        sa.CheckConstraint("length(bundle_hash) = 64", name="context_build_hash_length"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "call_sequence", name="uq_context_builds_run_sequence"),
    )
    op.create_index("ix_context_builds_run_id", "context_builds", ["run_id"])
    op.create_index("ix_context_builds_owner_id", "context_builds", ["owner_id"])
    op.create_index("ix_context_builds_expires_at", "context_builds", ["expires_at"])
    op.create_index("ix_context_builds_owner_created", "context_builds", ["owner_id", "created_at"])

    op.create_table(
        "context_summary_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("call_sequence", sa.Integer(), nullable=False),
        sa.Column("artifact_ref", sa.String(length=500), nullable=False),
        sa.Column(
            "source_candidate_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(content_hash) = 64", name="context_summary_hash_length"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "call_sequence",
            "artifact_ref",
            name="uq_context_summary_run_call_ref",
        ),
    )
    op.create_index("ix_context_summary_artifacts_run_id", "context_summary_artifacts", ["run_id"])
    op.create_index(
        "ix_context_summary_artifacts_owner_id", "context_summary_artifacts", ["owner_id"]
    )
    op.create_index(
        "ix_context_summary_artifacts_expires_at", "context_summary_artifacts", ["expires_at"]
    )
    op.create_index(
        "ix_context_summary_owner_expiry",
        "context_summary_artifacts",
        ["owner_id", "expires_at"],
    )


def downgrade() -> None:
    op.drop_table("context_summary_artifacts")
    op.drop_table("context_builds")
