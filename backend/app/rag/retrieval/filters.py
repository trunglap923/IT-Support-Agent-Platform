"""One server-owned ACL predicate shared by lexical and vector retrieval."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, exists, or_
from sqlalchemy.sql.elements import ColumnElement

from app.auth.principal import Principal
from app.db.models import Document, DocumentAcl, DocumentVersion, DocumentVersionStatus, UserRole


def readable_current_document(principal: Principal, *, now: datetime) -> ColumnElement[bool]:
    department_grant = exists().where(
        DocumentAcl.document_id == Document.id,
        DocumentAcl.department_id == principal.department_id,
    )
    scope = or_(
        Document.visibility == "company",
        and_(
            Document.visibility == "department",
            or_(Document.department_id == principal.department_id, department_grant),
        ),
    )
    if principal.role in {UserRole.IT, UserRole.ADMIN}:
        scope = or_(scope, Document.visibility == "it_only")
    return and_(
        Document.archived.is_(False),
        Document.current_version_id == DocumentVersion.id,
        DocumentVersion.status == DocumentVersionStatus.PUBLISHED,
        DocumentVersion.effective_at <= now,
        or_(DocumentVersion.expires_at.is_(None), DocumentVersion.expires_at > now),
        scope,
    )
