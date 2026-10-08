"""Add procedure audience scope and stored validation report.

Revision ID: 0025_procedure_scope_validation
Revises: 0024_procedural_memory
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025_procedure_scope_validation"
down_revision: str | None = "0024_procedural_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns("procedure_versions")}
    if "visibility" not in columns:
        op.add_column(
            "procedure_versions",
            sa.Column("visibility", sa.String(20), server_default="it_only", nullable=False),
        )
    if "department_id" not in columns:
        op.add_column(
            "procedure_versions", sa.Column("department_id", sa.Uuid(), nullable=True)
        )
    if "validation_report" not in columns:
        op.add_column(
            "procedure_versions",
            sa.Column(
                "validation_report",
                postgresql.JSONB(),
                server_default=sa.text("'{}'::jsonb"),
                nullable=False,
            ),
        )

    check_rows = inspector.get_check_constraints("procedure_versions")
    has_visibility_check = any(
        "visibility" in str(item.get("sqltext", "")).casefold()
        and "company" in str(item.get("sqltext", "")).casefold()
        for item in check_rows
    )
    if not has_visibility_check:
        op.create_check_constraint(
            "procedure_version_visibility_allowlist",
            "procedure_versions",
            "visibility IN ('company','department','it_only')",
        )
    has_department_check = any(
        "department_id is not null" in str(item.get("sqltext", "")).casefold()
        for item in check_rows
    )
    if not has_department_check:
        op.create_check_constraint(
            "procedure_version_department_scope_matches",
            "procedure_versions",
            "(visibility = 'department') = (department_id IS NOT NULL)",
        )
    foreign_keys = inspector.get_foreign_keys("procedure_versions")
    if not any(item["constrained_columns"] == ["department_id"] for item in foreign_keys):
        op.create_foreign_key(
            "fk_procedure_versions_department",
            "procedure_versions",
            "departments",
            ["department_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    indexes = {item["name"] for item in inspector.get_indexes("procedure_versions")}
    if "ix_procedure_versions_department_id" not in indexes:
        op.create_index(
            "ix_procedure_versions_department_id", "procedure_versions", ["department_id"]
        )


def downgrade() -> None:
    op.drop_index("ix_procedure_versions_department_id", table_name="procedure_versions")
    op.drop_constraint("fk_procedure_versions_department", "procedure_versions", type_="foreignkey")
    op.drop_constraint(
        "procedure_version_department_scope_matches",
        "procedure_versions",
        type_="check",
    )
    op.drop_constraint(
        "procedure_version_visibility_allowlist", "procedure_versions", type_="check"
    )
    op.drop_column("procedure_versions", "validation_report")
    op.drop_column("procedure_versions", "department_id")
    op.drop_column("procedure_versions", "visibility")
