"""Add reviewed and versioned procedural memory.

Revision ID: 0024_procedural_memory
Revises: 0023_semantic_episodic_memory
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects import postgresql

revision: str = "0024_procedural_memory"
down_revision: str | None = "0023_semantic_episodic_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    empty_array = sa.text("'[]'::jsonb")
    op.create_table(
        "procedures",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("intent", sa.String(120), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("version >= 1", name="procedure_version_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_procedures_intent", "procedures", ["intent"])
    op.create_index("ix_procedures_current_version_id", "procedures", ["current_version_id"])

    op.create_table(
        "procedure_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("procedure_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="candidate", nullable=False),
        sa.Column("version_range", sa.String(120), nullable=True),
        sa.Column("prerequisites", postgresql.JSONB(), server_default=empty_array, nullable=False),
        sa.Column(
            "prohibited_actions", postgresql.JSONB(), server_default=empty_array, nullable=False
        ),
        sa.Column("evidence_refs", postgresql.JSONB(), server_default=empty_array, nullable=False),
        sa.Column(
            "example_episode_ids", postgresql.JSONB(), server_default=empty_array, nullable=False
        ),
        sa.Column("source_document_version_id", sa.Uuid(), nullable=True),
        sa.Column("compiled_signature", sa.String(200), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("success_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding", VECTOR(1536), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("version_number >= 1", name="procedure_version_number_positive"),
        sa.CheckConstraint(
            "status IN ('candidate','review','approved','deprecated','rejected')",
            name="procedure_version_status_allowlist",
        ),
        sa.CheckConstraint("success_count >= 0", name="procedure_success_count_non_negative"),
        sa.CheckConstraint("failure_count >= 0", name="procedure_failure_count_non_negative"),
        sa.ForeignKeyConstraint(["procedure_id"], ["procedures.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_document_version_id"], ["document_versions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("procedure_id", "version_number", name="uq_procedure_versions_number"),
    )
    for column in (
        "procedure_id",
        "source_document_version_id",
        "approved_by",
        "created_by",
        "compiled_signature",
    ):
        op.create_index(f"ix_procedure_versions_{column}", "procedure_versions", [column])
    op.create_index(
        "ix_procedure_versions_status_effective",
        "procedure_versions",
        ["status", "effective_from", "effective_to"],
    )
    op.create_foreign_key(
        "fk_procedures_current_version",
        "procedures",
        "procedure_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "procedure_applicability",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("procedure_version_id", sa.Uuid(), nullable=False),
        sa.Column("signal_type", sa.String(30), nullable=False),
        sa.Column("signal_value", sa.String(160), nullable=False),
        sa.CheckConstraint(
            "signal_type IN ('service','product','operating_system','error_code','version')",
            name="procedure_applicability_type_allowlist",
        ),
        sa.ForeignKeyConstraint(
            ["procedure_version_id"], ["procedure_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "procedure_version_id",
            "signal_type",
            "signal_value",
            name="uq_procedure_applicability_signal",
        ),
    )
    for column in ("procedure_version_id", "signal_type", "signal_value"):
        op.create_index(f"ix_procedure_applicability_{column}", "procedure_applicability", [column])

    op.create_table(
        "procedure_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("procedure_version_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("step_key", sa.String(80), nullable=False),
        sa.Column("action", sa.String(500), nullable=False),
        sa.Column("tool_name", sa.String(80), nullable=True),
        sa.Column("expected_observation", sa.String(500), nullable=False),
        sa.Column("on_success", sa.String(80), nullable=True),
        sa.Column("on_failure", sa.String(80), nullable=True),
        sa.Column("permission", sa.String(120), nullable=True),
        sa.Column("approval_required", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("verification", sa.String(500), nullable=True),
        sa.CheckConstraint("ordinal >= 0", name="procedure_step_ordinal_non_negative"),
        sa.ForeignKeyConstraint(
            ["procedure_version_id"], ["procedure_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("procedure_version_id", "ordinal", name="uq_procedure_step_ordinal"),
        sa.UniqueConstraint("procedure_version_id", "step_key", name="uq_procedure_step_key"),
    )
    op.create_index(
        "ix_procedure_steps_procedure_version_id", "procedure_steps", ["procedure_version_id"]
    )

    op.create_table(
        "procedure_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("procedure_version_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "decision IN ('approve','reject','request_changes','deprecate')",
            name="procedure_review_decision_allowlist",
        ),
        sa.ForeignKeyConstraint(
            ["procedure_version_id"], ["procedure_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_procedure_reviews_procedure_version_id", "procedure_reviews", ["procedure_version_id"]
    )
    op.create_index("ix_procedure_reviews_reviewer_id", "procedure_reviews", ["reviewer_id"])
    op.create_index(
        "ix_procedure_reviews_version_created",
        "procedure_reviews",
        ["procedure_version_id", "created_at"],
    )

    op.create_table(
        "procedure_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("procedure_version_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(20), server_default="running", nullable=False),
        sa.Column("outcome", sa.String(20), nullable=True),
        sa.Column("verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "matched_signals", postgresql.JSONB(), server_default=empty_array, nullable=False
        ),
        sa.Column(
            "attempted_step_keys", postgresql.JSONB(), server_default=empty_array, nullable=False
        ),
        sa.Column("receipt_refs", postgresql.JSONB(), server_default=empty_array, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running','completed')", name="procedure_execution_status_allowlist"
        ),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('success','failure','abandoned')",
            name="procedure_execution_outcome_allowlist",
        ),
        sa.ForeignKeyConstraint(
            ["procedure_version_id"], ["procedure_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("procedure_version_id", "run_id", name="uq_procedure_execution_run"),
    )
    for column in ("procedure_version_id", "run_id", "owner_id", "ticket_id"):
        op.create_index(f"ix_procedure_executions_{column}", "procedure_executions", [column])
    op.create_index(
        "ix_procedure_executions_version_completed",
        "procedure_executions",
        ["procedure_version_id", "completed_at"],
    )


def downgrade() -> None:
    op.drop_table("procedure_executions")
    op.drop_table("procedure_reviews")
    op.drop_table("procedure_steps")
    op.drop_table("procedure_applicability")
    op.drop_constraint("fk_procedures_current_version", "procedures", type_="foreignkey")
    op.drop_table("procedure_versions")
    op.drop_table("procedures")
