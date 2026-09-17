"""Retryable parse → chunk → embed → store pipeline for draft PDF versions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, func, select

from app.db import Database
from app.db.models import (
    DocumentChunk,
    DocumentVersion,
    DocumentVersionStatus,
    IngestionJob,
    IngestionJobStatus,
)
from app.providers.embeddings import EmbeddingProvider
from app.rag.chunking.splitter import ChunkingConfig, SourceBlock, chunk_blocks
from app.rag.ingestion.markdown_parser import MarkdownParser
from app.rag.ingestion.pdf_parser import PdfExtractionError, PdfParser


class IngestionPipelineError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class IngestionResult:
    job_id: UUID
    version_id: UUID
    chunk_count: int
    reused: bool


class IngestionPipeline:
    def __init__(
        self,
        *,
        database: Database,
        embedding_provider: EmbeddingProvider,
        storage_root: Path,
        pdf_parser: PdfParser | None = None,
        chunking_config: ChunkingConfig | None = None,
        max_attempts: int = 3,
        max_text_bytes: int = 1024 * 1024,
    ) -> None:
        self._database = database
        self._embedding_provider = embedding_provider
        self._storage_root = storage_root.resolve()
        self._pdf_parser = pdf_parser or PdfParser()
        self._chunking_config = chunking_config or ChunkingConfig()
        self._max_attempts = max_attempts
        self._markdown_parser = MarkdownParser(max_bytes=max_text_bytes)

    async def run(self, job_id: UUID) -> IngestionResult:
        async with self._database.session() as session, session.begin():
            job = await session.scalar(
                select(IngestionJob).where(IngestionJob.id == job_id).with_for_update()
            )
            if job is None:
                raise LookupError(f"Unknown ingestion job {job_id}")
            version = await session.get(DocumentVersion, job.document_version_id)
            if version is None:
                raise LookupError(f"Missing document version for ingestion job {job_id}")
            version_id = version.id
            if job.status is IngestionJobStatus.COMPLETED:
                count = await session.scalar(
                    select(func.count(DocumentChunk.id)).where(
                        DocumentChunk.version_id == version.id
                    )
                )
                return IngestionResult(job.id, version.id, int(count or 0), True)
            if job.attempts >= self._max_attempts:
                raise IngestionPipelineError("Ingestion retry limit reached")
            job.attempts += 1
            job.status = IngestionJobStatus.RUNNING
            job.stage = "parse"
            job.progress = 5
            job.error_code = None
            job.error_detail = None
            version.status = DocumentVersionStatus.PROCESSING
            storage_key = version.storage_key
            media_type = version.media_type

        try:
            source_path = self._resolve_storage_key(storage_key)
            parser_version, blocks = self._extract_blocks(
                source_path=source_path,
                storage_key=storage_key,
                media_type=media_type,
            )
            drafts = chunk_blocks(
                version_id=version_id,
                blocks=blocks,
                config=self._chunking_config,
            )
            if not drafts:
                raise IngestionPipelineError("Document did not produce any chunks")
            batch = await self._embedding_provider.embed(
                [draft.content for draft in drafts],
                operation_id=f"ingestion:{job_id}:attempt:{job.attempts}",
            )
            if len(batch.vectors) != len(drafts) or batch.dimensions != 1536:
                raise IngestionPipelineError("Embedding batch shape is invalid for this index")

            async with self._database.session() as session, session.begin():
                locked_job = await session.scalar(
                    select(IngestionJob).where(IngestionJob.id == job_id).with_for_update()
                )
                locked_version = await session.get(DocumentVersion, version_id)
                if locked_job is None or locked_version is None:
                    raise LookupError("Ingestion state disappeared while processing")
                await session.execute(
                    delete(DocumentChunk).where(DocumentChunk.version_id == version_id)
                )
                session.add_all(
                    [
                        DocumentChunk(
                            id=draft.id,
                            version_id=version_id,
                            ordinal=draft.ordinal,
                            page_number=draft.page_number,
                            section=draft.section,
                            source_path=draft.source_path,
                            source_token_start=draft.source_token_start,
                            source_token_end=draft.source_token_end,
                            content=draft.content,
                            token_count=draft.token_count,
                            content_hash=draft.content_hash,
                            embedding_model=batch.model,
                            embedding_dimensions=batch.dimensions,
                            embedding=list(vector),
                        )
                        for draft, vector in zip(drafts, batch.vectors, strict=True)
                    ]
                )
                locked_version.status = DocumentVersionStatus.READY
                locked_version.parser_version = parser_version
                locked_version.chunker_version = self._chunking_config.version
                locked_version.embedding_model = batch.model
                locked_version.embedding_dimensions = batch.dimensions
                locked_job.status = IngestionJobStatus.COMPLETED
                locked_job.stage = "completed"
                locked_job.progress = 100
                locked_job.completed_at = func.now()
            return IngestionResult(job_id, version_id, len(drafts), False)
        except Exception as error:
            await self._record_failure(job_id, version_id, error)
            raise

    def _resolve_storage_key(self, storage_key: str) -> Path:
        candidate = (self._storage_root / storage_key).resolve()
        if not candidate.is_relative_to(self._storage_root):
            raise IngestionPipelineError("Storage key escapes the configured document root")
        return candidate

    def _extract_blocks(
        self,
        *,
        source_path: Path,
        storage_key: str,
        media_type: str,
    ) -> tuple[str, list[SourceBlock]]:
        if media_type == "application/pdf":
            extracted_pdf = self._pdf_parser.parse(source_path)
            return extracted_pdf.parser_version, [
                SourceBlock(
                    text=page.text,
                    page_number=page.page_number,
                    section=None,
                    source_path=storage_key,
                )
                for page in extracted_pdf.pages
                if page.text
            ]
        if media_type != "text/markdown":
            raise IngestionPipelineError(f"Unsupported ingestion media type: {media_type}")
        extracted_markdown = self._markdown_parser.parse(source_path)
        return extracted_markdown.parser_version, [
            SourceBlock(
                text=section.text,
                page_number=None,
                section=section.title,
                source_path=storage_key,
            )
            for section in extracted_markdown.sections
        ]

    async def _record_failure(self, job_id: UUID, version_id: UUID, error: Exception) -> None:
        error_code = (
            error.code.value if isinstance(error, PdfExtractionError) else "ingestion_failed"
        )
        async with self._database.session() as session, session.begin():
            job = await session.get(IngestionJob, job_id)
            version = await session.get(DocumentVersion, version_id)
            if job is not None:
                job.status = IngestionJobStatus.FAILED
                job.stage = "failed"
                job.error_code = error_code
                job.error_detail = str(error)[:500]
            if version is not None:
                version.status = DocumentVersionStatus.FAILED
