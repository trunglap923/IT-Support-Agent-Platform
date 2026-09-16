"""Add owned device scopes for confirmed memory.

Revision ID: 0015_memory_devices
Revises: 0014_consent_memory
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_memory_devices"
down_revision: str | None = "0014_consent_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("platform IN ('windows', 'macos', 'linux', 'other')", name="user_device_platform_allowlist"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "owner_id", name="uq_user_devices_id_owner"),
        sa.UniqueConstraint("owner_id", "label", name="uq_user_devices_owner_label"),
    )
    op.create_index("ix_user_devices_owner_id", "user_devices", ["owner_id"])

    op.add_column("conversations", sa.Column("device_id", sa.Uuid(), nullable=True))
    op.create_index("ix_conversations_device_id", "conversations", ["device_id"])
    op.create_foreign_key(
        "fk_conversations_device_owner",
        "conversations",
        "user_devices",
        ["device_id", "owner_id"],
        ["id", "owner_id"],
        ondelete="RESTRICT",
    )

    op.add_column("memory_candidates", sa.Column("device_id", sa.Uuid(), nullable=True))
    op.create_index("ix_memory_candidates_device_id", "memory_candidates", ["device_id"])
    op.create_foreign_key(
        "fk_memory_candidates_device_owner",
        "memory_candidates",
        "user_devices",
        ["device_id", "owner_id"],
        ["id", "owner_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_memory_facts_device_owner",
        "memory_facts",
        "user_devices",
        ["device_id", "owner_id"],
        ["id", "owner_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_memory_facts_device_owner", "memory_facts", type_="foreignkey")
    op.drop_constraint("fk_memory_candidates_device_owner", "memory_candidates", type_="foreignkey")
    op.drop_index("ix_memory_candidates_device_id", table_name="memory_candidates")
    op.drop_column("memory_candidates", "device_id")
    op.drop_constraint("fk_conversations_device_owner", "conversations", type_="foreignkey")
    op.drop_index("ix_conversations_device_id", table_name="conversations")
    op.drop_column("conversations", "device_id")
    op.drop_index("ix_user_devices_owner_id", table_name="user_devices")
    op.drop_table("user_devices")
