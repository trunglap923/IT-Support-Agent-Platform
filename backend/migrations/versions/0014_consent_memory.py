"""Add consent-gated memory candidates and facts.

Revision ID: 0014_consent_memory
Revises: 0013_langgraph_checkpoints
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_consent_memory"
down_revision: str | None = "0013_langgraph_checkpoints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_consent_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("epoch >= 0", name="memory_consent_epoch_non_negative"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_consent_events_owner_id", "memory_consent_events", ["owner_id"])
    op.create_table(
        "memory_extraction_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("source_message_id", sa.Uuid(), nullable=False),
        sa.Column("captured_epoch", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("captured_epoch >= 0", name="memory_job_epoch_non_negative"),
        sa.CheckConstraint("status IN ('pending', 'completed', 'discarded', 'failed')", name="memory_job_status_allowlist"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_message_id", name="uq_memory_job_source_message"),
    )
    op.create_index("ix_memory_extraction_jobs_owner_id", "memory_extraction_jobs", ["owner_id"])
    op.create_index("ix_memory_extraction_jobs_run_id", "memory_extraction_jobs", ["run_id"])
    op.create_index("ix_memory_extraction_jobs_source_message_id", "memory_extraction_jobs", ["source_message_id"])
    op.create_table(
        "memory_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("source_conversation_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("value", sa.String(length=240), nullable=False),
        sa.Column("evidence", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('profile', 'preference', 'device')", name="memory_candidate_kind_allowlist"),
        sa.CheckConstraint("status IN ('pending', 'confirmed', 'rejected', 'expired')", name="memory_candidate_status_allowlist"),
        sa.ForeignKeyConstraint(["job_id"], ["memory_extraction_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "kind", "key", name="uq_memory_candidate_job_key"),
    )
    op.create_index("ix_memory_candidates_job_id", "memory_candidates", ["job_id"])
    op.create_index("ix_memory_candidates_owner_id", "memory_candidates", ["owner_id"])
    op.create_index("ix_memory_candidates_source_conversation_id", "memory_candidates", ["source_conversation_id"])
    op.create_index("ix_memory_candidates_expires_at", "memory_candidates", ["expires_at"])
    op.create_table(
        "memory_facts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("source_conversation_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("value", sa.String(length=240), nullable=False),
        sa.Column("scope", sa.String(length=20), server_default="global", nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('profile', 'preference', 'device')", name="memory_fact_kind_allowlist"),
        sa.CheckConstraint("scope IN ('global', 'device')", name="memory_fact_scope_allowlist"),
        sa.CheckConstraint("(scope = 'device') = (device_id IS NOT NULL)", name="memory_fact_device_scope_matches"),
        sa.ForeignKeyConstraint(["candidate_id"], ["memory_candidates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id"),
    )
    op.create_index("ix_memory_facts_owner_id", "memory_facts", ["owner_id"])
    op.create_index("ix_memory_facts_source_conversation_id", "memory_facts", ["source_conversation_id"])
    op.create_index("ix_memory_facts_device_id", "memory_facts", ["device_id"])
    op.create_index("ix_memory_facts_expires_at", "memory_facts", ["expires_at"])
    op.create_index(
        "uq_memory_fact_global_active",
        "memory_facts",
        ["owner_id", "kind", "key"],
        unique=True,
        postgresql_where=sa.text("scope = 'global' AND deleted_at IS NULL"),
    )
    op.create_index(
        "uq_memory_fact_device_active",
        "memory_facts",
        ["owner_id", "device_id", "kind", "key"],
        unique=True,
        postgresql_where=sa.text("scope = 'device' AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("memory_facts")
    op.drop_table("memory_candidates")
    op.drop_table("memory_extraction_jobs")
    op.drop_table("memory_consent_events")
