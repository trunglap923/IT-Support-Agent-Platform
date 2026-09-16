from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.demo_identity import ensure_demo_identity
from app.auth.passwords import hash_password
from app.config import Settings
from app.db import Database
from app.db.models import DocumentVersion, User, UserRole
from app.main import create_app
from tests.unit.pdf_factory import build_text_pdf

PASSWORD = "correct-horse-battery-staple"
ORIGIN = "http://testserver"


def test_admin_upload_is_bounded_isolated_and_previewable(
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    async def seed() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                employee = await ensure_demo_identity(session, password=PASSWORD)
                session.add(
                    User(
                        email="document-admin@example.com",
                        display_name="Document Admin",
                        password_hash=hash_password(PASSWORD),
                        role=UserRole.ADMIN,
                        department_id=employee.department_id,
                        active=True,
                    )
                )
        finally:
            await database.close()

    asyncio.run(seed())
    settings = Settings(
        database_url=migrated_database_url,
        auth_login_rate_limit_enabled=False,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
        document_storage_path=str(tmp_path),
        document_max_pdf_bytes=1024 * 1024,
    )
    pdf = build_text_pdf("VPN access requires the managed client.", "Use company SSO.")
    form = {
        "document_key": "vpn-upload-guide",
        "title": "VPN upload guide",
        "version_label": "v1",
        "authority": "IT Operations",
        "language": "en",
        "visibility": "company",
        "effective_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
    }

    with TestClient(create_app(settings=settings), base_url=ORIGIN) as employee_client:
        login = employee_client.post(
            "/api/v1/auth/login",
            json={"email": "employee.engineering@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        denied = employee_client.post(
            "/api/v1/documents/uploads",
            data=form,
            files={"file": ("../../escape.pdf", pdf, "application/pdf")},
            headers={"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrf_token"]},
        )
        assert denied.status_code == 403

    with TestClient(create_app(settings=settings), base_url=ORIGIN) as admin_client:
        login = admin_client.post(
            "/api/v1/auth/login",
            json={"email": "document-admin@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        headers = {"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrf_token"]}
        wrong_mime = admin_client.post(
            "/api/v1/documents/uploads",
            data={**form, "document_key": "wrong-mime"},
            files={"file": ("guide.pdf", pdf, "text/plain")},
            headers=headers,
        )
        assert wrong_mime.status_code == 415

        created = admin_client.post(
            "/api/v1/documents/uploads",
            data=form,
            files={"file": ("../../escape.pdf", pdf, "application/pdf")},
            headers=headers,
        )
        assert created.status_code == 201
        body = created.json()
        assert body["status"] == "draft"
        assert [page["page_number"] for page in body["pages"]] == [1, 2]
        assert body["pages"][0]["text"] == "VPN access requires the managed client."

        preview = admin_client.get(
            f"/api/v1/documents/{body['document_id']}/versions/{body['version_id']}/preview"
        )
        assert preview.status_code == 200
        assert preview.json()["pages"] == body["pages"]

    async def verify_storage() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session:
                version = await session.scalar(select(DocumentVersion))
                assert version is not None
                path = (tmp_path / version.storage_key).resolve()
                assert path.is_relative_to(tmp_path.resolve())
                assert "escape" not in version.storage_key
                assert path.read_bytes() == pdf
        finally:
            await database.close()

    asyncio.run(verify_storage())


def test_upload_rejects_oversize_before_persisting(
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    async def seed() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                employee = await ensure_demo_identity(session, password=PASSWORD)
                session.add(
                    User(
                        email="size-admin@example.com",
                        display_name="Size Admin",
                        password_hash=hash_password(PASSWORD),
                        role=UserRole.ADMIN,
                        department_id=employee.department_id,
                        active=True,
                    )
                )
        finally:
            await database.close()

    asyncio.run(seed())
    settings = Settings(
        database_url=migrated_database_url,
        auth_login_rate_limit_enabled=False,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
        document_storage_path=str(tmp_path),
        document_max_pdf_bytes=32,
    )
    with TestClient(create_app(settings=settings), base_url=ORIGIN) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "size-admin@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        response = client.post(
            "/api/v1/documents/uploads",
            data={
                "document_key": "oversize-pdf",
                "title": "Oversize PDF",
                "version_label": "v1",
                "authority": "IT",
                "effective_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
            },
            files={
                "file": ("large.pdf", build_text_pdf("larger than 32 bytes"), "application/pdf")
            },
            headers={"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrf_token"]},
        )
        assert response.status_code == 413
        assert response.json()["detail"]["code"] == "pdf_too_large"
    assert not list(tmp_path.rglob("*.pdf"))
