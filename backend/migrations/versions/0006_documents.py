"""Add document, version, ACL and draft ingestion job persistence.

Revision ID: 0006_documents
Revises: 0005_run_state_events
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_documents"
down_revision: str | Sequence[str] | None = "0005_run_state_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_key", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("visibility", sa.String(length=10), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("archived", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column("access_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "visibility IN ('company', 'department', 'it_only')",
            name="ck_documents_document_visibility",
        ),
        sa.CheckConstraint(
            "(visibility = 'department') = (department_id IS NOT NULL)",
            name="ck_documents_department_scope_matches_visibility",
        ),
        sa.ForeignKeyConstraint(
            ["department_id"], ["departments.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_key"),
    )
    op.create_index("ix_documents_department_id", "documents", ["department_id"])
    op.create_index("ix_documents_current_version_id", "documents", ["current_version_id"])

    op.create_table(
        "document_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version_label", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("authority", sa.String(length=80), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parser_version", sa.String(length=80), nullable=True),
        sa.Column("chunker_version", sa.String(length=80), nullable=True),
        sa.Column("embedding_model", sa.String(length=120), nullable=True),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'processing', 'ready', 'published', 'superseded', 'failed')",
            name="ck_document_versions_document_version_status",
        ),
        sa.CheckConstraint(
            "char_length(source_checksum) = 64",
            name="ck_document_versions_source_checksum_length",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "version_label", name="uq_document_version_label"),
        sa.UniqueConstraint("id", "document_id", name="uq_document_versions_id_document"),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])
    op.create_foreign_key(
        "fk_documents_current_version_owner",
        "documents",
        "document_versions",
        ["current_version_id", "id"],
        ["id", "document_id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "document_acl",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "department_id", name="uq_document_acl_department"),
    )
    op.create_index("ix_document_acl_department_id", "document_acl", ["department_id"])
    op.create_index("ix_document_acl_document_id", "document_acl", ["document_id"])

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=False),
        sa.Column("identity_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=9), nullable=False),
        sa.Column("stage", sa.String(length=40), server_default="created", nullable=False),
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_detail", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'queued', 'running', 'completed', 'failed')",
            name="ck_ingestion_jobs_ingestion_job_status",
        ),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="ck_ingestion_jobs_progress_range"),
        sa.CheckConstraint("attempts >= 0", name="ck_ingestion_jobs_attempts_non_negative"),
        sa.ForeignKeyConstraint(
            ["document_version_id"], ["document_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_version_id", "identity_hash", name="uq_ingestion_job_identity"
        ),
    )
    op.create_index(
        "ix_ingestion_jobs_document_version_id", "ingestion_jobs", ["document_version_id"]
    )


def downgrade() -> None:
    op.drop_table("ingestion_jobs")
    op.drop_table("document_acl")
    op.drop_constraint("fk_documents_current_version_owner", "documents", type_="foreignkey")
    op.drop_table("document_versions")
    op.drop_table("documents")
