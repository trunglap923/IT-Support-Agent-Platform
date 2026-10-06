"""Measure dense, sparse, fusion, and reranking contributions on a public BEIR split."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from app.auth.principal import Principal
from app.db import Database
from app.db.models import UserRole
from app.rag.chunking.splitter import ChunkingConfig
from app.rag.retrieval.analysis import (
    DeterministicQueryAnalyzer,
    LowConfidenceRetry,
    QueryRewritePolicy,
)
from app.rag.retrieval.dense import PostgresDenseRetriever
from app.rag.retrieval.diversity import DocumentDiversitySelector
from app.rag.retrieval.exact import PostgresExactRetriever
from app.rag.retrieval.fusion import ReciprocalRankFusion
from app.rag.retrieval.models import QuerySpec, RetrievalCandidate, RetrievalRequest
from app.rag.retrieval.rerank import WeightedFeatureReranker
from app.rag.retrieval.sparse import PostgresSparseRetriever
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from evals.public.adapters.beir import BEIR_DATASETS, load_beir_dataset
from evals.public.contracts import PublicBenchmark, PublicQuery
from evals.public.metrics import aggregate_metrics, query_metrics
from evals.runner.public_retrieval import (
    BACKEND_ROOT,
    CANDIDATE_LIMIT,
    DEFAULT_CACHE_DIR,
    DEFAULT_REPORT_DIR,
    EMBEDDING_BATCH_SIZE,
    EVALUATION_TIME,
    RESULT_LIMIT,
    _embedding_provider,
    _precompute_query_embeddings,
    seed_public_corpus,
)

BRANCH_LIMIT = 100
VARIANTS = ("dense_only", "postgres_fts_only", "hybrid_rrf", "hybrid_weighted")


def _rerank_dense_candidates(
    candidates: dict[UUID, RetrievalCandidate],
) -> list[RetrievalCandidate]:
    return [
        replace(candidate, dense_rank=rank)
        for rank, candidate in enumerate(
            sorted(
                candidates.values(),
                key=lambda item: (
                    -(item.dense_score or 0.0),
                    item.document_key,
                    item.ordinal,
                ),
            )[:BRANCH_LIMIT],
            start=1,
        )
    ]


async def _candidate_branches(
    session: AsyncSession,
    *,
    query: PublicQuery,
    principal: Principal,
    query_provider: Any,
) -> tuple[
    QuerySpec,
    list[RetrievalCandidate],
    list[RetrievalCandidate],
    list[RetrievalCandidate],
]:
    analyzer = DeterministicQueryAnalyzer()
    retry = LowConfidenceRetry()
    rewrite_policy = QueryRewritePolicy()
    spec = analyzer.analyze(
        RetrievalRequest(raw_query=query.text, result_limit=RESULT_LIMIT)
    )
    semantic_queries = retry.semantic_queries(spec, policy=rewrite_policy)
    query_batch = await query_provider.embed(
        list(semantic_queries),
        operation_id=f"public-ablation:{query.query_id}",
    )
    dense_retriever = PostgresDenseRetriever()
    dense_by_chunk: dict[UUID, RetrievalCandidate] = {}
    for vector in query_batch.vectors:
        candidates = await dense_retriever.retrieve(
            session,
            query_vector=list(vector),
            principal=principal,
            now=EVALUATION_TIME,
            limit=BRANCH_LIMIT,
        )
        for candidate in candidates:
            previous = dense_by_chunk.get(candidate.chunk_id)
            if previous is None or (candidate.dense_score or 0.0) > (
                previous.dense_score or 0.0
            ):
                dense_by_chunk[candidate.chunk_id] = candidate
    dense = _rerank_dense_candidates(dense_by_chunk)
    sparse = await PostgresSparseRetriever().retrieve(
        session,
        raw_query=spec.sparse_query,
        principal=principal,
        now=EVALUATION_TIME,
        limit=BRANCH_LIMIT,
    )
    exact = await PostgresExactRetriever().retrieve(
        session,
        raw_query=spec.raw_query,
        exact_terms=tuple(
            dict.fromkeys(
                (
                    *spec.exact_terms,
                    *spec.filters.error_codes,
                    *spec.filters.version_labels,
                )
            )
        ),
        principal=principal,
        now=EVALUATION_TIME,
        limit=BRANCH_LIMIT,
    )
    return spec, dense, sparse, exact


async def evaluate_ablation(
    database_url: str,
    benchmark: PublicBenchmark,
    *,
    provider_name: str,
    query_limit: int | None,
    chunking: ChunkingConfig,
) -> dict[str, Any]:
    database = Database(database_url)
    provider, embedding_model = _embedding_provider(database, provider_name)
    started_at = time.monotonic()
    try:
        department, key_to_official_id, chunk_count = await seed_public_corpus(
            database,
            benchmark,
            provider=provider,
            embedding_model=embedding_model,
            chunking=chunking,
        )
        selected_queries = (
            benchmark.queries[:query_limit] if query_limit else benchmark.queries
        )
        selected_qrels = {
            query.query_id: benchmark.qrels[query.query_id]
            for query in selected_queries
        }
        selected_benchmark = PublicBenchmark(
            manifest=benchmark.manifest,
            split=benchmark.split,
            documents=benchmark.documents,
            queries=selected_queries,
            qrels=selected_qrels,
        )
        query_provider = await _precompute_query_embeddings(
            provider, selected_benchmark
        )
        principal = Principal(
            user_id=uuid4(),
            session_id=uuid4(),
            email="public-ablation@example.com",
            display_name="Public retrieval ablation",
            role=UserRole.EMPLOYEE,
            department_id=department.id,
            department_key=department.key,
        )
        diversity = DocumentDiversitySelector(
            max_chunks_per_document=1,
            adaptive_max_chunks_per_document=1,
        )
        fusion = ReciprocalRankFusion(k=60)
        reranker = WeightedFeatureReranker()
        rankings: dict[str, dict[str, list[str]]] = {
            variant: {} for variant in VARIANTS
        }
        cases: list[dict[str, Any]] = []
        retrieval_started_at = time.monotonic()
        async with database.session() as session:
            for query_number, query in enumerate(selected_queries, start=1):
                spec, dense, sparse, exact = await _candidate_branches(
                    session,
                    query=query,
                    principal=principal,
                    query_provider=query_provider,
                )
                fused = fusion.fuse(dense, sparse, exact)
                weighted = await reranker.rerank(
                    spec.raw_query,
                    fused[:CANDIDATE_LIMIT],
                    analysis=spec,
                )
                selected_by_variant = {
                    "dense_only": diversity.select(dense, limit=RESULT_LIMIT),
                    "postgres_fts_only": diversity.select(sparse, limit=RESULT_LIMIT),
                    "hybrid_rrf": diversity.select(fused, limit=RESULT_LIMIT),
                    "hybrid_weighted": diversity.select(weighted, limit=RESULT_LIMIT),
                }
                case_variants: dict[str, Any] = {}
                for variant, candidates in selected_by_variant.items():
                    ranking = [
                        key_to_official_id[item.document_key] for item in candidates
                    ]
                    rankings[variant][query.query_id] = ranking
                    case_variants[variant] = {
                        "ranking": ranking,
                        "metrics": asdict(
                            query_metrics(ranking, selected_qrels[query.query_id])
                        ),
                    }
                cases.append(
                    {
                        "query_id": query.query_id,
                        "query": query.text,
                        "relevant_documents": sorted(
                            document_id
                            for document_id, score in selected_qrels[
                                query.query_id
                            ].items()
                            if score > 0
                        ),
                        "variants": case_variants,
                    }
                )
                if query_number % 25 == 0 or query_number == len(selected_queries):
                    print(
                        f"public ablation progress: {query_number}/{len(selected_queries)}",
                        file=sys.stderr,
                        flush=True,
                    )
        variant_metrics = {
            variant: aggregate_metrics(variant_rankings, selected_qrels)
            for variant, variant_rankings in rankings.items()
        }
        full_split = len(selected_queries) == len(benchmark.queries)
        return {
            "schema_version": "public-retrieval-ablation-v1",
            "dataset": {
                "id": benchmark.manifest.dataset_id,
                "split": benchmark.split,
                "checksum": {
                    "algorithm": benchmark.manifest.checksum_algorithm,
                    "value": benchmark.manifest.checksum,
                },
                "corpus_documents": len(benchmark.documents),
                "official_split_queries": len(benchmark.queries),
                "evaluated_queries": len(selected_queries),
                "full_official_split": full_split,
            },
            "system": {
                "embedding_provider": provider_name,
                "embedding_model": embedding_model,
                "chunk_target_tokens": chunking.target_tokens,
                "chunk_overlap_tokens": chunking.overlap_tokens,
                "indexed_chunks": chunk_count,
                "embedding_batch_size": EMBEDDING_BATCH_SIZE,
                "branch_limit": BRANCH_LIMIT,
                "candidate_limit": CANDIDATE_LIMIT,
                "result_limit": RESULT_LIMIT,
            },
            "variants": variant_metrics,
            "timing": {
                "retrieval_seconds": time.monotonic() - retrieval_started_at,
                "total_seconds": time.monotonic() - started_at,
            },
            "cases": cases,
            "report_usage": (
                "Comparable full-split public benchmark run"
                if full_split
                else "Smoke test only; do not report these metrics as a benchmark result"
            ),
        }
    finally:
        await provider.close()
        await database.close()


def write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    rows = "\n".join(
        "| "
        + variant
        + " | "
        + " | ".join(
            f"{metrics[name]:.4f}"
            for name in (
                "ndcg_at_10",
                "map_at_10",
                "recall_at_5",
                "recall_at_10",
                "mrr_at_10",
            )
        )
        + " |"
        for variant, metrics in report["variants"].items()
    )
    output.with_suffix(".md").write_text(
        "\n".join(
            (
                "# Public retrieval ablation",
                "",
                f"Full official split: `{str(report['dataset']['full_official_split']).lower()}`",
                "",
                "| Variant | nDCG@10 | MAP@10 | Recall@5 | Recall@10 | MRR@10 |",
                "|---|---:|---:|---:|---:|---:|",
                rows,
                "",
            )
        ),
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(BEIR_DATASETS), default="scifact")
    parser.add_argument("--split", default="test")
    parser.add_argument(
        "--embedding-provider",
        choices=("fake", "openai"),
        default=os.getenv("PUBLIC_RETRIEVAL_EMBEDDING_PROVIDER", "fake"),
    )
    parser.add_argument("--query-limit", type=int)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--chunk-target-tokens", type=int, default=500)
    parser.add_argument("--chunk-overlap-tokens", type=int, default=60)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    benchmark = load_beir_dataset(
        args.dataset,
        split=args.split,
        cache_dir=args.cache_dir,
        allow_download=not args.no_download,
    )
    configured = (
        os.getenv("TEST_DATABASE_ADMIN_URL")
        or os.getenv("MIGRATION_DATABASE_URL")
        or os.getenv("DATABASE_URL")
    )
    if not configured:
        raise SystemExit(
            "Set TEST_DATABASE_ADMIN_URL to run the isolated public ablation"
        )
    admin_url = make_url(configured).set(
        drivername="postgresql+psycopg", database="postgres"
    )
    database_name = f"test_public_ablation_{uuid4().hex}"
    target_url = admin_url.set(database=database_name)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    database_created = False
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        database_created = True
        environment = os.environ.copy()
        environment["MIGRATION_DATABASE_URL"] = target_url.render_as_string(
            hide_password=False
        )
        subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=BACKEND_ROOT,
            env=environment,
            check=True,
        )
        report = asyncio.run(
            evaluate_ablation(
                target_url.set(drivername="postgresql+asyncpg").render_as_string(
                    hide_password=False
                ),
                benchmark,
                provider_name=args.embedding_provider,
                query_limit=args.query_limit,
                chunking=ChunkingConfig(
                    target_tokens=args.chunk_target_tokens,
                    overlap_tokens=args.chunk_overlap_tokens,
                ),
            )
        )
        output = args.output or (
            DEFAULT_REPORT_DIR
            / args.dataset
            / f"{args.embedding_provider}-{args.split}-ablation.json"
        )
        write_report(report, output)
    finally:
        if database_created:
            with admin_engine.connect() as connection:
                connection.execute(
                    text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
                )
        admin_engine.dispose()
    print(json.dumps(report["variants"], indent=2))


if __name__ == "__main__":
    main()
