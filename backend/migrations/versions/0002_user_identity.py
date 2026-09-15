"""Add departments and user identities.

Revision ID: 0002_user_identity
Revises: 0001_enable_vector
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_user_identity"
down_revision: str | Sequence[str] | None = "0001_enable_vector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = postgresql.ENUM("employee", "it", "admin", name="user_role", create_type=False)


def upgrade() -> None:
    user_role.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "departments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_departments"),
        sa.UniqueConstraint("key", name="uq_departments_key"),
        sa.UniqueConstraint("name", name="uq_departments_name"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "memory_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("memory_epoch", sa.Integer(), server_default="0", nullable=False),
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
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name="fk_users_department_id_departments",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_department_id", "users", ["department_id"])


def downgrade() -> None:
    op.drop_index("ix_users_department_id", table_name="users")
    op.drop_table("users")
    op.drop_table("departments")
    user_role.drop(op.get_bind(), checkfirst=True)
