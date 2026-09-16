"""Admin-only document upload and draft preview API."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.csrf import require_csrf
from app.auth.policies import require_roles
from app.config import Settings
from app.db import Database
from app.db.models import (
    Document,
    DocumentAcl,
    DocumentVersion,
    DocumentVisibility,
    IngestionJob,
    UserRole,
)
from app.dependencies import get_db_session
from app.providers.factory import create_embedding_provider
from app.rag.ingestion.pdf_parser import PdfParser
from app.rag.ingestion.pipeline import IngestionPipeline
from app.repositories.documents import DocumentRepository
from app.services.documents import (
    DocumentLifecycleConflictError,
    DocumentLifecycleNotFoundError,
    DocumentLifecycleService,
    DocumentUploadError,
    DocumentUploadService,
    UploadMetadata,
    VersionUploadMetadata,
)

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


class DocumentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_label: str
    status: str
    authority: str
    language: str
    effective_at: datetime
    expires_at: datetime | None
    created_at: datetime


class DocumentResponse(BaseModel):
    id: UUID
    document_key: str
    title: str
    visibility: str
    department_id: UUID | None
    archived: bool
    current_version_id: UUID | None
    access_version: int
    version: int
    granted_department_ids: list[UUID]
    versions: list[DocumentVersionResponse]


class ProcessVersionResponse(BaseModel):
    document_id: UUID
    version_id: UUID
    job_id: UUID
    status: str
    chunk_count: int
    reused: bool


class PublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: UUID
    expected_version: int = Field(ge=1)


class RevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)


class ReplaceAclRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    visibility: DocumentVisibility
    department_id: UUID | None = None
    granted_department_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_scope(self) -> ReplaceAclRequest:
        if (self.visibility is DocumentVisibility.DEPARTMENT) != (self.department_id is not None):
            raise ValueError("department visibility requires exactly one department_id")
        if len(set(self.granted_department_ids)) != len(self.granted_department_ids):
            raise ValueError("granted_department_ids must be unique")
        return self


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


def _lifecycle_error(
    error: DocumentLifecycleNotFoundError | DocumentLifecycleConflictError,
) -> HTTPException:
    return HTTPException(
        status_code=(
            status.HTTP_404_NOT_FOUND
            if isinstance(error, DocumentLifecycleNotFoundError)
            else status.HTTP_409_CONFLICT
        ),
        detail=str(error),
    )


async def _document_response(session: AsyncSession, document: Document) -> DocumentResponse:
    repository = DocumentRepository()
    versions = await repository.list_versions(session, document_id=document.id)
    grants = list(
        await session.scalars(
            select(DocumentAcl.department_id)
            .where(DocumentAcl.document_id == document.id)
            .order_by(DocumentAcl.department_id)
        )
    )
    return DocumentResponse(
        id=document.id,
        document_key=document.document_key,
        title=document.title,
        visibility=document.visibility.value,
        department_id=document.department_id,
        archived=document.archived,
        current_version_id=document.current_version_id,
        access_version=document.access_version,
        version=document.version,
        granted_department_ids=grants,
        versions=[DocumentVersionResponse.model_validate(value) for value in versions],
    )


@router.get(
    "",
    response_model=list[DocumentResponse],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def list_documents(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[DocumentResponse]:
    values = await DocumentRepository().list_documents(session)
    return [await _document_response(session, value) for value in values]


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


@router.post(
    "/{document_id}/versions",
    response_model=DocumentPreviewResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf), Depends(require_roles(UserRole.ADMIN))],
)
async def upload_document_version(
    document_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    file: Annotated[UploadFile, File()],
    version_label: Annotated[str, Form()],
    authority: Annotated[str, Form()],
    effective_at: Annotated[datetime, Form()],
    language: Annotated[str, Form()] = "vi",
    expires_at: Annotated[datetime | None, Form()] = None,
) -> DocumentPreviewResponse:
    settings = cast(Settings, request.app.state.settings)
    service = _service(settings)
    try:
        metadata = VersionUploadMetadata(
            version_label=version_label,
            authority=authority,
            effective_at=effective_at,
            language=language,
            expires_at=expires_at,
        )
        draft = await service.create_version(
            session,
            document_id=document_id,
            upload=file,
            metadata=metadata,
        )
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
            detail={"code": "version_conflict", "message": "Version metadata conflicts"},
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


@router.post(
    "/{document_id}/versions/{version_id}/process",
    response_model=ProcessVersionResponse,
    dependencies=[Depends(require_csrf), Depends(require_roles(UserRole.ADMIN))],
)
async def process_document_version(
    document_id: UUID,
    version_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProcessVersionResponse:
    row = (
        await session.execute(
            select(DocumentVersion, IngestionJob)
            .join(IngestionJob, IngestionJob.document_version_id == DocumentVersion.id)
            .where(
                DocumentVersion.id == version_id,
                DocumentVersion.document_id == document_id,
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    _, job = row
    job_id = job.id
    await session.rollback()
    settings = cast(Settings, request.app.state.settings)
    database = cast(Database, request.app.state.database)
    provider = create_embedding_provider(settings, database)
    try:
        result = await IngestionPipeline(
            database=database,
            embedding_provider=provider,
            storage_root=Path(settings.document_storage_path),
            pdf_parser=PdfParser(
                max_bytes=settings.document_max_pdf_bytes,
                max_pages=settings.document_max_pdf_pages,
                max_text_bytes=settings.document_max_extracted_text_bytes,
            ),
        ).run(job_id)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "ingestion_failed", "message": str(error)},
        ) from error
    finally:
        await provider.close()
    return ProcessVersionResponse(
        document_id=document_id,
        version_id=version_id,
        job_id=job_id,
        status="ready",
        chunk_count=result.chunk_count,
        reused=result.reused,
    )


@router.post(
    "/{document_id}/publish",
    response_model=DocumentResponse,
    dependencies=[Depends(require_csrf), Depends(require_roles(UserRole.ADMIN))],
)
async def publish_document(
    document_id: UUID,
    payload: PublishRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentResponse:
    try:
        result = await DocumentLifecycleService().publish(
            session,
            document_id=document_id,
            version_id=payload.version_id,
            expected_version=payload.expected_version,
            now=datetime.now(UTC),
        )
        await session.commit()
        await session.refresh(result.document)
    except (DocumentLifecycleNotFoundError, DocumentLifecycleConflictError) as error:
        await session.rollback()
        raise _lifecycle_error(error) from error
    return await _document_response(session, result.document)


@router.post(
    "/{document_id}/revoke",
    response_model=DocumentResponse,
    dependencies=[Depends(require_csrf), Depends(require_roles(UserRole.ADMIN))],
)
async def revoke_document(
    document_id: UUID,
    payload: RevokeRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentResponse:
    try:
        result = await DocumentLifecycleService().revoke(
            session,
            document_id=document_id,
            expected_version=payload.expected_version,
        )
        await session.commit()
        await session.refresh(result.document)
    except (DocumentLifecycleNotFoundError, DocumentLifecycleConflictError) as error:
        await session.rollback()
        raise _lifecycle_error(error) from error
    return await _document_response(session, result.document)


@router.put(
    "/{document_id}/acl",
    response_model=DocumentResponse,
    dependencies=[Depends(require_csrf), Depends(require_roles(UserRole.ADMIN))],
)
async def replace_document_acl(
    document_id: UUID,
    payload: ReplaceAclRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentResponse:
    try:
        result = await DocumentLifecycleService().replace_acl(
            session,
            document_id=document_id,
            expected_version=payload.expected_version,
            visibility=payload.visibility,
            department_id=payload.department_id,
            granted_department_ids=set(payload.granted_department_ids),
        )
        await session.commit()
        await session.refresh(result.document)
    except (DocumentLifecycleNotFoundError, DocumentLifecycleConflictError) as error:
        await session.rollback()
        raise _lifecycle_error(error) from error
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="One or more departments do not exist",
        ) from error
    return await _document_response(session, result.document)


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
