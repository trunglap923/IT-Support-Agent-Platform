"""SQLAlchemy models introduced by feature migrations."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(StrEnum):
    EMPLOYEE = "employee"
    IT = "it"
    ADMIN = "admin"


class RunKind(StrEnum):
    CHAT = "chat"
    MANUAL_TICKET = "manual_ticket"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    RESUME_QUEUED = "resume_queued"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DocumentVisibility(StrEnum):
    COMPANY = "company"
    DEPARTMENT = "department"
    IT_ONLY = "it_only"


class DocumentVersionStatus(StrEnum):
    DRAFT = "draft"
    PROCESSING = "processing"
    READY = "ready"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class IngestionJobStatus(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class UsageStatus(StrEnum):
    RESERVED = "reserved"
    COMPLETED = "completed"
    UNKNOWN = "unknown"


class ServiceHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class ServiceFaultMode(StrEnum):
    NONE = "none"
    TIMEOUT = "timeout"
    ERROR = "error"


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class TicketSeverity(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class TicketIssueType(StrEnum):
    VPN = "vpn"
    DOCKER = "docker"
    GITLAB = "gitlab"
    OTHER = "other"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    EXPIRED = "expired"


class MemoryExtractionStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    DISCARDED = "discarded"
    FAILED = "failed"


class MemoryCandidateStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EXPIRED = "expired"


USER_ROLE_TYPE = Enum(
    UserRole,
    name="user_role",
    values_callable=lambda values: [value.value for value in values],
)
RUN_KIND_TYPE = Enum(
    RunKind,
    name="run_kind",
    native_enum=False,
    create_constraint=True,
    values_callable=lambda values: [value.value for value in values],
)
RUN_STATUS_TYPE = Enum(
    RunStatus,
    name="run_status",
    native_enum=False,
    create_constraint=True,
    values_callable=lambda values: [value.value for value in values],
)
DOCUMENT_VISIBILITY_TYPE = Enum(
    DocumentVisibility,
    name="document_visibility",
    native_enum=False,
    create_constraint=True,
    values_callable=lambda values: [value.value for value in values],
)
DOCUMENT_VERSION_STATUS_TYPE = Enum(
    DocumentVersionStatus,
    name="document_version_status",
    native_enum=False,
    create_constraint=True,
    values_callable=lambda values: [value.value for value in values],
)
INGESTION_JOB_STATUS_TYPE = Enum(
    IngestionJobStatus,
    name="ingestion_job_status",
    native_enum=False,
    create_constraint=True,
    values_callable=lambda values: [value.value for value in values],
)


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list[User]] = relationship(back_populates="department")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("email = lower(email)", name="email_lowercase"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(USER_ROLE_TYPE)
    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    memory_epoch: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    department: Mapped[Department] = relationship(back_populates="users")
    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="sessions")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "(visibility = 'department') = (department_id IS NOT NULL)",
            name="department_scope_matches_visibility",
        ),
        ForeignKeyConstraint(
            ["current_version_id", "id"],
            ["document_versions.id", "document_versions.document_id"],
            name="fk_documents_current_version_owner",
            use_alter=True,
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_key: Mapped[str] = mapped_column(String(120), unique=True)
    title: Mapped[str] = mapped_column(String(240))
    visibility: Mapped[DocumentVisibility] = mapped_column(DOCUMENT_VISIBILITY_TYPE)
    department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    current_version_id: Mapped[UUID | None] = mapped_column(index=True)
    access_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_label", name="uq_document_version_label"),
        UniqueConstraint("id", "document_id", name="uq_document_versions_id_document"),
        CheckConstraint("char_length(source_checksum) = 64", name="source_checksum_length"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    version_label: Mapped[str] = mapped_column(String(40))
    status: Mapped[DocumentVersionStatus] = mapped_column(
        DOCUMENT_VERSION_STATUS_TYPE, default=DocumentVersionStatus.DRAFT
    )
    authority: Mapped[str] = mapped_column(String(80))
    language: Mapped[str] = mapped_column(String(20))
    media_type: Mapped[str] = mapped_column(String(100))
    source_checksum: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(500))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parser_version: Mapped[str | None] = mapped_column(String(80))
    chunker_version: Mapped[str | None] = mapped_column(String(80))
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentAcl(Base):
    __tablename__ = "document_acl"
    __table_args__ = (
        UniqueConstraint("document_id", "department_id", name="uq_document_acl_department"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        UniqueConstraint("document_version_id", "identity_hash", name="uq_ingestion_job_identity"),
        CheckConstraint("progress >= 0 AND progress <= 100", name="progress_range"),
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    identity_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[IngestionJobStatus] = mapped_column(
        INGESTION_JOB_STATUS_TYPE, default=IngestionJobStatus.DRAFT
    )
    stage: Mapped[str] = mapped_column(String(40), default="created", server_default="created")
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_detail: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UsageLedgerEntry(Base):
    __tablename__ = "usage_ledger"
    __table_args__ = (
        CheckConstraint("reserved_input_tokens > 0", name="reserved_tokens_positive"),
        CheckConstraint("reserved_output_tokens >= 0", name="reserved_output_tokens_non_negative"),
        CheckConstraint("reserved_cost_usd >= 0", name="reserved_cost_non_negative"),
        CheckConstraint(
            "actual_cost_usd IS NULL OR actual_cost_usd >= 0", name="actual_cost_non_negative"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    operation_id: Mapped[str] = mapped_column(String(120), unique=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(120))
    price_version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), index=True)
    reserved_input_tokens: Mapped[int] = mapped_column(Integer)
    actual_input_tokens: Mapped[int | None] = mapped_column(Integer)
    reserved_output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    actual_output_tokens: Mapped[int | None] = mapped_column(Integer)
    reserved_cost_usd: Mapped[Decimal] = mapped_column(Numeric(14, 8))
    actual_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 8))
    provider_request_id: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("version_id", "ordinal", name="uq_document_chunk_ordinal"),
        UniqueConstraint("version_id", "content_hash", name="uq_document_chunk_content_hash"),
        CheckConstraint("ordinal >= 0", name="ordinal_non_negative"),
        CheckConstraint("token_count > 0 AND token_count <= 800", name="token_count_range"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    version_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(240))
    source_path: Mapped[str] = mapped_column(String(500))
    source_token_start: Mapped[int] = mapped_column(Integer)
    source_token_end: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    embedding_model: Mapped[str] = mapped_column(String(120))
    embedding_dimensions: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float]] = mapped_column(VECTOR(1536))
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', content)", persisted=True),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("id", "owner_id", name="uq_conversations_id_owner_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    issue_state: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "actor_id"],
            ["conversations.id", "conversations.owner_id"],
            name="fk_agent_runs_conversation_actor",
            ondelete="CASCADE",
        ),
        UniqueConstraint("actor_id", "client_request_id", name="uq_agent_runs_actor_request"),
        CheckConstraint(
            "(status IN ('completed', 'failed', 'cancelled')) = (finished_at IS NOT NULL)",
            name="terminal_run_has_finished_at",
        ),
        Index(
            "uq_agent_runs_active_conversation",
            "conversation_id",
            unique=True,
            postgresql_where=text(
                "status IN ('queued', 'running', 'waiting_approval', 'resume_queued')"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column()
    actor_id: Mapped[UUID] = mapped_column(index=True)
    kind: Mapped[RunKind] = mapped_column(RUN_KIND_TYPE)
    client_request_id: Mapped[str] = mapped_column(String(80))
    input_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[RunStatus] = mapped_column(RUN_STATUS_TYPE, index=True)
    outcome: Mapped[str | None] = mapped_column(String(50))
    checkpoint_thread_id: Mapped[str] = mapped_column(String(80), unique=True)
    prompt_version: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(120))
    counters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    execution_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_run_events_run_sequence"),
        UniqueConstraint("run_id", "dedupe_key", name="uq_run_events_run_dedupe_key"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    dedupe_key: Mapped[str | None] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(80))
    safe_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'executed', 'expired')",
            name="approval_status_allowlist",
        ),
        CheckConstraint("length(arguments_hash) = 64", name="approval_hash_length"),
        Index("ix_approval_owner_status_expiry", "owner_id", "status", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    action_id: Mapped[str] = mapped_column(String(120), unique=True)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tool_name: Mapped[str] = mapped_column(String(80))
    canonical_args: Mapped[dict[str, Any]] = mapped_column(JSONB)
    arguments_hash: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    decided_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(String(50))
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemoryConsentEvent(Base):
    __tablename__ = "memory_consent_events"
    __table_args__ = (CheckConstraint("epoch >= 0", name="memory_consent_epoch_non_negative"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean)
    epoch: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemoryExtractionJob(Base):
    __tablename__ = "memory_extraction_jobs"
    __table_args__ = (
        CheckConstraint("captured_epoch >= 0", name="memory_job_epoch_non_negative"),
        CheckConstraint(
            "status IN ('pending', 'completed', 'discarded', 'failed')",
            name="memory_job_status_allowlist",
        ),
        UniqueConstraint("source_message_id", name="uq_memory_job_source_message"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), index=True
    )
    source_message_id: Mapped[UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    captured_epoch: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MemoryCandidate(Base):
    __tablename__ = "memory_candidates"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('profile', 'preference', 'device')",
            name="memory_candidate_kind_allowlist",
        ),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected', 'expired')",
            name="memory_candidate_status_allowlist",
        ),
        UniqueConstraint("job_id", "kind", "key", name="uq_memory_candidate_job_key"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("memory_extraction_jobs.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    key: Mapped[str] = mapped_column(String(40))
    value: Mapped[str] = mapped_column(String(240))
    evidence: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MemoryFact(Base):
    __tablename__ = "memory_facts"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('profile', 'preference', 'device')", name="memory_fact_kind_allowlist"
        ),
        CheckConstraint("scope IN ('global', 'device')", name="memory_fact_scope_allowlist"),
        CheckConstraint(
            "(scope = 'device') = (device_id IS NOT NULL)",
            name="memory_fact_device_scope_matches",
        ),
        Index(
            "uq_memory_fact_global_active",
            "owner_id",
            "kind",
            "key",
            unique=True,
            postgresql_where=text("scope = 'global' AND deleted_at IS NULL"),
        ),
        Index(
            "uq_memory_fact_device_active",
            "owner_id",
            "device_id",
            "kind",
            "key",
            unique=True,
            postgresql_where=text("scope = 'device' AND deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("memory_candidates.id", ondelete="RESTRICT"), unique=True
    )
    source_conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    key: Mapped[str] = mapped_column(String(40))
    value: Mapped[str] = mapped_column(String(240))
    scope: Mapped[str] = mapped_column(String(20), default="global", server_default="global")
    device_id: Mapped[UUID | None] = mapped_column(index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ServiceState(Base):
    __tablename__ = "service_states"
    __table_args__ = (
        CheckConstraint("service_id IN ('vpn', 'registry', 'gitlab')", name="service_id_allowlist"),
        CheckConstraint(
            "status IN ('healthy', 'degraded', 'down', 'unknown')",
            name="service_status_allowlist",
        ),
        CheckConstraint(
            "fault_mode IN ('none', 'timeout', 'error')", name="service_fault_allowlist"
        ),
    )

    service_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(String(500))
    fault_mode: Mapped[str] = mapped_column(String(20), default="none", server_default="none")
    updated_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "issue_type IN ('vpn', 'docker', 'gitlab', 'other')",
            name="ticket_issue_type_allowlist",
        ),
        CheckConstraint("severity IN ('low', 'normal', 'high')", name="ticket_severity_allowlist"),
        CheckConstraint(
            "status IN ('open', 'in_progress', 'resolved')", name="ticket_status_allowlist"
        ),
        CheckConstraint(
            "status != 'resolved' OR resolution_note IS NOT NULL",
            name="resolved_ticket_has_note",
        ),
        Index("ix_tickets_owner_status_created", "owner_id", "status", "created_at"),
        Index("ix_tickets_department_status_updated", "department_id", "status", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    display_key: Mapped[str] = mapped_column(String(30), unique=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    department_id: Mapped[UUID] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"))
    device_id: Mapped[UUID | None] = mapped_column()
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL")
    )
    approval_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("approval_requests.id", ondelete="RESTRICT"), unique=True
    )
    source: Mapped[str] = mapped_column(String(20), default="seed", server_default="seed")
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    issue_type: Mapped[str] = mapped_column(String(20))
    severity: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="open", server_default="open")
    resolution_note: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TicketEvent(Base):
    __tablename__ = "ticket_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    type: Mapped[str] = mapped_column(String(60))
    safe_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
