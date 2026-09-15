"""Create an idempotent queued run, commit it, then enqueue it."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.db import Database
from app.db.models import AgentRun, Message, RunEvent, RunKind, RunStatus
from app.jobs.dispatch import BrokerUnavailableError, RunDispatcher
from app.repositories.conversations import ConversationRepository
from app.repositories.runs import RunRepository


class ConversationNotFoundError(LookupError):
    pass


class RunRequestConflictError(RuntimeError):
    pass


class ActiveRunConflictError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RunSubmissionResult:
    run_id: UUID
    status: RunStatus
    created: bool
    enqueued: bool
    enqueue_error: str | None = None


def hash_run_input(content: str) -> str:
    return hashlib.sha256(content.strip().encode()).hexdigest()


class RunSubmissionService:
    def __init__(self, database: Database, dispatcher: RunDispatcher) -> None:
        self.database = database
        self.dispatcher = dispatcher
        self.runs = RunRepository()
        self.conversations = ConversationRepository()

    async def submit(
        self,
        *,
        actor_id: UUID,
        conversation_id: UUID,
        content: str,
        client_request_id: str,
        prompt_version: str = "v1",
        model: str = "fake",
    ) -> RunSubmissionResult:
        input_hash = hash_run_input(content)
        replay = await self._find_replay(
            actor_id=actor_id,
            client_request_id=client_request_id,
            input_hash=input_hash,
        )
        if replay is not None:
            return replay

        await self.dispatcher.ensure_available()
        try:
            created = await self._persist_queued_run(
                actor_id=actor_id,
                conversation_id=conversation_id,
                content=content,
                client_request_id=client_request_id,
                input_hash=input_hash,
                prompt_version=prompt_version,
                model=model,
            )
        except IntegrityError as error:
            replay = await self._find_replay(
                actor_id=actor_id,
                client_request_id=client_request_id,
                input_hash=input_hash,
            )
            if replay is not None:
                return replay
            raise ActiveRunConflictError("Conversation already has an active run") from error

        try:
            await self.dispatcher.enqueue_run(created.run_id)
        except BrokerUnavailableError:
            await self._record_enqueue_failure(created.run_id)
            return RunSubmissionResult(
                run_id=created.run_id,
                status=RunStatus.QUEUED,
                created=True,
                enqueued=False,
                enqueue_error="broker_unavailable",
            )
        return created

    async def _find_replay(
        self,
        *,
        actor_id: UUID,
        client_request_id: str,
        input_hash: str,
    ) -> RunSubmissionResult | None:
        async with self.database.session() as session:
            existing = await self.runs.get_by_client_request(
                session,
                actor_id=actor_id,
                client_request_id=client_request_id,
            )
        if existing is None:
            return None
        if existing.input_hash != input_hash:
            raise RunRequestConflictError("client_request_id was reused with different input")
        return RunSubmissionResult(
            run_id=existing.id,
            status=existing.status,
            created=False,
            enqueued=False,
        )

    async def _persist_queued_run(
        self,
        *,
        actor_id: UUID,
        conversation_id: UUID,
        content: str,
        client_request_id: str,
        input_hash: str,
        prompt_version: str,
        model: str,
    ) -> RunSubmissionResult:
        run_id = uuid4()
        async with self.database.session() as session, session.begin():
            conversation = await self.conversations.get_owned(
                session,
                conversation_id=conversation_id,
                owner_id=actor_id,
            )
            if conversation is None:
                raise ConversationNotFoundError("Conversation was not found")
            run = AgentRun(
                id=run_id,
                conversation_id=conversation_id,
                actor_id=actor_id,
                kind=RunKind.CHAT,
                client_request_id=client_request_id,
                input_hash=input_hash,
                status=RunStatus.QUEUED,
                checkpoint_thread_id=str(run_id),
                prompt_version=prompt_version,
                model=model,
                counters={},
            )
            session.add_all(
                [
                    run,
                    Message(
                        conversation_id=conversation_id,
                        run_id=run_id,
                        role="user",
                        content=content,
                    ),
                    RunEvent(
                        run_id=run_id,
                        sequence=1,
                        type="run.queued",
                        dedupe_key="submission",
                        safe_payload={},
                    ),
                ]
            )
        return RunSubmissionResult(
            run_id=run_id,
            status=RunStatus.QUEUED,
            created=True,
            enqueued=True,
        )

    async def _record_enqueue_failure(self, run_id: UUID) -> None:
        async with self.database.session() as session, session.begin():
            run = await self.runs.get_for_update(session, run_id=run_id)
            if run is None:
                return
            existing = await self.runs.get_event_by_dedupe_key(
                session,
                run_id=run_id,
                dedupe_key="initial-enqueue-failed",
            )
            if existing is None:
                await self.runs.append_event(
                    session,
                    run_id=run_id,
                    event_type="run.enqueue_failed",
                    dedupe_key="initial-enqueue-failed",
                    safe_payload={"error_code": "broker_unavailable"},
                )
