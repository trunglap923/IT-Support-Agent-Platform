"""Orchestrate scoped dense and sparse retrieval with pluggable fusion."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.diagnostics import content_log_fields, log_event
from app.providers.embeddings import EmbeddingProvider
from app.rag.retrieval.analysis import (
    DeterministicQueryAnalyzer,
    LowConfidenceRetry,
    ModelQueryAnalyzer,
    QueryAnalyzer,
    QueryRewritePolicy,
    expand_query_for_retrieval,
    meaningful_terms,
)
from app.rag.retrieval.dense import DenseRetriever, PostgresDenseRetriever
from app.rag.retrieval.expansion import expand_parent_and_neighbors
from app.rag.retrieval.fusion import FusionStrategy, ReciprocalRankFusion
from app.rag.retrieval.models import QuerySpec, RetrievalCandidate, RetrievalRequest
from app.rag.retrieval.rerank import Reranker, WeightedFeatureReranker
from app.rag.retrieval.sparse import PostgresSparseRetriever, SparseRetriever

logger = logging.getLogger(__name__)
__all__ = ["HybridRetriever", "RetrievalHit", "expand_query_for_retrieval", "meaningful_terms"]


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    chunk_id: UUID
    document_id: UUID
    version_id: UUID
    document_key: str
    version_label: str
    title: str
    page_number: int | None
    section: str | None
    content: str
    score: float
    vector_rank: int | None
    lexical_rank: int | None
    vector_similarity: float | None = None
    lexical_coverage: float = 0.0
    rrf_score: float = 0.0
    section_path: tuple[str, ...] = ()
    section_id: UUID | None = None
    ordinal: int = 0
    rerank_score: float | None = None
    expansion_kind: str | None = None


class HybridRetriever:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        query_analyzer: QueryAnalyzer | None = None,
        model_query_analyzer: ModelQueryAnalyzer | None = None,
        query_rewrite_policy: QueryRewritePolicy | None = None,
        low_confidence_retry: LowConfidenceRetry | None = None,
        dense_retriever: DenseRetriever | None = None,
        sparse_retriever: SparseRetriever | None = None,
        fusion_strategy: FusionStrategy | None = None,
        reranker: Reranker | None = None,
        branch_limit: int = 20,
        candidate_limit: int = 20,
        result_limit: int = 5,
        expansion_per_hit: int = 2,
        rrf_k: int = 60,
        log_prompts: bool = False,
    ) -> None:
        if branch_limit < 1 or candidate_limit < result_limit or result_limit < 1:
            raise ValueError("Retrieval limits must be positive")
        self._embedding_provider = embedding_provider
        self._query_analyzer = query_analyzer or DeterministicQueryAnalyzer()
        self._model_query_analyzer = model_query_analyzer
        self._query_rewrite_policy = query_rewrite_policy or QueryRewritePolicy()
        self._low_confidence_retry = low_confidence_retry or LowConfidenceRetry()
        self._dense_retriever = dense_retriever or PostgresDenseRetriever()
        self._sparse_retriever = sparse_retriever or PostgresSparseRetriever()
        self._fusion_strategy = fusion_strategy or ReciprocalRankFusion(k=rrf_k)
        self._reranker = reranker or WeightedFeatureReranker()
        self._branch_limit = branch_limit
        self._candidate_limit = candidate_limit
        self._result_limit = result_limit
        self._expansion_per_hit = max(0, expansion_per_hit)
        self._log_prompts = log_prompts
        self._last_analysis: QuerySpec | None = None

    @property
    def last_analysis(self) -> QuerySpec | None:
        return self._last_analysis

    async def search(
        self,
        session: AsyncSession,
        *,
        query: str,
        principal: Principal,
        operation_id: str,
        now: datetime | None = None,
    ) -> list[RetrievalHit]:
        started_at = time.monotonic()
        request = RetrievalRequest(raw_query=query, result_limit=self._result_limit)
        spec = self._query_analyzer.analyze(request)
        run_id = (
            operation_id.removeprefix("rag:").removesuffix(":retrieve")
            if operation_id.startswith("rag:")
            else None
        )
        model_analysis_used = False
        if self._model_query_analyzer is not None and self._query_rewrite_policy.use_model(spec):
            try:
                calls_before = self._model_query_analyzer.calls_used
                spec = await self._model_query_analyzer.analyze(
                    request,
                    spec,
                    operation_id=f"{operation_id}:query-analysis",
                )
                model_analysis_used = self._model_query_analyzer.calls_used > calls_before
            except Exception as error:
                log_event(
                    logger,
                    "retrieval.analysis.model_fallback",
                    run_id=run_id,
                    operation_id=operation_id,
                    error_type=type(error).__name__,
                )
        semantic_queries = self._low_confidence_retry.semantic_queries(
            spec, policy=self._query_rewrite_policy
        )
        self._last_analysis = spec
        log_event(
            logger,
            "retrieval.analysis.completed",
            run_id=run_id,
            operation_id=operation_id,
            actor_id=str(principal.user_id),
            semantic_query_expanded=spec.semantic_query != spec.raw_query,
            analyzer=spec.analyzer,
            analysis_confidence=round(spec.confidence, 4),
            intent=spec.intent,
            model_analysis_used=model_analysis_used,
            semantic_query_count=len(semantic_queries),
            exact_identifier_count=len(spec.exact_terms),
            services=list(spec.filters.services),
            products=list(spec.filters.products),
            operating_systems=list(spec.filters.operating_systems),
            error_codes=list(spec.filters.error_codes),
            versions=list(spec.filters.version_labels),
            version_scope=spec.filters.version_scope,
            **content_log_fields("query", spec.raw_query, include_content=self._log_prompts),
            **content_log_fields(
                "semantic_query", spec.semantic_query, include_content=self._log_prompts
            ),
        )

        embedding_started = time.monotonic()
        query_batch = await self._embedding_provider.embed(
            list(semantic_queries), operation_id=operation_id
        )
        embedding_ms = (time.monotonic() - embedding_started) * 1_000
        if query_batch.dimensions != 1536:
            raise ValueError("Query embedding dimensions do not match the corpus")

        selected_now = now or datetime.now(UTC)
        dense_started = time.monotonic()
        dense_by_chunk: dict[UUID, RetrievalCandidate] = {}
        for vector in query_batch.vectors:
            query_dense = await self._dense_retriever.retrieve(
                session,
                query_vector=list(vector),
                principal=principal,
                now=selected_now,
                limit=self._branch_limit,
            )
            for candidate in query_dense:
                previous = dense_by_chunk.get(candidate.chunk_id)
                if previous is None or (candidate.dense_score or 0.0) > (
                    previous.dense_score or 0.0
                ):
                    dense_by_chunk[candidate.chunk_id] = candidate
        dense = [
            replace(candidate, dense_rank=rank)
            for rank, candidate in enumerate(
                sorted(
                    dense_by_chunk.values(),
                    key=lambda item: (
                        -(item.dense_score or 0.0),
                        item.document_key,
                        item.ordinal,
                    ),
                )[: self._branch_limit],
                start=1,
            )
        ]
        dense_ms = (time.monotonic() - dense_started) * 1_000

        sparse_started = time.monotonic()
        sparse = await self._sparse_retriever.retrieve(
            session,
            raw_query=spec.sparse_query,
            principal=principal,
            now=selected_now,
            limit=self._branch_limit,
        )
        sparse_ms = (time.monotonic() - sparse_started) * 1_000

        fusion_started = time.monotonic()
        fused = self._fusion_strategy.fuse(dense, sparse)
        fusion_ms = (time.monotonic() - fusion_started) * 1_000
        rerank_started = time.monotonic()
        reranked = self._reranker.rerank(spec.raw_query, fused[: self._candidate_limit])
        seeds = reranked[: request.result_limit]
        hits = [
            self._to_hit(
                item,
                raw_query=spec.raw_query,
                semantic_query=spec.semantic_query,
            )
            for item in seeds
        ]
        rerank_ms = (time.monotonic() - rerank_started) * 1_000
        expanded: list[RetrievalHit] = []
        expansion_started = time.monotonic()
        if self._expansion_per_hit:
            expansion_candidates = await expand_parent_and_neighbors(
                session,
                seeds,
                principal=principal,
                now=selected_now,
                max_neighbors_per_seed=self._expansion_per_hit,
            )
            expanded_candidates = self._reranker.rerank(
                spec.raw_query, [item.candidate for item in expansion_candidates]
            )
            expansion_kind_by_id = {
                item.candidate.chunk_id: item.expansion_kind for item in expansion_candidates
            }
            expanded = [
                self._to_hit(
                    item,
                    raw_query=spec.raw_query,
                    semantic_query=spec.semantic_query,
                    expansion_kind=expansion_kind_by_id[item.chunk_id],
                )
                for item in expanded_candidates
            ]
        results = [*hits, *expanded]
        expansion_ms = (time.monotonic() - expansion_started) * 1_000

        log_event(
            logger,
            "retrieval.search.completed",
            run_id=run_id,
            operation_id=operation_id,
            embedding_model=query_batch.model,
            embedding_request_id=query_batch.provider_request_id,
            query_analyzer=spec.analyzer,
            query_intent=spec.intent,
            query_confidence=round(spec.confidence, 4),
            semantic_query_count=len(semantic_queries),
            fusion_strategy=self._fusion_strategy.name,
            reranker=self._reranker.name,
            dense_candidates=len(dense),
            sparse_candidates=len(sparse),
            fused_candidates=len(fused),
            reranked_candidates=len(reranked),
            expanded_candidates=len(expanded),
            primary_result_count=len(hits),
            result_count=len(results),
            embedding_ms=round(embedding_ms, 2),
            dense_ms=round(dense_ms, 2),
            sparse_ms=round(sparse_ms, 2),
            fusion_ms=round(fusion_ms, 2),
            rerank_ms=round(rerank_ms, 2),
            expansion_ms=round(expansion_ms, 2),
            duration_ms=round((time.monotonic() - started_at) * 1_000, 2),
            results=[self._safe_result(hit) for hit in results],
        )
        return results

    def _to_hit(
        self,
        candidate: RetrievalCandidate,
        *,
        raw_query: str,
        semantic_query: str,
        expansion_kind: str | None = None,
    ) -> RetrievalHit:
        raw_terms = set(meaningful_terms(raw_query))
        semantic_terms = set(meaningful_terms(semantic_query))
        content_terms = set(meaningful_terms(candidate.content, limit=800))
        lexical_coverage = (
            min(1.0, len(semantic_terms & content_terms) / len(raw_terms)) if raw_terms else 0.0
        )
        confidence = max(candidate.dense_score or 0.0, lexical_coverage)
        return RetrievalHit(
            chunk_id=candidate.chunk_id,
            document_id=candidate.document_id,
            version_id=candidate.version_id,
            document_key=candidate.document_key,
            version_label=candidate.version_label,
            title=candidate.title,
            page_number=candidate.page_number,
            section=candidate.section,
            content=candidate.content,
            score=confidence,
            vector_rank=candidate.dense_rank,
            lexical_rank=candidate.sparse_rank,
            vector_similarity=candidate.dense_score,
            lexical_coverage=lexical_coverage,
            rrf_score=candidate.fusion_score,
            section_path=candidate.section_path,
            section_id=candidate.section_id,
            ordinal=candidate.ordinal,
            rerank_score=candidate.rerank_score,
            expansion_kind=expansion_kind,
        )

    def _safe_result(self, hit: RetrievalHit) -> dict[str, object]:
        return {
            "chunk_id": str(hit.chunk_id),
            "document_key": hit.document_key,
            "version_label": hit.version_label,
            "title": hit.title,
            "page_number": hit.page_number,
            "section": hit.section,
            "section_path": list(hit.section_path),
            "score": round(hit.score, 6),
            "dense_rank": hit.vector_rank,
            "sparse_rank": hit.lexical_rank,
            "vector_similarity": (
                round(hit.vector_similarity, 6) if hit.vector_similarity is not None else None
            ),
            "lexical_coverage": round(hit.lexical_coverage, 6),
            "rrf_score": round(hit.rrf_score, 6),
            "rerank_score": (round(hit.rerank_score, 6) if hit.rerank_score is not None else None),
            "expansion_kind": hit.expansion_kind,
            **content_log_fields("content", hit.content, include_content=self._log_prompts),
        }
