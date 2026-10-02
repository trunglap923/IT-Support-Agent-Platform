"""Shared scoped candidate projection for all retrieval branches."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select, select

from app.auth.principal import Principal
from app.db.models import Document, DocumentChunk, DocumentVersion
from app.rag.retrieval.filters import readable_current_document
from app.rag.retrieval.models import RetrievalCandidate


def scoped_chunk_query(principal: Principal, *, now: datetime) -> Select[Any]:
    return (
        select(
            DocumentChunk.id.label("chunk_id"),
            DocumentChunk.section_id,
            Document.id.label("document_id"),
            DocumentVersion.id.label("version_id"),
            Document.document_key,
            DocumentVersion.version_label,
            Document.title,
            DocumentChunk.page_number,
            DocumentChunk.section,
            DocumentChunk.content,
            DocumentChunk.ordinal,
            DocumentChunk.section_path,
        )
        .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(readable_current_document(principal, now=now))
    )


def candidate_from_row(row: object) -> RetrievalCandidate:
    mapping = row._mapping  # type: ignore[attr-defined]
    return RetrievalCandidate(
        chunk_id=mapping["chunk_id"],
        section_id=mapping["section_id"],
        document_id=mapping["document_id"],
        version_id=mapping["version_id"],
        document_key=mapping["document_key"],
        version_label=mapping["version_label"],
        title=mapping["title"],
        page_number=mapping["page_number"],
        section=mapping["section"],
        content=mapping["content"],
        ordinal=mapping["ordinal"],
        section_path=tuple(mapping["section_path"] or ()),
    )
