"""Trusted execution context for the internal MCP subprocess."""

from __future__ import annotations

import os
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select

from app.auth.principal import Principal
from app.db import Database
from app.db.models import AgentRun, Department, User

ACTOR_ENV = "MCP_ACTOR_ID"
RUN_ENV = "MCP_RUN_ID"
DATABASE_ENV = "MCP_DATABASE_URL"


class MCPContextError(RuntimeError):
    """Raised when subprocess context cannot be trusted."""


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    actor_id: UUID
    run_id: UUID
    database_url: str


def load_execution_context() -> ExecutionContext:
    try:
        actor_id = UUID(os.environ[ACTOR_ENV])
        run_id = UUID(os.environ[RUN_ENV])
        database_url = os.environ[DATABASE_ENV]
    except (KeyError, ValueError) as exc:
        raise MCPContextError("MCP execution context is missing or invalid") from exc
    if not database_url.startswith("postgresql+asyncpg://"):
        raise MCPContextError("MCP database transport is invalid")
    return ExecutionContext(actor_id=actor_id, run_id=run_id, database_url=database_url)


async def load_current_principal(database: Database, *, context: ExecutionContext) -> Principal:
    """Revalidate run ownership and the active user on every tool call."""

    async with database.session() as session:
        row = (
            await session.execute(
                select(AgentRun, User, Department)
                .join(User, User.id == AgentRun.actor_id)
                .join(Department, Department.id == User.department_id)
                .where(
                    AgentRun.id == context.run_id,
                    AgentRun.actor_id == context.actor_id,
                    User.active.is_(True),
                )
            )
        ).one_or_none()
    if row is None:
        raise MCPContextError("Actor is not allowed to access this run")
    run, user, department = row
    return Principal(
        user_id=user.id,
        session_id=run.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        department_id=department.id,
        department_key=department.key,
    )
