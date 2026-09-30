"""Make confirmed memory always active.

Revision ID: 0018_always_on_memory
Revises: 0017_ticket_device_owner
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_always_on_memory"
down_revision: str | None = "0017_ticket_device_owner"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE users SET memory_enabled = true WHERE memory_enabled = false"))
    op.alter_column("users", "memory_enabled", server_default=sa.text("true"))


def downgrade() -> None:
    op.alter_column("users", "memory_enabled", server_default=sa.text("false"))
