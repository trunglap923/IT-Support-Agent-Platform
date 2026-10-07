"""Add durable working-memory snapshots, events and tool observations.

Revision ID: 0021_durable_working_memory
Revises: 0020_hierarchical_sections
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_durable_working_memory"
down_revision: str | None = "0020_hierarchical_sections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "working_memory_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=True),
        sa.Column("incident_key", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=24), server_default="active", nullable=False),
        sa.Column(
            "schema_version",
            sa.String(length=40),
            server_default="working-memory-v1",
            nullable=False,
        ),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("event_sequence", sa.Integer(), server_default="1", nullable=False),
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
            "status IN ('active', 'waiting_input', 'waiting_approval', 'verifying', "
            "'completed', 'failed', 'cancelled')",
            name="working_memory_status_allowlist",
        ),
        sa.CheckConstraint("version >= 1", name="working_memory_version_positive"),
        sa.CheckConstraint("event_sequence >= 1", name="working_memory_event_sequence_positive"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index(
        "ix_working_memory_snapshots_tenant_id", "working_memory_snapshots", ["tenant_id"]
    )
    op.create_index("ix_working_memory_snapshots_run_id", "working_memory_snapshots", ["run_id"])
    op.create_index(
        "ix_working_memory_snapshots_conversation_id",
        "working_memory_snapshots",
        ["conversation_id"],
    )
    op.create_index(
        "ix_working_memory_snapshots_owner_id", "working_memory_snapshots", ["owner_id"]
    )
    op.create_index(
        "ix_working_memory_snapshots_ticket_id", "working_memory_snapshots", ["ticket_id"]
    )
    op.create_index(
        "ix_working_memory_snapshots_incident_key",
        "working_memory_snapshots",
        ["incident_key"],
    )
    op.create_index(
        "ix_working_memory_owner_status",
        "working_memory_snapshots",
        ["owner_id", "status"],
    )

    op.create_table(
        "working_memory_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("working_memory_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("operation_id", sa.String(length=180), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=True),
        sa.Column("to_status", sa.String(length=24), nullable=False),
        sa.Column("snapshot_version", sa.Integer(), nullable=False),
        sa.Column(
            "safe_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("sequence >= 1", name="working_memory_event_sequence_positive"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["working_memory_id"], ["working_memory_snapshots.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "working_memory_id", "operation_id", name="uq_working_memory_events_operation"
        ),
        sa.UniqueConstraint(
            "working_memory_id", "sequence", name="uq_working_memory_events_sequence"
        ),
    )
    op.create_index(
        "ix_working_memory_events_working_memory_id",
        "working_memory_events",
        ["working_memory_id"],
    )
    op.create_index("ix_working_memory_events_run_id", "working_memory_events", ["run_id"])
    op.create_index(
        "ix_working_memory_events_run_created",
        "working_memory_events",
        ["run_id", "created_at"],
    )

    op.create_table(
        "tool_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("working_memory_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("call_id", sa.String(length=160), nullable=False),
        sa.Column("tool_name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("summary", sa.String(length=1000), nullable=False),
        sa.Column("arguments_hash", sa.String(length=64), nullable=False),
        sa.Column("result_hash", sa.String(length=64), nullable=False),
        sa.Column("artifact_ref", sa.String(length=500), nullable=True),
        sa.Column("receipt_ref", sa.String(length=500), nullable=True),
        sa.Column(
            "safe_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "schema_version",
            sa.String(length=40),
            server_default="tool-observation-v1",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('success', 'failed', 'unknown')",
            name="tool_observation_status_allowlist",
        ),
        sa.CheckConstraint("length(arguments_hash) = 64", name="tool_observation_args_hash_length"),
        sa.CheckConstraint("length(result_hash) = 64", name="tool_observation_result_hash_length"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["working_memory_id"], ["working_memory_snapshots.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "call_id", name="uq_tool_observations_run_call"),
    )
    op.create_index(
        "ix_tool_observations_working_memory_id",
        "tool_observations",
        ["working_memory_id"],
    )
    op.create_index("ix_tool_observations_run_id", "tool_observations", ["run_id"])
    op.create_index("ix_tool_observations_owner_id", "tool_observations", ["owner_id"])
    op.create_index(
        "ix_tool_observations_owner_created",
        "tool_observations",
        ["owner_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("tool_observations")
    op.drop_table("working_memory_events")
    op.drop_table("working_memory_snapshots")
