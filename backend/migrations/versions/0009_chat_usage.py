"""Track output tokens for guarded chat calls.

Revision ID: 0009_chat_usage
Revises: 0008_document_chunks
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_chat_usage"
down_revision: str | Sequence[str] | None = "0008_document_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "usage_ledger",
        sa.Column("reserved_output_tokens", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("usage_ledger", sa.Column("actual_output_tokens", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_usage_ledger_reserved_output_tokens_non_negative",
        "usage_ledger",
        "reserved_output_tokens >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_usage_ledger_reserved_output_tokens_non_negative",
        "usage_ledger",
        type_="check",
    )
    op.drop_column("usage_ledger", "actual_output_tokens")
    op.drop_column("usage_ledger", "reserved_output_tokens")
