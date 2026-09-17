"""Authenticated, ACL-rechecked access to current citation sources."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import Document, DocumentChunk, DocumentVersion
from app.dependencies import CurrentPrincipal, get_db_session
from app.rag.citations.sources import source_id_for_chunk
from app.rag.retrieval.filters import readable_current_document
from app.services.documents import DocumentUploadError, DocumentUploadService

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceResponse(BaseModel):
    source_id: str
    title: str
    version_label: str
    page_number: int | None
    section: str | None
    excerpt: str
    download_url: str


def _chunk_id(source_id: str) -> UUID:
    if len(source_id) != 36 or not source_id.startswith("src_"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    try:
        return UUID(hex=source_id.removeprefix("src_"))
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        ) from error


async def _readable_source(
    session: AsyncSession,
    *,
    source_id: str,
    principal: CurrentPrincipal,
) -> tuple[DocumentChunk, DocumentVersion, Document]:
    row = (
        await session.execute(
            select(DocumentChunk, DocumentVersion, Document)
            .join(DocumentVersion, DocumentVersion.id == DocumentChunk.version_id)
            .join(Document, Document.id == DocumentVersion.document_id)
            .where(
                DocumentChunk.id == _chunk_id(source_id),
                readable_current_document(principal, now=datetime.now(UTC)),
            )
        )
    ).one_or_none()
    if row is None:
        # Deliberately hide whether the source exists but falls outside the caller's ACL.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return row[0], row[1], row[2]


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: str,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SourceResponse:
    chunk, version, document = await _readable_source(
        session,
        source_id=source_id,
        principal=principal,
    )
    canonical_source_id = source_id_for_chunk(chunk.id)
    return SourceResponse(
        source_id=canonical_source_id,
        title=document.title,
        version_label=version.version_label,
        page_number=chunk.page_number,
        section=chunk.section,
        excerpt=" ".join(chunk.content.split())[:2_000],
        download_url=f"/api/v1/sources/{canonical_source_id}/download",
    )


@router.get("/{source_id}/download", response_class=FileResponse)
async def download_source(
    source_id: str,
    request: Request,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FileResponse:
    _, version, document = await _readable_source(
        session,
        source_id=source_id,
        principal=principal,
    )
    settings = cast(Settings, request.app.state.settings)
    storage = DocumentUploadService(
        storage_root=Path(settings.document_storage_path),
        max_pdf_bytes=settings.document_max_pdf_bytes,
        max_pdf_pages=settings.document_max_pdf_pages,
        max_extracted_text_bytes=settings.document_max_extracted_text_bytes,
    )
    try:
        path = storage.resolve_storage_key(version.storage_key)
    except DocumentUploadError as error:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Source file is unavailable",
        ) from error
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Source file is unavailable")
    suffix = ".pdf" if version.media_type == "application/pdf" else ".md"
    return FileResponse(
        path,
        media_type=version.media_type,
        filename=f"{document.document_key}-{version.version_label}{suffix}",
        headers={"Cache-Control": "private, no-store"},
    )
