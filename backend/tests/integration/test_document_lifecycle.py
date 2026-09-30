from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from app.auth.demo_identity import ensure_demo_identity
from app.auth.passwords import hash_password
from app.auth.principal import Principal
from app.config import AIProvider, Settings
from app.db import Database
from app.db.models import Conversation, Message, User, UserRole
from app.main import create_app
from app.providers.embeddings import FakeEmbeddingProvider
from app.rag.citations.sources import source_id_for_chunk
from app.rag.retrieval.query import HybridRetriever
from tests.unit.pdf_factory import build_text_pdf

PASSWORD = "correct-horse-battery-staple"
ORIGIN = "http://testserver"


def test_publish_acl_revoke_apply_to_retrieval_and_history(
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    async def seed() -> tuple[UUID, UUID]:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                employee = await ensure_demo_identity(session, password=PASSWORD)
                admin = User(
                    email="lifecycle-admin@example.com",
                    display_name="Lifecycle Admin",
                    password_hash=hash_password(PASSWORD),
                    role=UserRole.ADMIN,
                    department_id=employee.department_id,
                    active=True,
                )
                session.add(admin)
                await session.flush()
                return employee.id, admin.id
        finally:
            await database.close()

    employee_id, _ = asyncio.run(seed())
    settings = Settings(
        database_url=migrated_database_url,
        text_provider=AIProvider.FAKE,
        embedding_provider=AIProvider.FAKE,
        auth_login_rate_limit_enabled=False,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
        document_storage_path=str(tmp_path),
    )
    with TestClient(create_app(settings=settings), base_url=ORIGIN) as admin_client:
        login = admin_client.post(
            "/api/v1/auth/login",
            json={"email": "lifecycle-admin@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        headers = {"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrf_token"]}
        created = admin_client.post(
            "/api/v1/documents/uploads",
            data={
                "document_key": "vpn-lifecycle",
                "title": "VPN lifecycle guide",
                "version_label": "v1",
                "authority": "IT Operations",
                "language": "en",
                "visibility": "company",
                "effective_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
            },
            files={
                "file": (
                    "vpn.pdf",
                    build_text_pdf("VPN access uses the managed client and company SSO."),
                    "application/pdf",
                )
            },
            headers=headers,
        )
        assert created.status_code == 201
        document_id = created.json()["document_id"]
        version_id = created.json()["version_id"]

        processed = admin_client.post(
            f"/api/v1/documents/{document_id}/versions/{version_id}/process",
            headers=headers,
        )
        assert processed.status_code == 200
        assert processed.json()["status"] == "ready"

        published = admin_client.post(
            f"/api/v1/documents/{document_id}/publish",
            json={"version_id": version_id, "expected_version": 1},
            headers=headers,
        )
        assert published.status_code == 200
        assert published.json()["current_version_id"] == version_id
        assert published.json()["version"] == 2

    async def retrieve_and_seed_history() -> tuple[int, UUID, str]:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                employee = await session.get(User, employee_id)
                assert employee is not None
                principal = Principal(
                    user_id=employee.id,
                    session_id=UUID(int=0),
                    email=employee.email,
                    display_name=employee.display_name,
                    role=employee.role,
                    department_id=employee.department_id,
                    department_key="engineering",
                )
                hits = await HybridRetriever(
                    embedding_provider=FakeEmbeddingProvider(dimensions=1536)
                ).search(
                    session,
                    query="managed VPN client company SSO",
                    principal=principal,
                    operation_id="document-lifecycle-before-revoke",
                )
                conversation = Conversation(owner_id=employee.id, title="Cited answer")
                session.add(conversation)
                await session.flush()
                session.add(
                    Message(
                        conversation_id=conversation.id,
                        role="assistant",
                        content="Use the managed VPN client and company SSO.",
                        outcome="answered",
                        citations=[
                            {
                                "source_id": source_id_for_chunk(hits[0].chunk_id),
                                "source_url": (
                                    f"/api/v1/sources/{source_id_for_chunk(hits[0].chunk_id)}"
                                    "/download"
                                ),
                                "document_id": str(hits[0].document_id),
                                "version_id": str(hits[0].version_id),
                                "chunk_id": str(hits[0].chunk_id),
                                "title": hits[0].title,
                                "excerpt": hits[0].content,
                            }
                        ],
                    )
                )
                return len(hits), conversation.id, source_id_for_chunk(hits[0].chunk_id)
        finally:
            await database.close()

    hit_count, conversation_id, source_id = asyncio.run(retrieve_and_seed_history())
    assert hit_count > 0

    with TestClient(create_app(settings=settings), base_url=ORIGIN) as employee_client:
        login = employee_client.post(
            "/api/v1/auth/login",
            json={"email": "employee.engineering@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        assert login.status_code == 200
        visible = employee_client.get(f"/api/v1/conversations/{conversation_id}/messages")
        assert visible.json()["items"][0]["content"] == (
            "Use the managed VPN client and company SSO."
        )
        assert len(visible.json()["items"][0]["citations"]) == 1
        source = employee_client.get(f"/api/v1/sources/{source_id}")
        assert source.status_code == 200
        assert source.json()["page_number"] == 1
        downloaded = employee_client.get(f"/api/v1/sources/{source_id}/download")
        assert downloaded.status_code == 200
        assert downloaded.headers["cache-control"] == "private, no-store"
        assert downloaded.content.startswith(b"%PDF")

    with TestClient(create_app(settings=settings), base_url=ORIGIN) as admin_client:
        login = admin_client.post(
            "/api/v1/auth/login",
            json={"email": "lifecycle-admin@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        headers = {"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrf_token"]}
        restricted = admin_client.put(
            f"/api/v1/documents/{document_id}/acl",
            json={
                "expected_version": 2,
                "visibility": "it_only",
                "department_id": None,
                "granted_department_ids": [],
            },
            headers=headers,
        )
        assert restricted.status_code == 200
        assert restricted.json()["access_version"] == 2

        stale = admin_client.post(
            f"/api/v1/documents/{document_id}/revoke",
            json={"expected_version": 2},
            headers=headers,
        )
        assert stale.status_code == 409
        revoked = admin_client.post(
            f"/api/v1/documents/{document_id}/revoke",
            json={"expected_version": 3},
            headers=headers,
        )
        assert revoked.status_code == 200
        assert revoked.json()["archived"] is True
        assert revoked.json()["current_version_id"] is None

    async def retrieve_after_revoke() -> int:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session:
                employee = await session.get(User, employee_id)
                assert employee is not None
                principal = Principal(
                    user_id=employee.id,
                    session_id=UUID(int=0),
                    email=employee.email,
                    display_name=employee.display_name,
                    role=employee.role,
                    department_id=employee.department_id,
                    department_key="engineering",
                )
                hits = await HybridRetriever(
                    embedding_provider=FakeEmbeddingProvider(dimensions=1536)
                ).search(
                    session,
                    query="managed VPN client company SSO",
                    principal=principal,
                    operation_id="document-lifecycle-after-revoke",
                )
                return len(hits)
        finally:
            await database.close()

    assert asyncio.run(retrieve_after_revoke()) == 0
    with TestClient(create_app(settings=settings), base_url=ORIGIN) as employee_client:
        employee_client.post(
            "/api/v1/auth/login",
            json={"email": "employee.engineering@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        hidden = employee_client.get(f"/api/v1/conversations/{conversation_id}/messages")
        assert hidden.status_code == 200
        assert hidden.json()["items"][0]["outcome"] == "source_revoked"
        assert hidden.json()["items"][0]["citations"] == []
        assert "managed VPN" not in hidden.json()["items"][0]["content"]
        assert employee_client.get(f"/api/v1/sources/{source_id}").status_code == 404
        assert employee_client.get(f"/api/v1/sources/{source_id}/download").status_code == 404
