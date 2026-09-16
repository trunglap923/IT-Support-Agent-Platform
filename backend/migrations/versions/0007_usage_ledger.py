"""Add AI usage reservations and cost ledger.

Revision ID: 0007_usage_ledger
Revises: 0006_documents
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_usage_ledger"
down_revision: str | Sequence[str] | None = "0006_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usage_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("price_version", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reserved_input_tokens", sa.Integer(), nullable=False),
        sa.Column("actual_input_tokens", sa.Integer(), nullable=True),
        sa.Column("reserved_cost_usd", sa.Numeric(14, 8), nullable=False),
        sa.Column("actual_cost_usd", sa.Numeric(14, 8), nullable=True),
        sa.Column("provider_request_id", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "reserved_input_tokens > 0", name="ck_usage_ledger_reserved_tokens_positive"
        ),
        sa.CheckConstraint(
            "reserved_cost_usd >= 0", name="ck_usage_ledger_reserved_cost_non_negative"
        ),
        sa.CheckConstraint(
            "actual_cost_usd IS NULL OR actual_cost_usd >= 0",
            name="ck_usage_ledger_actual_cost_non_negative",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operation_id"),
    )
    op.create_index("ix_usage_ledger_kind", "usage_ledger", ["kind"])
    op.create_index("ix_usage_ledger_status", "usage_ledger", ["status"])
    op.create_index("ix_usage_ledger_created_at", "usage_ledger", ["created_at"])


def downgrade() -> None:
    op.drop_table("usage_ledger")
