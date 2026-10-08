"""Track the embedding space used by durable memory vectors.

Revision ID: 0026_memory_embedding_identity
Revises: 0025_procedure_scope_validation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_memory_embedding_identity"
down_revision: str | None = "0025_procedure_scope_validation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("memory_assertions", "incident_episodes", "procedure_versions")


def upgrade() -> None:
    for table in _TABLES:
        columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}
        if "embedding_model" not in columns:
            op.add_column(table, sa.Column("embedding_model", sa.String(120), nullable=True))
        if "embedding_dimensions" not in columns:
            op.add_column(table, sa.Column("embedding_dimensions", sa.Integer(), nullable=True))
        # Vectors written before this migration have no model identity and cannot be compared
        # safely with a newly configured query embedding space.
        op.execute(
            sa.text(
                f"UPDATE {table} SET embedding = NULL "
                "WHERE embedding IS NOT NULL AND embedding_model IS NULL"
            )
        )
        constraints = {
            item["name"] for item in sa.inspect(op.get_bind()).get_check_constraints(table)
        }
        name = f"{table}_embedding_identity_complete"
        if name not in constraints:
            op.create_check_constraint(
                name,
                table,
                "(embedding IS NULL AND embedding_model IS NULL AND embedding_dimensions IS NULL) "
                "OR (embedding IS NOT NULL AND embedding_model IS NOT NULL "
                "AND embedding_dimensions = 1536)",
            )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_constraint(f"{table}_embedding_identity_complete", table, type_="check")
        op.drop_column(table, "embedding_dimensions")
        op.drop_column(table, "embedding_model")
