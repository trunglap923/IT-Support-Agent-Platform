import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.db import Database
from app.db.models import Document, DocumentVersion, DocumentVersionStatus, DocumentVisibility
from app.repositories.documents import DocumentRepository


def test_create_document_version_and_draft_job(migrated_database_url: str) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                document, version, job = await DocumentRepository().create_draft(
                    session,
                    document_key="vpn-setup",
                    title="VPN setup",
                    visibility=DocumentVisibility.COMPANY,
                    department_id=None,
                    version_label="v1",
                    authority="it",
                    language="en",
                    media_type="application/pdf",
                    source_checksum="a" * 64,
                    storage_key="documents/vpn-setup/v1.pdf",
                    effective_at=datetime(2026, 1, 1, tzinfo=UTC),
                    expires_at=None,
                    identity_hash="b" * 64,
                )
                assert version.document_id == document.id
                assert version.status is DocumentVersionStatus.DRAFT
                assert job.document_version_id == version.id
                assert job.progress == 0
        finally:
            await database.close()

    asyncio.run(scenario())


def test_current_version_must_belong_to_same_document(migrated_database_url: str) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session:
                first = Document(
                    document_key="first",
                    title="First",
                    visibility=DocumentVisibility.COMPANY,
                    department_id=None,
                )
                second = Document(
                    document_key="second",
                    title="Second",
                    visibility=DocumentVisibility.COMPANY,
                    department_id=None,
                )
                session.add_all([first, second])
                await session.flush()
                second_version = DocumentVersion(
                    document_id=second.id,
                    version_label="v1",
                    status=DocumentVersionStatus.READY,
                    authority="it",
                    language="en",
                    media_type="application/pdf",
                    source_checksum="c" * 64,
                    storage_key=f"documents/{uuid4()}.pdf",
                    effective_at=datetime(2026, 1, 1, tzinfo=UTC),
                )
                session.add(second_version)
                await session.flush()
                first.current_version_id = second_version.id
                with pytest.raises(IntegrityError):
                    await session.flush()
                await session.rollback()
        finally:
            await database.close()

    asyncio.run(scenario())
