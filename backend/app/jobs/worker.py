"""Worker-side graph execution using PostgreSQL for duplicate delivery safety."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select

from app.agent.graph import build_support_graph, run_support_graph
from app.agent.rag import RAGGraphNodes
from app.auth.principal import Principal
from app.db import Database
from app.db.models import Conversation, Message, RunStatus
from app.memory.lifecycle import MemoryLifecycleService
from app.memory.retrieval import MemoryContextService
from app.observability import AIObserver, NoopAIObserver
from app.providers.base import StructuredResponseProvider
from app.providers.embeddings import EmbeddingProvider, FakeEmbeddingProvider
from app.providers.fake import FakeTextProvider
from app.rag.retrieval.query import HybridRetriever
from app.repositories.runs import RunRepository
from app.repositories.users import UserRepository
from app.services.approvals.resume import execute_approval_resume_run
from app.services.conversations.run_lease import RunLeaseService
from app.services.conversations.run_state import RunStateService


@dataclass(frozen=True, slots=True)
class WorkerResult:
    run_id: UUID
    status: str


async def execute_fake_run(database: Database, *, run_id: UUID) -> WorkerResult:
    return await execute_support_run(
        database,
        run_id=run_id,
        provider=FakeTextProvider(),
        embedding_provider=FakeEmbeddingProvider(),
        observer=NoopAIObserver(),
        model="fake",
    )


async def execute_support_run(
    database: Database,
    *,
    run_id: UUID,
    provider: StructuredResponseProvider,
    embedding_provider: EmbeddingProvider,
    observer: AIObserver,
    model: str,
    worker_id: str | None = None,
    lease_seconds: int = 90,
    max_attempts: int = 3,
) -> WorkerResult:
    repository = RunRepository()
    lease = RunLeaseService(repository)
    state = RunStateService(repository)
    execution_worker_id = worker_id or f"worker:{uuid4()}"
    async with database.session() as session, session.begin():
        claim = await lease.claim(
            session,
            run_id=run_id,
            worker_id=execution_worker_id,
            lease_seconds=lease_seconds,
            max_attempts=max_attempts,
        )
        if not claim.acquired:
            return WorkerResult(
                run_id=run_id,
                status="duplicate" if claim.outcome == "busy" else claim.outcome,
            )
        assert claim.run is not None and claim.previous_status is not None
        actor_id = claim.run.actor_id
        conversation_id = claim.run.conversation_id
        if claim.previous_status is RunStatus.QUEUED:
            await state.transition(
                session,
                run_id=run_id,
                actor_id=actor_id,
                target=RunStatus.RUNNING,
                operation_id=f"worker-claim:{run_id}",
            )

    if claim.previous_status in {RunStatus.RESUME_QUEUED, RunStatus.RUNNING}:
        resumed = await execute_approval_resume_run(
            database,
            run_id=run_id,
            worker_id=execution_worker_id,
        )
        if resumed != "not_approval":
            return WorkerResult(run_id=run_id, status=resumed)

    try:
        async with database.session() as session:
            user = await UserRepository().get_by_id(session, actor_id)
            if user is None:
                raise LookupError("Run actor no longer exists")
            user_message = await session.scalar(
                select(Message)
                .where(Message.run_id == run_id, Message.role == "user")
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            if user_message is None:
                raise LookupError("Run has no user message")
            query = user_message.content
            conversation_device_id = await session.scalar(
                select(Conversation.device_id).where(Conversation.id == conversation_id)
            )
            memory_context = await MemoryContextService().context_messages(
                session,
                owner_id=actor_id,
                device_id=conversation_device_id,
            )
            principal = Principal(
                user_id=user.id,
                session_id=UUID(int=0),
                email=user.email,
                display_name=user.display_name,
                role=user.role,
                department_id=user.department_id,
                department_key=user.department.key,
            )
            nodes = RAGGraphNodes(
                session=session,
                principal=principal,
                retriever=HybridRetriever(embedding_provider=embedding_provider),
                provider=provider,
                history=memory_context,
                observer=observer,
                model=model,
            )
            result = await run_support_graph(
                build_support_graph(nodes.graph_nodes()),
                {
                    "run_id": str(run_id),
                    "conversation_id": str(conversation_id),
                    "actor_id": str(actor_id),
                    "query": query,
                },
            )

        async with database.session() as session, session.begin():
            lease_extended = await lease.heartbeat(
                session,
                run_id=run_id,
                worker_id=execution_worker_id,
                lease_seconds=lease_seconds,
            )
            if not lease_extended:
                raise RuntimeError("Run lease was lost before result commit")
            session.add(
                Message(
                    conversation_id=conversation_id,
                    run_id=run_id,
                    role="assistant",
                    content=result["answer"],
                    outcome=result["outcome"],
                    citations=result.get("citations", []),
                )
            )
            await MemoryLifecycleService().extract_from_message(
                session,
                owner_id=actor_id,
                source_message_id=user_message.id,
            )
            transition = await state.transition(
                session,
                run_id=run_id,
                actor_id=actor_id,
                target=RunStatus.COMPLETED,
                operation_id=f"worker-complete:{run_id}",
                outcome=result["outcome"],
                safe_payload={
                    "provider": model,
                    "citation_count": len(result.get("citations", [])),
                },
            )
            transition.run.counters = {
                "model_calls": result.get("model_calls", 0),
                "retrieval_calls": result.get("retrieval_calls", 0),
                "input_tokens": result.get("input_tokens", 0),
                "output_tokens": result.get("output_tokens", 0),
            }
    except Exception:
        async with database.session() as session, session.begin():
            failed_run = await repository.get_for_update(session, run_id=run_id)
            if (
                failed_run is not None
                and failed_run.status is RunStatus.RUNNING
                and failed_run.lease_owner == execution_worker_id
            ):
                await state.transition(
                    session,
                    run_id=run_id,
                    actor_id=actor_id,
                    target=RunStatus.FAILED,
                    operation_id=f"worker-failed:{run_id}",
                    error_code="agent_execution_failed",
                    safe_payload={"error_code": "agent_execution_failed"},
                )
        raise
    return WorkerResult(run_id=run_id, status="processed")
