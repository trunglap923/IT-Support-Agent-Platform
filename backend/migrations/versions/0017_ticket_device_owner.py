"""Require ticket devices to belong to the ticket owner.

Revision ID: 0017_ticket_device_owner
Revises: 0016_message_feedback
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017_ticket_device_owner"
down_revision: str | None = "0016_message_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_tickets_device_id", "tickets", ["device_id"])
    op.create_foreign_key(
        "fk_tickets_device_owner",
        "tickets",
        "user_devices",
        ["device_id", "owner_id"],
        ["id", "owner_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_tickets_device_owner", "tickets", type_="foreignkey")
    op.drop_index("ix_tickets_device_id", table_name="tickets")
