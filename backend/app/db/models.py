"""SQLAlchemy models introduced by feature migrations."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
