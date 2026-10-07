"""Minimal task contracts; production handlers are added with their feature slices."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from uuid import UUID

from celery import shared_task  # type: ignore[import-untyped]

from app.agent.openai_agents_runtime import OpenAIAgentsRuntimeFactory
from app.config import AgentRuntime, AIProvider, Settings
from app.db import Database
from app.jobs.celery_app import celery_app
from app.jobs.dispatch import CeleryMemoryExtractionDispatcher, CeleryRunDispatcher
from app.jobs.maintenance import expire_pending_approvals
from app.jobs.memory import execute_memory_extraction, reconcile_memory_extractions
from app.jobs.reconcile import reconcile_queued_run_dispatches
from app.jobs.worker import execute_support_run
from app.observability import create_ai_observer
from app.providers.factory import (
    create_embedding_provider,
    create_provider,
    create_text_usage_ledger,
)
from app.rag.retrieval.fusion import ReciprocalRankFusion
from app.rag.retrieval.rerank import create_reranker
from app.rag.retrieval.sparse import create_sparse_retriever


@shared_task(name="jobs.run_agent")  # type: ignore[untyped-decorator]
def run_agent(run_id: str) -> dict[str, str]:
    """Claim a run and execute the configured retrieval-backed support graph."""

    settings = Settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is required by the agent worker")
    database_url = settings.database_url.get_secret_value()

    async def execute() -> dict[str, str]:
        database = Database(database_url)
        provider = create_provider(settings, database)
        embedding_provider = create_embedding_provider(settings, database)
        observer = create_ai_observer(settings)
        retrieval_reranker = create_reranker(
            strategy=settings.retrieval_reranker.value,
            model=settings.retrieval_cross_encoder_model,
            model_file=settings.retrieval_cross_encoder_model_file,
            max_candidates=settings.retrieval_cross_encoder_candidate_limit,
            timeout_seconds=settings.retrieval_cross_encoder_timeout_seconds,
        )
        retrieval_sparse_retriever = create_sparse_retriever(
            strategy=settings.retrieval_sparse_backend.value
        )
        retrieval_fusion_strategy = ReciprocalRankFusion(
            k=settings.retrieval_rrf_k,
            dense_weight=settings.retrieval_rrf_dense_weight,
            sparse_weight=settings.retrieval_rrf_sparse_weight,
            exact_weight=settings.retrieval_rrf_exact_weight,
        )
        use_agents_sdk = settings.agent_runtime is AgentRuntime.OPENAI_AGENTS or (
            settings.agent_runtime is AgentRuntime.AUTO
            and settings.text_provider is AIProvider.OPENAI
        )
        agent_runtime_factory = None
        if use_agents_sdk:
            key = settings.openai_api_key
            if key is None:
                raise RuntimeError("OpenAI credentials were not validated")
            agent_runtime_factory = OpenAIAgentsRuntimeFactory(
                api_key=key.get_secret_value(),
                model=settings.openai_model,
                usage_ledger=create_text_usage_ledger(settings, database),
            )
        try:
            receipt = asdict(
                await execute_support_run(
                    database,
                    run_id=UUID(run_id),
                    provider=provider,
                    embedding_provider=embedding_provider,
                    observer=observer,
                    model=(
                        settings.openai_model
                        if settings.text_provider.value == "openai"
                        else "fake"
                    ),
                    lease_seconds=settings.run_lease_seconds,
                    max_attempts=settings.run_max_attempts,
                    memory_dispatcher=CeleryMemoryExtractionDispatcher(celery_app),
                    agent_runtime_factory=agent_runtime_factory,
                    log_prompts=settings.log_prompts,
                    retrieval_branch_limit=settings.retrieval_branch_limit,
                    retrieval_result_limit=settings.retrieval_result_limit,
                    retrieval_rrf_k=settings.retrieval_rrf_k,
                    retrieval_max_primary_chunks_per_document=(
                        settings.retrieval_max_primary_chunks_per_document
                    ),
                    retrieval_minimum_evidence_score=(settings.retrieval_minimum_evidence_score),
                    retrieval_fusion_strategy=retrieval_fusion_strategy,
                    retrieval_reranker=retrieval_reranker,
                    retrieval_sparse_retriever=retrieval_sparse_retriever,
                )
            )
            return {key: str(value) for key, value in receipt.items()}
        finally:
            observer.close()
            await embedding_provider.close()
            await provider.close()
            await database.close()

    return asyncio.run(execute())


@shared_task(name="jobs.reconcile_queued_runs")  # type: ignore[untyped-decorator]
def reconcile_queued_runs() -> dict[str, int]:
    """Re-enqueue old queued runs; duplicate deliveries are claimed in PostgreSQL."""

    settings = Settings()
    if settings.database_url is None or settings.redis_url is None:
        raise RuntimeError("DATABASE_URL and REDIS_URL are required by reconciliation")
    database_url = settings.database_url.get_secret_value()
    redis_url = settings.redis_url.get_secret_value()

    async def reconcile() -> int:
        database = Database(database_url)
        dispatcher = CeleryRunDispatcher(
            celery_app,
            redis_url=redis_url,
            socket_timeout_seconds=settings.redis_socket_timeout_seconds,
        )
        try:
            return await reconcile_queued_run_dispatches(
                database,
                dispatcher,
                max_attempts=settings.run_max_attempts,
            )
        finally:
            await database.close()

    return {"requeued": asyncio.run(reconcile())}


@shared_task(name="jobs.expire_pending_approvals")  # type: ignore[untyped-decorator]
def expire_approvals() -> dict[str, int]:
    """Expire due approval drafts and release their waiting runs."""

    settings = Settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is required by approval maintenance")
    database_url = settings.database_url.get_secret_value()

    async def expire() -> int:
        database = Database(database_url)
        try:
            return await expire_pending_approvals(database)
        finally:
            await database.close()

    return {"expired": asyncio.run(expire())}


@shared_task(name="jobs.extract_memory")  # type: ignore[untyped-decorator]
def extract_memory(job_id: str) -> dict[str, str]:
    """Complete one durable, epoch-checked memory extraction job."""

    settings = Settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is required by memory extraction")
    database_url = settings.database_url.get_secret_value()

    async def execute() -> str:
        database = Database(database_url)
        try:
            return await execute_memory_extraction(database, job_id=UUID(job_id))
        finally:
            await database.close()

    return {"status": asyncio.run(execute())}


@shared_task(name="jobs.reconcile_memory_extractions")  # type: ignore[untyped-decorator]
def reconcile_memory_jobs() -> dict[str, int]:
    """Redeliver pending memory jobs after broker/process failures."""

    settings = Settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is required by memory reconciliation")
    database_url = settings.database_url.get_secret_value()

    async def reconcile() -> int:
        database = Database(database_url)
        try:
            return await reconcile_memory_extractions(
                database,
                CeleryMemoryExtractionDispatcher(celery_app),
            )
        finally:
            await database.close()

    return {"requeued": asyncio.run(reconcile())}
