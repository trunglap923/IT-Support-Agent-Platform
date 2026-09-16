"""Bounded PDF storage with server-owned paths and draft previews."""

from __future__ import annotations

import hashlib
import os
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO
from uuid import UUID, uuid4

from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, DocumentVersion, DocumentVisibility, IngestionJob
from app.rag.ingestion.pdf_parser import ExtractedPdf, PdfExtractionError, PdfParser
from app.repositories.documents import DocumentRepository

PDF_MEDIA_TYPE = "application/pdf"
UPLOAD_CHUNK_BYTES = 64 * 1024


class UploadMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_key: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    title: str = Field(min_length=1, max_length=240)
    version_label: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$", max_length=40)
    authority: str = Field(min_length=1, max_length=80)
    language: str = Field(default="vi", pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$", max_length=20)
    visibility: DocumentVisibility = DocumentVisibility.COMPANY
    department_id: UUID | None = None
    effective_at: datetime
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_scope_and_dates(self) -> UploadMetadata:
        if (self.visibility is DocumentVisibility.DEPARTMENT) != (self.department_id is not None):
            raise ValueError("department visibility requires exactly one department_id")
        if self.expires_at is not None and self.expires_at <= self.effective_at:
            raise ValueError("expires_at must be later than effective_at")
        return self


class VersionUploadMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_label: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$", max_length=40)
    authority: str = Field(min_length=1, max_length=80)
    language: str = Field(default="vi", pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$", max_length=20)
    effective_at: datetime
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> VersionUploadMetadata:
        if self.expires_at is not None and self.expires_at <= self.effective_at:
            raise ValueError("expires_at must be later than effective_at")
        return self


class DocumentUploadError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class PreviewPage:
    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class DocumentPreview:
    byte_size: int
    parser_version: str
    pages: tuple[PreviewPage, ...]


@dataclass(frozen=True, slots=True)
class DocumentDraft:
    document: Document
    version: DocumentVersion
    job: IngestionJob
    preview: DocumentPreview


class DocumentUploadService:
    def __init__(
        self,
        *,
        storage_root: Path,
        max_pdf_bytes: int,
        max_pdf_pages: int,
        max_extracted_text_bytes: int,
    ) -> None:
        self._storage_root = storage_root.resolve()
        self._max_pdf_bytes = max_pdf_bytes
        self._parser = PdfParser(
            max_bytes=max_pdf_bytes,
            max_pages=max_pdf_pages,
            max_text_bytes=max_extracted_text_bytes,
        )

    async def create_draft(
        self,
        session: AsyncSession,
        *,
        upload: UploadFile,
        metadata: UploadMetadata,
    ) -> DocumentDraft:
        if upload.content_type != PDF_MEDIA_TYPE:
            raise DocumentUploadError("unsupported_media_type", "Only application/pdf is allowed")
        if (
            await DocumentRepository().get_by_key(session, document_key=metadata.document_key)
            is not None
        ):
            raise DocumentUploadError("document_key_conflict", "Document key already exists")

        storage_key = self._new_storage_key()
        final_path = self.resolve_storage_key(storage_key)
        temporary_path = final_path.with_suffix(".part")
        final_path.parent.mkdir(parents=True, exist_ok=True)
        checksum = hashlib.sha256()
        size = 0
        try:
            with temporary_path.open("xb") as destination:
                size = await self._copy_bounded(upload, destination, checksum)
                destination.flush()
                os.fsync(destination.fileno())
            os.replace(temporary_path, final_path)
            extracted = self._parser.parse(final_path)
            identity_hash = self._identity_hash(metadata, checksum.hexdigest())
            document, version, job = await DocumentRepository().create_draft(
                session,
                document_key=metadata.document_key,
                title=metadata.title.strip(),
                visibility=metadata.visibility,
                department_id=metadata.department_id,
                version_label=metadata.version_label,
                authority=metadata.authority.strip(),
                language=metadata.language,
                media_type=PDF_MEDIA_TYPE,
                source_checksum=checksum.hexdigest(),
                storage_key=storage_key,
                effective_at=metadata.effective_at,
                expires_at=metadata.expires_at,
                identity_hash=identity_hash,
            )
            return DocumentDraft(
                document=document,
                version=version,
                job=job,
                preview=self._preview(extracted, size=size),
            )
        except PdfExtractionError as error:
            self._unlink(temporary_path)
            self._unlink(final_path)
            raise DocumentUploadError(error.code.value, str(error)) from error
        except Exception:
            self._unlink(temporary_path)
            self._unlink(final_path)
            raise
        finally:
            await upload.close()

    async def preview(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        version_id: UUID,
    ) -> DocumentPreview | None:
        version = await session.scalar(
            select(DocumentVersion).where(
                DocumentVersion.id == version_id,
                DocumentVersion.document_id == document_id,
            )
        )
        if version is None:
            return None
        extracted = self._parser.parse(self.resolve_storage_key(version.storage_key))
        return self._preview(extracted, size=extracted.byte_size)

    async def create_version(
        self,
        session: AsyncSession,
        *,
        document_id: UUID,
        upload: UploadFile,
        metadata: VersionUploadMetadata,
    ) -> DocumentDraft:
        if upload.content_type != PDF_MEDIA_TYPE:
            raise DocumentUploadError("unsupported_media_type", "Only application/pdf is allowed")
        document = await session.get(Document, document_id)
        if document is None:
            raise DocumentUploadError("document_not_found", "Document was not found")

        storage_key = self._new_storage_key()
        final_path = self.resolve_storage_key(storage_key)
        temporary_path = final_path.with_suffix(".part")
        final_path.parent.mkdir(parents=True, exist_ok=True)
        checksum = hashlib.sha256()
        size = 0
        try:
            with temporary_path.open("xb") as destination:
                size = await self._copy_bounded(upload, destination, checksum)
                destination.flush()
                os.fsync(destination.fileno())
            os.replace(temporary_path, final_path)
            extracted = self._parser.parse(final_path)
            identity_payload = (
                f"{document.document_key}\0{metadata.version_label}\0{checksum.hexdigest()}"
            )
            version, job = await DocumentRepository().create_version(
                session,
                document=document,
                version_label=metadata.version_label,
                authority=metadata.authority.strip(),
                language=metadata.language,
                media_type=PDF_MEDIA_TYPE,
                source_checksum=checksum.hexdigest(),
                storage_key=storage_key,
                effective_at=metadata.effective_at,
                expires_at=metadata.expires_at,
                identity_hash=hashlib.sha256(identity_payload.encode()).hexdigest(),
            )
            return DocumentDraft(
                document=document,
                version=version,
                job=job,
                preview=self._preview(extracted, size=size),
            )
        except PdfExtractionError as error:
            self._unlink(temporary_path)
            self._unlink(final_path)
            raise DocumentUploadError(error.code.value, str(error)) from error
        except Exception:
            self._unlink(temporary_path)
            self._unlink(final_path)
            raise
        finally:
            await upload.close()

    def resolve_storage_key(self, storage_key: str) -> Path:
        candidate = (self._storage_root / storage_key).resolve()
        if not candidate.is_relative_to(self._storage_root):
            raise DocumentUploadError("invalid_storage_key", "Storage key escapes document root")
        return candidate

    async def _copy_bounded(
        self,
        upload: UploadFile,
        destination: BinaryIO,
        checksum: Any,
    ) -> int:
        size = 0
        while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
            size += len(chunk)
            if size > self._max_pdf_bytes:
                raise DocumentUploadError("pdf_too_large", "PDF exceeds the upload size limit")
            checksum.update(chunk)
            destination.write(chunk)
        if size == 0:
            raise DocumentUploadError("empty_upload", "Uploaded PDF is empty")
        return size

    def _new_storage_key(self) -> str:
        identifier = uuid4().hex
        return f"uploads/{identifier[:2]}/{identifier}.pdf"

    @staticmethod
    def _identity_hash(metadata: UploadMetadata, checksum: str) -> str:
        payload = f"{metadata.document_key}\0{metadata.version_label}\0{checksum}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def delete_storage_key(self, storage_key: str) -> None:
        self._unlink(self.resolve_storage_key(storage_key))

    @staticmethod
    def _preview(extracted: ExtractedPdf, *, size: int) -> DocumentPreview:
        return DocumentPreview(
            byte_size=size,
            parser_version=extracted.parser_version,
            pages=tuple(
                PreviewPage(page_number=page.page_number, text=page.text)
                for page in extracted.pages
            ),
        )

    @staticmethod
    def _unlink(path: Path) -> None:
        with suppress(FileNotFoundError):
            path.unlink()
