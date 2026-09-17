"""Seed the committed IT corpus through ingestion and publication lifecycle."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select

from app.db import Database
from app.db.models import (
    Department,
    Document,
    DocumentAcl,
    DocumentChunk,
    DocumentVersion,
    DocumentVersionStatus,
    DocumentVisibility,
    IngestionJob,
    IngestionJobStatus,
)
from app.providers.embeddings import FakeEmbeddingProvider
from app.rag.chunking.splitter import CHUNKER_VERSION
from app.rag.ingestion.markdown_parser import MARKDOWN_PARSER_VERSION
from app.rag.ingestion.pipeline import IngestionPipeline
from app.services.documents.lifecycle import DocumentLifecycleService

_MANIFEST_NAME = "documents.json"
_MEDIA_TYPE = "text/markdown"
_STORAGE_PREFIX = "seed-corpus"


@dataclass(frozen=True, slots=True)
class DemoCorpusVersionSpec:
    document_key: str
    version_label: str
    title: str
    source_path: Path
    storage_key: str
    authority: str
    language: str
    visibility: DocumentVisibility
    department_key: str | None
    effective_at: datetime
    expires_at: datetime | None
    checksum: str


@dataclass(frozen=True, slots=True)
class DemoKnowledgeSeedResult:
    document_count: int
    version_count: int
    published_count: int
    chunk_count: int
    reused_jobs: int


@dataclass(frozen=True, slots=True)
class DemoKnowledgeSeedPlan:
    created: int
    updated: int
    unchanged: int
    document_count: int
    version_count: int

    @property
    def total(self) -> int:
        return self.created + self.updated + self.unchanged


@dataclass(frozen=True, slots=True)
class _IngestionTarget:
    job_id: UUID
    force: bool
    preserve_version_status: bool


def _parse_timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"Corpus {field} must be an ISO-8601 string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Corpus {field} must include a timezone")
    return parsed


def _required_string(item: dict[str, Any], field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"Corpus {field} must be a non-empty normalized string")
    return value


def load_demo_corpus(data_root: Path) -> tuple[DemoCorpusVersionSpec, ...]:
    """Load and checksum the self-authored manifest without trusting file paths."""

    resolved_root = data_root.resolve()
    manifest_path = resolved_root / "manifests" / _MANIFEST_NAME
    knowledge_root = (resolved_root / "knowledge").resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Demo corpus manifest must be an object")
    snapshot = payload.get("snapshot")
    if not isinstance(snapshot, dict) or snapshot.get("license_policy") != "self-authored-only":
        raise ValueError("Demo corpus must use the self-authored-only license policy")
    raw_documents = payload.get("documents")
    if not isinstance(raw_documents, list) or not raw_documents:
        raise ValueError("Demo corpus manifest must contain documents")

    specs: list[DemoCorpusVersionSpec] = []
    identities: set[tuple[str, str]] = set()
    document_scopes: dict[str, tuple[DocumentVisibility, str | None]] = {}
    for raw in raw_documents:
        if not isinstance(raw, dict):
            raise ValueError("Corpus document entry must be an object")
        document_key = _required_string(raw, "document_key")
        version_label = _required_string(raw, "version_label")
        identity = (document_key, version_label)
        if identity in identities:
            raise ValueError(f"Duplicate corpus identity: {document_key}:{version_label}")
        identities.add(identity)
        if raw.get("media_type") != _MEDIA_TYPE:
            raise ValueError(f"Unsupported corpus media type: {raw.get('media_type')}")
        source = raw.get("source")
        if not isinstance(source, dict) or source.get("kind") != "self-authored":
            raise ValueError(f"Corpus source must be self-authored: {document_key}:{version_label}")
        if raw.get("license") != "CC-BY-4.0":
            raise ValueError(f"Corpus license must be CC-BY-4.0: {document_key}:{version_label}")

        relative_path = Path(_required_string(raw, "path"))
        source_path = (knowledge_root / relative_path).resolve()
        if not source_path.is_relative_to(knowledge_root) or not source_path.is_file():
            raise ValueError(f"Corpus source path is invalid: {relative_path}")
        expected_checksum = _required_string(raw, "checksum")
        if not expected_checksum.startswith("sha256:"):
            raise ValueError(f"Corpus checksum is invalid: {relative_path}")
        checksum = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if expected_checksum != f"sha256:{checksum}":
            raise ValueError(f"Corpus checksum mismatch: {relative_path}")

        try:
            visibility = DocumentVisibility(_required_string(raw, "visibility"))
        except ValueError as error:
            raise ValueError(f"Invalid corpus visibility: {raw.get('visibility')}") from error
        department_value = raw.get("department_key")
        if department_value is not None and not isinstance(department_value, str):
            raise ValueError(f"Invalid corpus department: {document_key}:{version_label}")
        department_key = department_value
        if (visibility is DocumentVisibility.DEPARTMENT) != (department_key is not None):
            raise ValueError(f"Invalid corpus department scope: {document_key}:{version_label}")
        scope = (visibility, department_key)
        previous_scope = document_scopes.setdefault(document_key, scope)
        if previous_scope != scope:
            raise ValueError(f"Corpus versions disagree on scope: {document_key}")

        effective_at = _parse_timestamp(raw.get("effective_at"), field="effective_at")
        expires_raw = raw.get("expires_at")
        expires_at = (
            _parse_timestamp(expires_raw, field="expires_at") if expires_raw is not None else None
        )
        if expires_at is not None and expires_at <= effective_at:
            raise ValueError(f"Corpus expiry is invalid: {document_key}:{version_label}")
        storage_key = (_STORAGE_PREFIX + "/" + relative_path.as_posix()).strip("/")
        specs.append(
            DemoCorpusVersionSpec(
                document_key=document_key,
                version_label=version_label,
                title=_required_string(raw, "title"),
                source_path=source_path,
                storage_key=storage_key,
                authority=_required_string(raw, "authority"),
                language=_required_string(raw, "language"),
                visibility=visibility,
                department_key=department_key,
                effective_at=effective_at,
                expires_at=expires_at,
                checksum=checksum,
            )
        )
    return tuple(specs)


def _current_versions(
    specs: tuple[DemoCorpusVersionSpec, ...], *, now: datetime
) -> dict[str, DemoCorpusVersionSpec]:
    grouped: dict[str, list[DemoCorpusVersionSpec]] = defaultdict(list)
    for spec in specs:
        grouped[spec.document_key].append(spec)
    current: dict[str, DemoCorpusVersionSpec] = {}
    for document_key, versions in grouped.items():
        eligible = [
            spec
            for spec in versions
            if spec.effective_at <= now and (spec.expires_at is None or spec.expires_at > now)
        ]
        if not eligible:
            raise ValueError(f"Corpus document has no current version: {document_key}")
        current[document_key] = max(
            eligible, key=lambda spec: (spec.effective_at, spec.version_label)
        )
    return current


def _copy_corpus_sources(specs: tuple[DemoCorpusVersionSpec, ...], *, storage_root: Path) -> None:
    resolved_storage = storage_root.resolve()
    for spec in specs:
        destination = (resolved_storage / spec.storage_key).resolve()
        if not destination.is_relative_to(resolved_storage):
            raise ValueError(f"Corpus storage path escapes root: {spec.storage_key}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != spec.checksum:
                raise ValueError(f"Stored corpus checksum mismatch: {spec.storage_key}")
            continue
        temporary = destination.with_suffix(destination.suffix + ".part")
        shutil.copyfile(spec.source_path, temporary)
        temporary.replace(destination)


def _identity_hash(spec: DemoCorpusVersionSpec) -> str:
    value = f"{spec.document_key}\0{spec.version_label}\0{spec.checksum}"
    return hashlib.sha256(value.encode()).hexdigest()


async def plan_published_knowledge(
    database: Database,
    *,
    data_root: Path,
    now: datetime | None = None,
) -> DemoKnowledgeSeedPlan:
    """Validate the corpus and classify version changes without writing DB or storage."""

    selected_now = now or datetime.now(UTC)
    specs = load_demo_corpus(data_root)
    current = _current_versions(specs, now=selected_now)
    document_keys = set(current)
    async with database.session() as session:
        departments = {
            department.key: department for department in await session.scalars(select(Department))
        }
        documents = {
            document.document_key: document
            for document in await session.scalars(
                select(Document).where(Document.document_key.in_(document_keys))
            )
        }
        document_ids = [document.id for document in documents.values()]
        stored_versions = (
            list(
                await session.scalars(
                    select(DocumentVersion).where(DocumentVersion.document_id.in_(document_ids))
                )
            )
            if document_ids
            else []
        )
        versions = {
            (version.document_id, version.version_label): version for version in stored_versions
        }
        version_ids = [version.id for version in stored_versions]
        jobs = {
            job.document_version_id: job
            for job in (
                await session.scalars(
                    select(IngestionJob).where(IngestionJob.document_version_id.in_(version_ids))
                )
                if version_ids
                else []
            )
        }
        acl_document_ids = (
            set(
                await session.scalars(
                    select(DocumentAcl.document_id).where(DocumentAcl.document_id.in_(document_ids))
                )
            )
            if document_ids
            else set()
        )
        chunk_counts = (
            {
                version_id: int(count)
                for version_id, count in (
                    await session.execute(
                        select(DocumentChunk.version_id, func.count(DocumentChunk.id))
                        .where(DocumentChunk.version_id.in_(version_ids))
                        .group_by(DocumentChunk.version_id)
                    )
                ).all()
            }
            if version_ids
            else {}
        )

    counts = {"created": 0, "updated": 0, "unchanged": 0}
    for spec in specs:
        document = documents.get(spec.document_key)
        if document is None:
            counts["created"] += 1
            continue
        if any(
            version.document_id == document.id
            and not version.storage_key.startswith(f"{_STORAGE_PREFIX}/")
            for version in stored_versions
        ):
            raise ValueError(f"Corpus key collides with uploaded document: {spec.document_key}")
        version = versions.get((document.id, spec.version_label))
        if version is None:
            counts["created"] += 1
            continue

        immutable = (
            version.source_checksum,
            version.storage_key,
            version.media_type,
            version.effective_at,
            version.expires_at,
        )
        expected_immutable = (
            spec.checksum,
            spec.storage_key,
            _MEDIA_TYPE,
            spec.effective_at,
            spec.expires_at,
        )
        if immutable != expected_immutable:
            raise ValueError(
                "Published corpus version changed without a version bump: "
                f"{spec.document_key}:{spec.version_label}"
            )

        selected = current[spec.document_key]
        is_current = spec.version_label == selected.version_label
        expected_status = (
            DocumentVersionStatus.PUBLISHED if is_current else DocumentVersionStatus.SUPERSEDED
        )
        job = jobs.get(version.id)
        changed = any(
            (
                version.authority != spec.authority,
                version.language != spec.language,
                version.status is not expected_status,
                version.parser_version != MARKDOWN_PARSER_VERSION,
                version.chunker_version != CHUNKER_VERSION,
                version.embedding_model is None,
                version.embedding_dimensions != 1536,
                job is None,
                job is not None and job.status is not IngestionJobStatus.COMPLETED,
                chunk_counts.get(version.id, 0) == 0,
            )
        )
        if is_current:
            expected_department_id = (
                departments[spec.department_key].id if spec.department_key in departments else None
            )
            changed = changed or any(
                (
                    document.title != spec.title,
                    document.visibility is not spec.visibility,
                    document.department_id != expected_department_id,
                    document.archived,
                    document.current_version_id != version.id,
                    document.id in acl_document_ids,
                )
            )
        counts["updated" if changed else "unchanged"] += 1

    return DemoKnowledgeSeedPlan(
        created=counts["created"],
        updated=counts["updated"],
        unchanged=counts["unchanged"],
        document_count=len(current),
        version_count=len(specs),
    )


async def _prepare_documents(
    database: Database,
    *,
    specs: tuple[DemoCorpusVersionSpec, ...],
    current: dict[str, DemoCorpusVersionSpec],
) -> tuple[_IngestionTarget, ...]:
    async with database.session() as session, session.begin():
        department_keys = {spec.department_key for spec in specs if spec.department_key}
        departments = {
            department.key: department
            for department in await session.scalars(
                select(Department).where(Department.key.in_(department_keys))
            )
        }
        missing_departments = department_keys - departments.keys()
        if missing_departments:
            raise ValueError(
                "Demo departments must be seeded first: " + ", ".join(sorted(missing_departments))
            )

        document_keys = set(current)
        documents = {
            document.document_key: document
            for document in await session.scalars(
                select(Document).where(Document.document_key.in_(document_keys))
            )
        }
        jobs: list[_IngestionTarget] = []
        for document_key in sorted(document_keys):
            selected = current[document_key]
            department_id = (
                departments[selected.department_key].id if selected.department_key else None
            )
            document = documents.get(document_key)
            if document is None:
                document = Document(
                    document_key=document_key,
                    title=selected.title,
                    visibility=selected.visibility,
                    department_id=department_id,
                    archived=False,
                )
                session.add(document)
                await session.flush()
                documents[document_key] = document
            else:
                existing_versions = list(
                    await session.scalars(
                        select(DocumentVersion).where(DocumentVersion.document_id == document.id)
                    )
                )
                if existing_versions and any(
                    not version.storage_key.startswith(f"{_STORAGE_PREFIX}/")
                    for version in existing_versions
                ):
                    raise ValueError(f"Corpus key collides with uploaded document: {document_key}")
                scope_changed = (
                    document.visibility != selected.visibility
                    or document.department_id != department_id
                )
                metadata_changed = scope_changed or document.title != selected.title
                document.title = selected.title
                document.visibility = selected.visibility
                document.department_id = department_id
                if metadata_changed:
                    document.version += 1
                if scope_changed:
                    document.access_version += 1

        versions_by_identity = {
            (version.document_id, version.version_label): version
            for version in await session.scalars(
                select(DocumentVersion).where(
                    DocumentVersion.document_id.in_(
                        [document.id for document in documents.values()]
                    )
                )
            )
        }
        for spec in specs:
            document = documents[spec.document_key]
            version = versions_by_identity.get((document.id, spec.version_label))
            if version is None:
                version = DocumentVersion(
                    document_id=document.id,
                    version_label=spec.version_label,
                    status=DocumentVersionStatus.DRAFT,
                    authority=spec.authority,
                    language=spec.language,
                    media_type=_MEDIA_TYPE,
                    source_checksum=spec.checksum,
                    storage_key=spec.storage_key,
                    effective_at=spec.effective_at,
                    expires_at=spec.expires_at,
                )
                session.add(version)
                await session.flush()
            else:
                immutable = (
                    version.source_checksum,
                    version.storage_key,
                    version.media_type,
                    version.effective_at,
                    version.expires_at,
                )
                expected = (
                    spec.checksum,
                    spec.storage_key,
                    _MEDIA_TYPE,
                    spec.effective_at,
                    spec.expires_at,
                )
                if immutable != expected:
                    raise ValueError(
                        f"Published corpus version changed without a version bump: "
                        f"{spec.document_key}:{spec.version_label}"
                    )
                version.authority = spec.authority
                version.language = spec.language

            identity_hash = _identity_hash(spec)
            job = await session.scalar(
                select(IngestionJob).where(IngestionJob.document_version_id == version.id)
            )
            if job is None:
                job = IngestionJob(
                    document_version_id=version.id,
                    identity_hash=identity_hash,
                    status=IngestionJobStatus.DRAFT,
                )
                session.add(job)
                await session.flush()
            chunk_count = int(
                await session.scalar(
                    select(func.count(DocumentChunk.id)).where(
                        DocumentChunk.version_id == version.id
                    )
                )
                or 0
            )
            force_refresh = job.status is IngestionJobStatus.COMPLETED and any(
                (
                    version.parser_version != MARKDOWN_PARSER_VERSION,
                    version.chunker_version != CHUNKER_VERSION,
                    version.embedding_model is None,
                    version.embedding_dimensions != 1536,
                    chunk_count == 0,
                )
            )
            selected = current[spec.document_key]
            if (
                spec.version_label == selected.version_label
                and job.status is IngestionJobStatus.COMPLETED
                and (
                    document.archived
                    or document.current_version_id != version.id
                    or version.status is not DocumentVersionStatus.PUBLISHED
                )
            ):
                version.status = DocumentVersionStatus.READY
            jobs.append(
                _IngestionTarget(
                    job_id=job.id,
                    force=force_refresh,
                    preserve_version_status=(
                        force_refresh
                        and version.status
                        in {
                            DocumentVersionStatus.PUBLISHED,
                            DocumentVersionStatus.SUPERSEDED,
                        }
                    ),
                )
            )
        return tuple(jobs)


async def _publish_current_versions(
    database: Database,
    *,
    specs: tuple[DemoCorpusVersionSpec, ...],
    current: dict[str, DemoCorpusVersionSpec],
    now: datetime,
) -> None:
    async with database.session() as session, session.begin():
        documents = {
            document.document_key: document
            for document in await session.scalars(
                select(Document).where(Document.document_key.in_(set(current)))
            )
        }
        versions = {
            (document.document_key, version.version_label): version
            for document, version in (
                await session.execute(
                    select(Document, DocumentVersion)
                    .join(DocumentVersion, DocumentVersion.document_id == Document.id)
                    .where(Document.document_key.in_(set(current)))
                )
            ).all()
        }
        lifecycle = DocumentLifecycleService()
        for document_key in sorted(current):
            selected = current[document_key]
            document = documents[document_key]
            desired = versions[(document_key, selected.version_label)]
            if not (
                document.current_version_id == desired.id
                and desired.status is DocumentVersionStatus.PUBLISHED
            ):
                if desired.status is not DocumentVersionStatus.READY:
                    raise ValueError(f"Current corpus version is not ready: {document_key}")
                await lifecycle.publish(
                    session,
                    document_id=document.id,
                    version_id=desired.id,
                    expected_version=document.version,
                    now=now,
                )
            for spec in specs:
                if (
                    spec.document_key != document_key
                    or spec.version_label == selected.version_label
                ):
                    continue
                historical = versions[(document_key, spec.version_label)]
                if historical.status is not DocumentVersionStatus.SUPERSEDED:
                    historical.status = DocumentVersionStatus.SUPERSEDED
            acl_ids = list(
                await session.scalars(
                    select(DocumentAcl.id).where(DocumentAcl.document_id == document.id)
                )
            )
            if acl_ids:
                await session.execute(
                    delete(DocumentAcl).where(DocumentAcl.document_id == document.id)
                )
                document.access_version += 1
                document.version += 1
        await session.flush()


async def seed_published_knowledge(
    database: Database,
    *,
    data_root: Path,
    storage_root: Path,
    now: datetime | None = None,
) -> DemoKnowledgeSeedResult:
    """Validate, ingest with fake embeddings, and publish the committed corpus."""

    selected_now = now or datetime.now(UTC)
    specs = load_demo_corpus(data_root)
    current = _current_versions(specs, now=selected_now)
    _copy_corpus_sources(specs, storage_root=storage_root)
    ingestion_targets = await _prepare_documents(database, specs=specs, current=current)

    provider = FakeEmbeddingProvider(dimensions=1536)
    reused_jobs = 0
    try:
        pipeline = IngestionPipeline(
            database=database,
            embedding_provider=provider,
            storage_root=storage_root,
        )
        for target in ingestion_targets:
            result = await pipeline.run(
                target.job_id,
                force=target.force,
                preserve_version_status=target.preserve_version_status,
            )
            reused_jobs += int(result.reused)
    finally:
        await provider.close()

    await _publish_current_versions(database, specs=specs, current=current, now=selected_now)
    async with database.session() as session:
        chunk_count = int(
            await session.scalar(
                select(func.count(DocumentChunk.id))
                .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
                .join(Document, DocumentVersion.document_id == Document.id)
                .where(Document.document_key.in_(set(current)))
            )
            or 0
        )
    return DemoKnowledgeSeedResult(
        document_count=len(current),
        version_count=len(specs),
        published_count=len(current),
        chunk_count=chunk_count,
        reused_jobs=reused_jobs,
    )
