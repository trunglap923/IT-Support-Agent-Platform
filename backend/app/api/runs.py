"""Owner-scoped run snapshots and persisted Server-Sent Events."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth.csrf import require_csrf
from app.auth.principal import Principal
from app.config import Settings
from app.db import Database
from app.db.models import AgentRun, RunEvent, RunStatus
from app.dependencies import CurrentPrincipal, DatabaseSession, get_database
from app.repositories.runs import RunRepository
from app.services.conversations.cancellation import RunCancellationService
from app.services.conversations.run_state import (
    TERMINAL_RUN_STATUSES,
    InvalidRunTransitionError,
    RunNotFoundError,
    RunVersionConflictError,
)

router = APIRouter(prefix="/runs", tags=["runs"])


class RunResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    status: RunStatus
    outcome: str | None
    version: int
    error_code: str | None


class CancelRunRequest(BaseModel):
    expected_version: int = Field(ge=1)


def run_response(run: AgentRun) -> RunResponse:
    return RunResponse(
        id=run.id,
        conversation_id=run.conversation_id,
        status=run.status,
        outcome=run.outcome,
        version=run.version,
        error_code=run.error_code,
    )


def resolve_event_cursor(last_event_id: str | None, after_sequence: int) -> int:
    if last_event_id is None:
        return after_sequence
    try:
        header_cursor = int(last_event_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Last-Event-ID must be a non-negative integer",
        ) from error
    if header_cursor < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Last-Event-ID must be a non-negative integer",
        )
    return max(header_cursor, after_sequence)


def encode_sse_event(event: RunEvent) -> str:
    data: dict[str, Any] = {
        "sequence": event.sequence,
        "run_id": str(event.run_id),
        "type": event.type,
        "timestamp": event.created_at.isoformat(),
        "payload": event.safe_payload,
    }
    return (
        f"id: {event.sequence}\n"
        f"event: {event.type}\n"
        f"data: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"
    )


def encode_sse_heartbeat() -> str:
    return ": heartbeat\n\n"


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: UUID, principal: CurrentPrincipal, request: Request) -> RunResponse:
    database = get_database(request)
    async with database.session() as session:
        run = await RunRepository().get_owned(
            session,
            run_id=run_id,
            actor_id=principal.user_id,
        )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run was not found")
    return run_response(run)


@router.post(
    "/{run_id}/cancel",
    response_model=RunResponse,
    dependencies=[Depends(require_csrf)],
)
async def cancel_run(
    run_id: UUID,
    payload: CancelRunRequest,
    principal: CurrentPrincipal,
    session: DatabaseSession,
) -> RunResponse:
    try:
        transition = await RunCancellationService().cancel_owned(
            session,
            run_id=run_id,
            actor_id=principal.user_id,
            expected_version=payload.expected_version,
        )
        await session.commit()
    except RunNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run was not found"
        ) from error
    except (InvalidRunTransitionError, RunVersionConflictError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return run_response(transition.run)


async def persisted_event_stream(
    *,
    request: Request,
    database: Database,
    principal: Principal,
    run_id: UUID,
    cursor: int,
    poll_interval_seconds: float,
    heartbeat_seconds: float,
) -> AsyncIterator[str]:
    repository = RunRepository()
    last_heartbeat = time.monotonic()
    while not await request.is_disconnected():
        async with database.session() as session:
            run = await repository.get_owned(
                session,
                run_id=run_id,
                actor_id=principal.user_id,
            )
            events = await repository.list_events_after_owned(
                session,
                run_id=run_id,
                actor_id=principal.user_id,
                after_sequence=cursor,
            )
        if run is None:
            return
        for event in events:
            cursor = event.sequence
            yield encode_sse_event(event)
        if run.status in TERMINAL_RUN_STATUSES and len(events) < 100:
            return
        now = time.monotonic()
        if now - last_heartbeat >= heartbeat_seconds:
            yield encode_sse_heartbeat()
            last_heartbeat = now
        await asyncio.sleep(poll_interval_seconds)


@router.get("/{run_id}/events", response_class=StreamingResponse)
async def stream_run_events(
    run_id: UUID,
    request: Request,
    principal: CurrentPrincipal,
    after_sequence: Annotated[int, Query(ge=0)] = 0,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    database = get_database(request)
    repository = RunRepository()
    async with database.session() as session:
        run = await repository.get_owned(
            session,
            run_id=run_id,
            actor_id=principal.user_id,
        )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run was not found")

    settings = cast(Settings, request.app.state.settings)
    cursor = resolve_event_cursor(last_event_id, after_sequence)
    return StreamingResponse(
        persisted_event_stream(
            request=request,
            database=database,
            principal=principal,
            run_id=run_id,
            cursor=cursor,
            poll_interval_seconds=settings.sse_poll_interval_seconds,
            heartbeat_seconds=settings.sse_heartbeat_seconds,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
