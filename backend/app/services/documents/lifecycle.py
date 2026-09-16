"""Transactional document publication, revocation and ACL lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Document,
    DocumentAcl,
    DocumentVersion,
    DocumentVersionStatus,
    DocumentVisibility,
)


class DocumentLifecycleNotFoundError(LookupError):
    pass


class DocumentLifecycleConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DocumentLifecycleResult:
    document: Document
    version: DocumentVersion | None


class DocumentLifecycleService:
    async def publish(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        version_id: UUID,
        expected_version: int,
        now: datetime | None = None,
    ) -> DocumentLifecycleResult:
        current = now or datetime.now(UTC)
        document = await self._lock_document(session, document_id)
        self._check_version(document, expected_version)
        version = await session.scalar(
            select(DocumentVersion)
            .where(
                DocumentVersion.id == version_id,
                DocumentVersion.document_id == document.id,
            )
            .with_for_update()
        )
        if version is None:
            raise DocumentLifecycleNotFoundError("Version does not belong to document")
        if version.status is not DocumentVersionStatus.READY:
            raise DocumentLifecycleConflictError("Only a ready version can be published")
        if version.effective_at > current:
            raise DocumentLifecycleConflictError("Version effective_at is in the future")
        if version.expires_at is not None and version.expires_at <= current:
            raise DocumentLifecycleConflictError("Version has expired")

        if document.current_version_id is not None:
            previous = await session.get(DocumentVersion, document.current_version_id)
            if previous is not None:
                previous.status = DocumentVersionStatus.SUPERSEDED
        version.status = DocumentVersionStatus.PUBLISHED
        document.current_version_id = version.id
        document.archived = False
        document.version += 1
        await session.flush()
        return DocumentLifecycleResult(document=document, version=version)

    async def revoke(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        expected_version: int,
    ) -> DocumentLifecycleResult:
        document = await self._lock_document(session, document_id)
        self._check_version(document, expected_version)
        previous = (
            await session.get(DocumentVersion, document.current_version_id)
            if document.current_version_id is not None
            else None
        )
        if previous is not None:
            previous.status = DocumentVersionStatus.SUPERSEDED
        document.current_version_id = None
        document.archived = True
        document.access_version += 1
        document.version += 1
        await session.flush()
        return DocumentLifecycleResult(document=document, version=previous)

    async def replace_acl(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        expected_version: int,
        visibility: DocumentVisibility,
        department_id: UUID | None,
        granted_department_ids: set[UUID],
    ) -> DocumentLifecycleResult:
        if (visibility is DocumentVisibility.DEPARTMENT) != (department_id is not None):
            raise DocumentLifecycleConflictError(
                "department visibility requires exactly one department_id"
            )
        document = await self._lock_document(session, document_id)
        self._check_version(document, expected_version)
        document.visibility = visibility
        document.department_id = department_id
        document.access_version += 1
        document.version += 1
        await session.execute(delete(DocumentAcl).where(DocumentAcl.document_id == document.id))
        session.add_all(
            DocumentAcl(document_id=document.id, department_id=value)
            for value in sorted(granted_department_ids, key=str)
        )
        await session.flush()
        return DocumentLifecycleResult(document=document, version=None)

    @staticmethod
    async def _lock_document(session: AsyncSession, document_id: UUID) -> Document:
        document = await session.scalar(
            select(Document).where(Document.id == document_id).with_for_update()
        )
        if document is None:
            raise DocumentLifecycleNotFoundError("Document was not found")
        return document

    @staticmethod
    def _check_version(document: Document, expected_version: int) -> None:
        if document.version != expected_version:
            raise DocumentLifecycleConflictError("Document version is stale")
