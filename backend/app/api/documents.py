"""Admin-only document upload and draft preview API."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.csrf import require_csrf
from app.auth.policies import require_roles
from app.config import Settings
from app.db.models import DocumentVisibility, UserRole
from app.dependencies import get_db_session
from app.services.documents import DocumentUploadError, DocumentUploadService, UploadMetadata

router = APIRouter(prefix="/documents", tags=["documents"])


class PreviewPageResponse(BaseModel):
    page_number: int
    text: str


class DocumentPreviewResponse(BaseModel):
    document_id: UUID
    version_id: UUID
    document_key: str
    title: str
    version_label: str
    status: str
    job_id: UUID
    byte_size: int
    parser_version: str
    pages: list[PreviewPageResponse]


class VersionPreviewResponse(BaseModel):
    document_id: UUID
    version_id: UUID
    byte_size: int
    parser_version: str
    pages: list[PreviewPageResponse]


def _service(settings: Settings) -> DocumentUploadService:
    return DocumentUploadService(
        storage_root=Path(settings.document_storage_path),
        max_pdf_bytes=settings.document_max_pdf_bytes,
        max_pdf_pages=settings.document_max_pdf_pages,
        max_extracted_text_bytes=settings.document_max_extracted_text_bytes,
    )


def _upload_error(error: DocumentUploadError) -> HTTPException:
    status_code = {
        "unsupported_media_type": status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        "pdf_too_large": status.HTTP_413_CONTENT_TOO_LARGE,
        "document_key_conflict": status.HTTP_409_CONFLICT,
    }.get(error.code, status.HTTP_422_UNPROCESSABLE_CONTENT)
    return HTTPException(
        status_code=status_code, detail={"code": error.code, "message": str(error)}
    )


@router.post(
    "/uploads",
    response_model=DocumentPreviewResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf), Depends(require_roles(UserRole.ADMIN))],
)
async def upload_document(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    file: Annotated[UploadFile, File()],
    document_key: Annotated[str, Form()],
    title: Annotated[str, Form()],
    version_label: Annotated[str, Form()],
    authority: Annotated[str, Form()],
    effective_at: Annotated[datetime, Form()],
    language: Annotated[str, Form()] = "vi",
    visibility: Annotated[Literal["company", "department", "it_only"], Form()] = "company",
    department_id: Annotated[UUID | None, Form()] = None,
    expires_at: Annotated[datetime | None, Form()] = None,
) -> DocumentPreviewResponse:
    settings = cast(Settings, request.app.state.settings)
    service = _service(settings)
    try:
        metadata = UploadMetadata(
            document_key=document_key,
            title=title,
            version_label=version_label,
            authority=authority,
            effective_at=effective_at,
            language=language,
            visibility=DocumentVisibility(visibility),
            department_id=department_id,
            expires_at=expires_at,
        )
        draft = await service.create_draft(session, upload=file, metadata=metadata)
        await session.commit()
    except ValidationError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_metadata", "message": str(error)},
        ) from error
    except DocumentUploadError as error:
        await session.rollback()
        raise _upload_error(error) from error
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "document_conflict", "message": "Document metadata conflicts"},
        ) from error
    finally:
        await file.close()
    return DocumentPreviewResponse(
        document_id=draft.document.id,
        version_id=draft.version.id,
        document_key=draft.document.document_key,
        title=draft.document.title,
        version_label=draft.version.version_label,
        status=draft.version.status.value,
        job_id=draft.job.id,
        byte_size=draft.preview.byte_size,
        parser_version=draft.preview.parser_version,
        pages=[
            PreviewPageResponse(page_number=page.page_number, text=page.text)
            for page in draft.preview.pages
        ],
    )


@router.get(
    "/{document_id}/versions/{version_id}/preview",
    response_model=VersionPreviewResponse,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def preview_document_version(
    document_id: UUID,
    version_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> VersionPreviewResponse:
    settings = cast(Settings, request.app.state.settings)
    try:
        preview = await _service(settings).preview(
            session,
            document_id=document_id,
            version_id=version_id,
        )
    except DocumentUploadError as error:
        raise _upload_error(error) from error
    if preview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    return VersionPreviewResponse(
        document_id=document_id,
        version_id=version_id,
        byte_size=preview.byte_size,
        parser_version=preview.parser_version,
        pages=[
            PreviewPageResponse(page_number=page.page_number, text=page.text)
            for page in preview.pages
        ],
    )
