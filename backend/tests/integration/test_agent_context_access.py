from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from app.auth.passwords import hash_password
from app.auth.principal import Principal
from app.db import Database
from app.db.models import (
    Conversation,
    Department,
    Document,
    DocumentVersion,
    DocumentVersionStatus,
    DocumentVisibility,
    Message,
    User,
    UserRole,
)
from app.services.documents.access import HISTORICAL_SOURCE_LABEL, authorized_history_context


def test_agent_history_labels_superseded_sources_and_drops_revoked_acl(
    migrated_database_url: str,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                department = Department(key="engineering", name="Engineering")
                session.add(department)
                await session.flush()
                user = User(
                    email="context-owner@example.com",
                    display_name="Context Owner",
                    password_hash=hash_password("test-password"),
                    role=UserRole.EMPLOYEE,
                    department_id=department.id,
                    active=True,
                )
                session.add(user)
                await session.flush()
                document = Document(
                    document_key="context-vpn",
                    title="VPN context",
                    visibility=DocumentVisibility.COMPANY,
                )
                session.add(document)
                await session.flush()
                old_version = DocumentVersion(
                    document_id=document.id,
                    version_label="v1",
                    status=DocumentVersionStatus.SUPERSEDED,
                    authority="internal-it",
                    language="vi",
                    media_type="text/markdown",
                    source_checksum="1" * 64,
                    storage_key="context-vpn-v1.md",
                    effective_at=datetime(2026, 1, 1, tzinfo=UTC),
                )
                current_version = DocumentVersion(
                    document_id=document.id,
                    version_label="v2",
                    status=DocumentVersionStatus.PUBLISHED,
                    authority="internal-it",
                    language="vi",
                    media_type="text/markdown",
                    source_checksum="2" * 64,
                    storage_key="context-vpn-v2.md",
                    effective_at=datetime(2026, 2, 1, tzinfo=UTC),
                )
                session.add_all([old_version, current_version])
                await session.flush()
                document.current_version_id = current_version.id
                conversation = Conversation(owner_id=user.id, title="Context")
                session.add(conversation)
                await session.flush()
                message = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content="Hãy dùng cấu hình VPN cũ.",
                    outcome="answered",
                    citations=[
                        {
                            "document_id": str(document.id),
                            "version_id": str(old_version.id),
                            "source_id": "src_old",
                        }
                    ],
                )
                session.add(message)
                await session.flush()
                principal = Principal(
                    user_id=user.id,
                    session_id=UUID(int=0),
                    email=user.email,
                    display_name=user.display_name,
                    role=user.role,
                    department_id=department.id,
                    department_key=department.key,
                )
                history = await authorized_history_context(
                    session,
                    principal=principal,
                    messages=[message],
                )
                assert history[0].content.startswith(HISTORICAL_SOURCE_LABEL)

                document.visibility = DocumentVisibility.IT_ONLY
                await session.flush()
                revoked = await authorized_history_context(
                    session,
                    principal=principal,
                    messages=[message],
                )
                assert revoked == []
        finally:
            await database.close()

    asyncio.run(scenario())
