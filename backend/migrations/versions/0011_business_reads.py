"""Add simulated service state and ticket read models.

Revision ID: 0011_business_reads
Revises: 0010_message_citations
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_business_reads"
down_revision: str | Sequence[str] | None = "0010_message_citations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_states",
        sa.Column("service_id", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("fault_mode", sa.String(length=20), server_default="none", nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("service_id IN ('vpn', 'registry', 'gitlab')", name="ck_service_states_service_id_allowlist"),
        sa.CheckConstraint("status IN ('healthy', 'degraded', 'down', 'unknown')", name="ck_service_states_service_status_allowlist"),
        sa.CheckConstraint("fault_mode IN ('none', 'timeout', 'error')", name="ck_service_states_service_fault_allowlist"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("service_id"),
    )
    op.create_index("ix_service_states_updated_by", "service_states", ["updated_by"])
    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_key", sa.String(length=30), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("approval_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=20), server_default="seed", nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("issue_type", sa.String(length=20), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("issue_type IN ('vpn', 'docker', 'gitlab', 'other')", name="ck_tickets_ticket_issue_type_allowlist"),
        sa.CheckConstraint("severity IN ('low', 'normal', 'high')", name="ck_tickets_ticket_severity_allowlist"),
        sa.CheckConstraint("status IN ('open', 'in_progress', 'resolved')", name="ck_tickets_ticket_status_allowlist"),
        sa.CheckConstraint("status != 'resolved' OR resolution_note IS NOT NULL", name="ck_tickets_resolved_ticket_has_note"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("approval_id"),
        sa.UniqueConstraint("display_key"),
    )
    op.create_index("ix_tickets_owner_status_created", "tickets", ["owner_id", "status", "created_at"])
    op.create_index("ix_tickets_department_status_updated", "tickets", ["department_id", "status", "updated_at"])
    op.create_table(
        "ticket_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("type", sa.String(length=60), nullable=False),
        sa.Column("safe_payload", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_events_ticket_id", "ticket_events", ["ticket_id"])


def downgrade() -> None:
    op.drop_table("ticket_events")
    op.drop_table("tickets")
    op.drop_table("service_states")
