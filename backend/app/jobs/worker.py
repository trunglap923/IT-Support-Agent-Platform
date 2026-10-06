"""Worker-side graph execution using PostgreSQL for duplicate delivery safety."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select

from app.agent.approval_checkpoint import pause_ticket_approval
from app.agent.context.service import SupportContextService
from app.agent.graph import build_support_graph, run_support_graph
from app.agent.knowledge_tool import KnowledgeToolSearch
from app.agent.openai_agents_runtime import (
    OpenAIAgentsRuntimeFactory,
    SupportSDKContext,
)
from app.agent.rag import RAGGraphNodes
from app.agent.request_policy import resolve_request_policy
from app.auth.principal import Principal
from app.db import Database
from app.db.models import AgentRuntimeState, ApprovalRequest, ApprovalStatus, Message, RunStatus
from app.diagnostics import content_log_fields, log_event
from app.jobs.dispatch import (
    BrokerUnavailableError,
    MemoryExtractionDispatcher,
)
from app.memory.lifecycle import MemoryLifecycleService
from app.observability import AIObserver, NoopAIObserver
from app.providers.base import StructuredResponseProvider
from app.providers.embeddings import EmbeddingProvider, FakeEmbeddingProvider
from app.providers.fake import FakeTextProvider
from app.providers.structured import IncompleteStructuredResponseError
from app.rag.retrieval.query import HybridRetriever
from app.rag.retrieval.rerank import Reranker
from app.repositories.conversations import ConversationRepository
from app.repositories.runs import RunRepository
from app.repositories.users import UserRepository
from app.services.approvals.resume import execute_approval_resume_run
from app.services.approvals.service import ApprovalService
from app.services.conversations.agent_runtime_state import AgentRuntimeStateService
from app.services.conversations.run_lease import RunLeaseService
from app.services.conversations.run_state import RunStateService
from app.tools import ToolExecutionContext, ToolExecutor
from app.tools.schemas import CreateTicketArguments

logger = logging.getLogger(__name__)


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
    memory_dispatcher: MemoryExtractionDispatcher | None = None,
    agent_runtime_factory: OpenAIAgentsRuntimeFactory | None = None,
    log_prompts: bool = False,
    retrieval_branch_limit: int = 20,
    retrieval_result_limit: int = 5,
    retrieval_rrf_k: int = 60,
    retrieval_max_primary_chunks_per_document: int = 1,
    retrieval_minimum_evidence_score: float = 0.45,
    retrieval_reranker: Reranker | None = None,
) -> WorkerResult:
    started_at = time.monotonic()
    log_event(
        logger,
        "worker.run.started",
        run_id=str(run_id),
        model=model,
        worker_id=worker_id,
    )
    repository = RunRepository()
    lease = RunLeaseService(repository)
    state = RunStateService(repository)
    memory_job_id: UUID | None = None
    approval_pause: tuple[UUID, str, str] | None = None
    sdk_resume = False
    prior_tool_calls = 0
    prior_retrieval_calls = 0
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
            log_event(
                logger,
                "worker.run.not_claimed",
                run_id=str(run_id),
                outcome=claim.outcome,
                duration_ms=round((time.monotonic() - started_at) * 1_000, 2),
            )
            return WorkerResult(
                run_id=run_id,
                status="duplicate" if claim.outcome == "busy" else claim.outcome,
            )
        assert claim.run is not None and claim.previous_status is not None
        actor_id = claim.run.actor_id
        conversation_id = claim.run.conversation_id
        execution_version = claim.run.execution_version
        log_event(
            logger,
            "worker.run.claimed",
            run_id=str(run_id),
            worker_id=execution_worker_id,
            previous_status=claim.previous_status.value,
            execution_version=execution_version,
            attempt=claim.run.attempts,
        )
        if claim.previous_status is RunStatus.QUEUED:
            await state.transition(
                session,
                run_id=run_id,
                actor_id=actor_id,
                target=RunStatus.RUNNING,
                operation_id=f"worker-claim:{run_id}",
            )
        elif claim.previous_status in {RunStatus.RESUME_QUEUED, RunStatus.RUNNING}:
            persisted_runtime = await session.get(AgentRuntimeState, run_id)
            if (
                persisted_runtime is not None
                and persisted_runtime.runtime == "openai_agents"
                and persisted_runtime.status == "paused"
                and persisted_runtime.serialized_state is not None
            ):
                if agent_runtime_factory is None:
                    raise RuntimeError("OpenAI Agents runtime is unavailable for a paused run")
                if claim.previous_status is RunStatus.RESUME_QUEUED:
                    await state.transition(
                        session,
                        run_id=run_id,
                        actor_id=actor_id,
                        target=RunStatus.RUNNING,
                        operation_id=f"agent-sdk-resume-claim:{run_id}:{execution_version}",
                    )
                sdk_resume = True
                raw_tool_calls = claim.run.counters.get("tool_calls", 0)
                raw_retrieval_calls = claim.run.counters.get("retrieval_calls", 0)
                prior_tool_calls = raw_tool_calls if isinstance(raw_tool_calls, int) else 0
                prior_retrieval_calls = (
                    raw_retrieval_calls if isinstance(raw_retrieval_calls, int) else 0
                )

    if claim.previous_status in {RunStatus.RESUME_QUEUED, RunStatus.RUNNING} and not sdk_resume:
        resumed = await execute_approval_resume_run(
            database,
            run_id=run_id,
            worker_id=execution_worker_id,
        )
        if resumed != "not_approval":
            return WorkerResult(run_id=run_id, status=resumed)

    stream_generation = 0
    stream_delta_index = 0
    progress_event_index = 0

    async def append_progress_event(
        stage: str,
        status: str,
        detail: str | None = None,
        count: int | None = None,
    ) -> None:
        nonlocal progress_event_index
        payload: dict[str, object] = {"stage": stage, "status": status}
        if detail is not None:
            payload["detail"] = detail[:180]
        if count is not None:
            payload["count"] = max(0, count)
        async with database.session() as event_session, event_session.begin():
            active_run = await repository.get_for_update(event_session, run_id=run_id)
            if (
                active_run is None
                or active_run.status is not RunStatus.RUNNING
                or active_run.lease_owner != execution_worker_id
            ):
                raise RuntimeError("Run lease was lost while reporting progress")
            await repository.append_event(
                event_session,
                run_id=run_id,
                event_type="agent.progress",
                dedupe_key=f"progress:{execution_version}:{progress_event_index}",
                safe_payload=payload,
            )
            progress_event_index += 1

    async def append_stream_event(event_type: str, payload: dict[str, object]) -> None:
        nonlocal stream_delta_index
        async with database.session() as event_session, event_session.begin():
            streaming_run = await repository.get_for_update(event_session, run_id=run_id)
            if (
                streaming_run is None
                or streaming_run.status is not RunStatus.RUNNING
                or streaming_run.lease_owner != execution_worker_id
            ):
                raise RuntimeError("Run lease was lost while streaming the response")
            suffix = (
                f"{stream_generation}:start"
                if event_type == "assistant.stream.started"
                else f"{stream_generation}:{stream_delta_index}"
            )
            await repository.append_event(
                event_session,
                run_id=run_id,
                event_type=event_type,
                dedupe_key=f"stream:{execution_version}:{suffix}",
                safe_payload=payload,
            )
            if event_type == "assistant.stream.delta":
                stream_delta_index += 1

    async def start_response_stream() -> None:
        nonlocal stream_generation, stream_delta_index
        stream_generation += 1
        stream_delta_index = 0
        await append_stream_event("assistant.stream.started", {"generation": stream_generation})
        log_event(
            logger,
            "worker.stream.started",
            run_id=str(run_id),
            generation=stream_generation,
        )

    async def stream_text_delta(delta: str) -> None:
        if delta:
            await append_stream_event("assistant.stream.delta", {"delta": delta})
            log_event(
                logger,
                "worker.stream.delta.persisted",
                run_id=str(run_id),
                generation=stream_generation,
                delta_index=stream_delta_index - 1,
                **content_log_fields(
                    "delta",
                    delta,
                    include_content=log_prompts,
                    max_chars=1_000,
                ),
            )

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
            await append_progress_event("analyze", "started")
            principal = Principal(
                user_id=user.id,
                session_id=UUID(int=0),
                email=user.email,
                display_name=user.display_name,
                role=user.role,
                department_id=user.department_id,
                department_key=user.department.key,
            )
            support_context = await SupportContextService().build(
                session,
                principal=principal,
                conversation_id=conversation_id,
                current_message_id=user_message.id,
                query=query,
            )
            log_event(
                logger,
                "worker.context.prepared",
                run_id=str(run_id),
                actor_id=str(actor_id),
                conversation_id=str(conversation_id),
                conversation_messages=len(support_context.history),
                memory_messages=len(support_context.memories),
                **content_log_fields(
                    "user_message",
                    query,
                    include_content=log_prompts,
                ),
            )

            request_policy = await resolve_request_policy(
                query,
                model=provider,
                operation_id=f"agent:{run_id}:query-analysis",
            )
            log_event(
                logger,
                "worker.query_analysis.resolved",
                run_id=str(run_id),
                intent=request_policy.analysis.intent,
                confidence=round(request_policy.analysis.confidence, 4),
                analyzer=request_policy.analysis.analyzer,
                model_calls=request_policy.analysis_model_calls,
            )
            retriever = HybridRetriever(
                embedding_provider=embedding_provider,
                query_analysis=request_policy.analysis,
                branch_limit=retrieval_branch_limit,
                result_limit=retrieval_result_limit,
                rrf_k=retrieval_rrf_k,
                max_primary_chunks_per_document=(retrieval_max_primary_chunks_per_document),
                reranker=retrieval_reranker,
                log_prompts=log_prompts,
            )
            citation_store: dict[str, dict[str, object]] = {}
            local_search = KnowledgeToolSearch(
                session=session,
                principal=principal,
                retriever=retriever,
                run_id=str(run_id),
                citation_store=citation_store,
                current_query=query,
                minimum_evidence_score=retrieval_minimum_evidence_score,
            )

            tool_executor = ToolExecutor(
                context=ToolExecutionContext(
                    actor_id=actor_id,
                    run_id=run_id,
                    database_url=database.engine.url.render_as_string(hide_password=False),
                    actor_role=user.role.value,
                ),
                local_search=local_search,
            )
            runtime_state_service = AgentRuntimeStateService()
            persisted_runtime = await runtime_state_service.get(session, run_id=run_id)
            if agent_runtime_factory is not None:
                approval = await session.scalar(
                    select(ApprovalRequest).where(
                        ApprovalRequest.run_id == run_id,
                        ApprovalRequest.owner_id == actor_id,
                        ApprovalRequest.status.in_(
                            [
                                ApprovalStatus.APPROVED.value,
                                ApprovalStatus.REJECTED.value,
                                ApprovalStatus.EXECUTED.value,
                            ]
                        ),
                    )
                )
                approval_decision = None
                approval_id = None
                if approval is not None:
                    approval_id = approval.id
                    approval_decision = (
                        "approved"
                        if approval.status
                        in {ApprovalStatus.APPROVED.value, ApprovalStatus.EXECUTED.value}
                        else "rejected"
                    )
                sdk_context = SupportSDKContext(
                    support=support_context,
                    executor=tool_executor,
                    database=database,
                    run_id=run_id,
                    citation_store=citation_store,
                    on_progress=append_progress_event,
                    approval_id=approval_id,
                    approval_decision=approval_decision,
                    tool_calls=prior_tool_calls,
                    retrieval_calls=prior_retrieval_calls,
                    policy=request_policy,
                )
                runtime = agent_runtime_factory.create(
                    context=sdk_context,
                    operation_id=f"agent:{run_id}:sdk:{execution_version}",
                    on_stream_started=start_response_stream,
                    on_text_delta=stream_text_delta,
                )
                try:
                    runtime_result = await runtime.run(
                        query=query,
                        serialized_state=(
                            persisted_runtime.serialized_state
                            if persisted_runtime is not None
                            and persisted_runtime.status == "paused"
                            else None
                        ),
                    )
                finally:
                    await runtime.close()
                result = runtime_result.as_graph_result()
            else:
                nodes = RAGGraphNodes(
                    session=session,
                    principal=principal,
                    retriever=retriever,
                    provider=provider,
                    request_policy=request_policy,
                    history=support_context.model_history,
                    observer=observer,
                    model=model,
                    tool_runner=tool_executor,
                    on_stream_started=start_response_stream,
                    on_text_delta=stream_text_delta,
                    on_progress=append_progress_event,
                    log_prompts=log_prompts,
                    minimum_evidence_score=retrieval_minimum_evidence_score,
                )
                log_event(logger, "worker.graph.started", run_id=str(run_id))
                result = dict(
                    await run_support_graph(
                        build_support_graph(nodes.graph_nodes()),
                        {
                            "run_id": str(run_id),
                            "conversation_id": str(conversation_id),
                            "actor_id": str(actor_id),
                            "query": query,
                        },
                    )
                )
            result["model_calls"] = (
                int(result.get("model_calls", 0)) + request_policy.analysis_model_calls
            )
            result["step_count"] = (
                int(result.get("step_count", 0)) + request_policy.analysis_model_calls
            )
            result["input_tokens"] = (
                int(result.get("input_tokens", 0)) + request_policy.analysis_input_tokens
            )
            result["output_tokens"] = (
                int(result.get("output_tokens", 0)) + request_policy.analysis_output_tokens
            )
            log_event(
                logger,
                "worker.graph.completed",
                run_id=str(run_id),
                outcome=result.get("outcome"),
                route=result.get("route"),
                stop_reason=result.get("stop_reason"),
                model_calls=result.get("model_calls", 0),
                retrieval_calls=result.get("retrieval_calls", 0),
                tool_calls=result.get("tool_calls", 0),
                step_count=result.get("step_count", 0),
                citation_count=len(result.get("citations", [])),
                input_tokens=result.get("input_tokens", 0),
                output_tokens=result.get("output_tokens", 0),
                **content_log_fields(
                    "answer",
                    str(result.get("answer", "")),
                    include_content=log_prompts,
                ),
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
            assistant_message = Message(
                conversation_id=conversation_id,
                run_id=run_id,
                role="assistant",
                content=result["answer"],
                outcome=result["outcome"],
                citations=result.get("citations", []),
            )
            await ConversationRepository().touch(session, conversation_id=conversation_id)
            session.add(assistant_message)
            await session.flush()
            proposal = result.get("approval_proposal")
            if isinstance(proposal, dict):
                arguments = CreateTicketArguments.model_validate(proposal)
                approval = await ApprovalService().create_ticket_draft(
                    session,
                    owner_id=actor_id,
                    run_id=run_id,
                    action_id=f"agent-ticket:{run_id}",
                    arguments=arguments,
                )
                transition = await state.transition(
                    session,
                    run_id=run_id,
                    actor_id=actor_id,
                    target=RunStatus.WAITING_APPROVAL,
                    operation_id=f"worker-waiting-approval:{run_id}",
                    outcome="approval_required",
                    safe_payload={"approval_id": str(approval.id)},
                )
                approval_pause = (
                    approval.id,
                    approval.arguments_hash,
                    transition.run.checkpoint_thread_id,
                )
                serialized_state = result.get("serialized_state")
                approval_call_id = result.get("approval_call_id")
                if isinstance(serialized_state, str) and isinstance(approval_call_id, str):
                    await AgentRuntimeStateService().pause(
                        session,
                        run_id=run_id,
                        serialized_state=serialized_state,
                        approval_call_id=approval_call_id,
                    )
                    approval_pause = None
            else:
                await AgentRuntimeStateService().complete(session, run_id=run_id)
                memory_job = await MemoryLifecycleService().start_extraction_job(
                    session,
                    owner_id=actor_id,
                    source_message_id=user_message.id,
                )
                memory_job_id = memory_job.id if memory_job is not None else None
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
                "tool_calls": result.get("tool_calls", 0),
                "input_tokens": result.get("input_tokens", 0),
                "output_tokens": result.get("output_tokens", 0),
            }
            final_status = transition.run.status.value
            assistant_message_id = str(assistant_message.id)
    except Exception as error:
        error_code = (
            "provider_output_incomplete"
            if isinstance(error, IncompleteStructuredResponseError)
            else "agent_execution_failed"
        )
        async with database.session() as session, session.begin():
            failed_run = await repository.get_for_update(session, run_id=run_id)
            if (
                failed_run is not None
                and failed_run.status is RunStatus.RUNNING
                and failed_run.lease_owner == execution_worker_id
            ):
                await AgentRuntimeStateService().complete(session, run_id=run_id)
                await state.transition(
                    session,
                    run_id=run_id,
                    actor_id=actor_id,
                    target=RunStatus.FAILED,
                    operation_id=f"worker-failed:{run_id}",
                    error_code=error_code,
                    safe_payload={"error_code": error_code},
                )
        log_event(
            logger,
            "worker.run.failed",
            level=logging.ERROR,
            exc_info=True,
            run_id=str(run_id),
            worker_id=execution_worker_id,
            error_code=error_code,
            error_type=type(error).__name__,
            error=str(error),
            duration_ms=round((time.monotonic() - started_at) * 1_000, 2),
        )
        raise
    log_event(
        logger,
        "worker.result.committed",
        run_id=str(run_id),
        status=final_status,
        assistant_message_id=assistant_message_id,
        duration_ms=round((time.monotonic() - started_at) * 1_000, 2),
    )
    if approval_pause is not None:
        approval_id, arguments_hash, checkpoint_thread_id = approval_pause
        await asyncio.to_thread(
            pause_ticket_approval,
            database_url=database.engine.url.render_as_string(hide_password=False),
            checkpoint_thread_id=checkpoint_thread_id,
            run_id=run_id,
            actor_id=actor_id,
            approval_id=approval_id,
            arguments_hash=arguments_hash,
        )
        return WorkerResult(run_id=run_id, status="waiting_approval")
    if memory_dispatcher is not None and memory_job_id is not None:
        # This runs only after the transaction containing the final message,
        # completed run and pending extraction job has committed. The periodic
        # reconciler redelivers the durable ID when the broker is unavailable.
        with suppress(BrokerUnavailableError):
            await memory_dispatcher.enqueue_memory_extraction(memory_job_id)
    return WorkerResult(run_id=run_id, status="processed")
