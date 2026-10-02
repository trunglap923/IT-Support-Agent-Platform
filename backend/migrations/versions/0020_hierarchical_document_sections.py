"""Add hierarchical document sections and leaf provenance.

Revision ID: 0020_hierarchical_sections
Revises: 0019_agent_runtime_state
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_hierarchical_sections"
down_revision: str | None = "0019_agent_runtime_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_sections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=True),
        sa.Column(
            "section_path",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "content_types",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("source_path", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("ordinal >= 0", name="ordinal_non_negative"),
        sa.CheckConstraint("level >= 0 AND level <= 6", name="level_range"),
        sa.CheckConstraint("token_count > 0", name="token_count_positive"),
        sa.ForeignKeyConstraint(["parent_id"], ["document_sections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["version_id"], ["document_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "ordinal", name="uq_document_section_ordinal"),
    )
    op.create_index("ix_document_sections_version_id", "document_sections", ["version_id"])
    op.create_index("ix_document_sections_parent_id", "document_sections", ["parent_id"])

    op.add_column("document_chunks", sa.Column("section_id", sa.Uuid(), nullable=True))
    op.add_column(
        "document_chunks",
        sa.Column("section_chunk_index", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "document_chunks",
        sa.Column(
            "section_path",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE document_chunks SET section_path = jsonb_build_array(section) "
        "WHERE section IS NOT NULL"
    )
    op.create_check_constraint(
        "section_chunk_index_non_negative",
        "document_chunks",
        "section_chunk_index >= 0",
    )
    op.create_foreign_key(
        "fk_document_chunks_section_id",
        "document_chunks",
        "document_sections",
        ["section_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_document_chunks_section_id", "document_chunks", ["section_id"])
    op.execute(
        """
        INSERT INTO document_sections (
            id, version_id, parent_id, ordinal, level, title, section_path,
            content_types, content, token_count, page_number, source_path
        )
        SELECT
            (array_agg(id ORDER BY ordinal))[1],
            version_id,
            NULL,
            min(ordinal),
            CASE WHEN section IS NULL THEN 0 ELSE 1 END,
            section,
            CASE
                WHEN section IS NULL THEN '[]'::jsonb
                ELSE jsonb_build_array(section)
            END,
            '["paragraph"]'::jsonb,
            string_agg(content, E'\n\n' ORDER BY ordinal),
            sum(token_count),
            page_number,
            source_path
        FROM document_chunks
        GROUP BY version_id, section, page_number, source_path
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                chunk.id,
                section.id AS section_id,
                section.section_path,
                row_number() OVER (
                    PARTITION BY chunk.version_id, chunk.section, chunk.page_number,
                                 chunk.source_path
                    ORDER BY chunk.ordinal
                ) - 1 AS section_chunk_index
            FROM document_chunks AS chunk
            JOIN document_sections AS section
              ON section.version_id = chunk.version_id
             AND section.title IS NOT DISTINCT FROM chunk.section
             AND section.page_number IS NOT DISTINCT FROM chunk.page_number
             AND section.source_path = chunk.source_path
        )
        UPDATE document_chunks AS chunk
        SET section_id = ranked.section_id,
            section_path = ranked.section_path,
            section_chunk_index = ranked.section_chunk_index
        FROM ranked
        WHERE chunk.id = ranked.id
        """
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_section_id", table_name="document_chunks")
    op.drop_constraint("fk_document_chunks_section_id", "document_chunks", type_="foreignkey")
    op.drop_constraint(
        "section_chunk_index_non_negative",
        "document_chunks",
        type_="check",
    )
    op.drop_column("document_chunks", "section_path")
    op.drop_column("document_chunks", "section_chunk_index")
    op.drop_column("document_chunks", "section_id")
    op.drop_table("document_sections")
