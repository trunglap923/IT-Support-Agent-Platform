"""Document persistence queries; publication remains a separate service concern."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Document,
    DocumentVersion,
    DocumentVersionStatus,
    DocumentVisibility,
    IngestionJob,
    IngestionJobStatus,
)


class DocumentRepository:
    async def create_draft(
        self,
        session: AsyncSession,
        *,
        document_key: str,
        title: str,
        visibility: DocumentVisibility,
        department_id: UUID | None,
        version_label: str,
        authority: str,
        language: str,
        media_type: str,
        source_checksum: str,
        storage_key: str,
        effective_at: datetime,
        expires_at: datetime | None,
        identity_hash: str,
    ) -> tuple[Document, DocumentVersion, IngestionJob]:
        document = Document(
            document_key=document_key,
            title=title,
            visibility=visibility,
            department_id=department_id,
        )
        session.add(document)
        await session.flush()
        version = DocumentVersion(
            document_id=document.id,
            version_label=version_label,
            status=DocumentVersionStatus.DRAFT,
            authority=authority,
            language=language,
            media_type=media_type,
            source_checksum=source_checksum,
            storage_key=storage_key,
            effective_at=effective_at,
            expires_at=expires_at,
        )
        session.add(version)
        await session.flush()
        job = IngestionJob(
            document_version_id=version.id,
            identity_hash=identity_hash,
            status=IngestionJobStatus.DRAFT,
        )
        session.add(job)
        await session.flush()
        return document, version, job

    async def get_by_key(self, session: AsyncSession, *, document_key: str) -> Document | None:
        return cast(
            Document | None,
            await session.scalar(select(Document).where(Document.document_key == document_key)),
        )

    async def get_version(
        self, session: AsyncSession, *, version_id: UUID
    ) -> DocumentVersion | None:
        return await session.get(DocumentVersion, version_id)

    async def create_version(
        self,
        session: AsyncSession,
        *,
        document: Document,
        version_label: str,
        authority: str,
        language: str,
        media_type: str,
        source_checksum: str,
        storage_key: str,
        effective_at: datetime,
        expires_at: datetime | None,
        identity_hash: str,
    ) -> tuple[DocumentVersion, IngestionJob]:
        version = DocumentVersion(
            document_id=document.id,
            version_label=version_label,
            status=DocumentVersionStatus.DRAFT,
            authority=authority,
            language=language,
            media_type=media_type,
            source_checksum=source_checksum,
            storage_key=storage_key,
            effective_at=effective_at,
            expires_at=expires_at,
        )
        session.add(version)
        await session.flush()
        job = IngestionJob(
            document_version_id=version.id,
            identity_hash=identity_hash,
            status=IngestionJobStatus.DRAFT,
        )
        session.add(job)
        await session.flush()
        return version, job

    async def list_documents(
        self,
        session: AsyncSession,
        *,
        limit: int | None = None,
        before: tuple[datetime, UUID] | None = None,
    ) -> list[Document]:
        statement = select(Document)
        if before is not None:
            timestamp, item_id = before
            statement = statement.where(
                or_(
                    Document.updated_at < timestamp,
                    and_(Document.updated_at == timestamp, Document.id < item_id),
                )
            )
        statement = statement.order_by(Document.updated_at.desc(), Document.id.desc())
        if limit is not None:
            statement = statement.limit(limit)
        return list((await session.scalars(statement)).all())

    async def list_versions(
        self, session: AsyncSession, *, document_id: UUID
    ) -> list[DocumentVersion]:
        return list(
            (
                await session.scalars(
                    select(DocumentVersion)
                    .where(DocumentVersion.document_id == document_id)
                    .order_by(DocumentVersion.created_at.desc(), DocumentVersion.id.desc())
                )
            ).all()
        )
