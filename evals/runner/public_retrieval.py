"""Evaluate the production retrieval pipeline on an official public BEIR split."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.auth.principal import Principal
from app.config import AIProvider, Settings
from app.db import Database
from app.db.models import (
    Department,
    Document,
    DocumentChunk,
    DocumentSection,
    DocumentVersion,
    DocumentVersionStatus,
    DocumentVisibility,
    UserRole,
)
from app.providers.embeddings import (
    EmbeddingBatch,
    EmbeddingProvider,
    FakeEmbeddingProvider,
)
from app.providers.factory import create_embedding_provider
from app.rag.chunking.splitter import (
    ChunkDraft,
    ChunkingConfig,
    SourceBlock,
    build_section_drafts,
    chunk_blocks,
)
from app.rag.retrieval.analysis import (
    DeterministicQueryAnalyzer,
    LowConfidenceRetry,
    QueryRewritePolicy,
)
from app.rag.retrieval.diversity import DocumentDiversitySelector
from app.rag.retrieval.models import RetrievalRequest
from app.rag.retrieval.query import HybridRetriever
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from evals.public.adapters.beir import BEIR_DATASETS, load_beir_dataset
from evals.public.contracts import PublicBenchmark
from evals.public.metrics import aggregate_metrics, query_metrics

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
DEFAULT_CACHE_DIR = ROOT / ".cache" / "public-benchmarks"
DEFAULT_REPORT_DIR = ROOT / "reports" / "public"
EVALUATION_TIME = datetime(2026, 10, 6, tzinfo=UTC)
EMBEDDING_BATCH_SIZE = 96
RESULT_LIMIT = 10
BRANCH_LIMIT = 100
CANDIDATE_LIMIT = 100


class _PrecomputedQueryEmbeddingProvider:
    """Serve benchmark query embeddings from a cache without changing retrieval behavior."""

    def __init__(
        self,
        *,
        vectors: dict[str, tuple[float, ...]],
        model: str,
        dimensions: int,
    ) -> None:
        self._vectors = vectors
        self._model = model
        self._dimensions = dimensions

    async def embed(self, texts: list[str], *, operation_id: str) -> EmbeddingBatch:
        missing = [text for text in texts if text not in self._vectors]
        if missing:
            raise KeyError(f"Query embedding was not precomputed: {missing[0]!r}")
        return EmbeddingBatch(
            vectors=tuple(self._vectors[text] for text in texts),
            model=self._model,
            dimensions=self._dimensions,
            provider_request_id=f"precomputed-{operation_id}",
            input_tokens=0,
        )

    async def close(self) -> None:
        return None


def _document_key(dataset_id: str, document_id: str) -> str:
    digest = hashlib.sha256(document_id.encode("utf-8")).hexdigest()[:32]
    return f"public-{dataset_id}-{digest}"


def _checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _embedding_provider(
    database: Database, provider_name: str
) -> tuple[EmbeddingProvider, str]:
    if provider_name == "fake":
        return FakeEmbeddingProvider(dimensions=1536), "fake-embedding-v2"
    if provider_name != "openai":
        raise ValueError("Embedding provider must be 'fake' or 'openai'")
    if os.getenv("RUN_PAID_PUBLIC_RETRIEVAL_BENCHMARK", "false").casefold() != "true":
        raise RuntimeError(
            "Set RUN_PAID_PUBLIC_RETRIEVAL_BENCHMARK=true to authorize a paid public run"
        )
    settings = Settings(embedding_provider=AIProvider.OPENAI)
    return (
        create_embedding_provider(settings, database, timeout_seconds=120.0),
        settings.embedding_model,
    )


async def _embed_chunks(
    session: AsyncSession,
    provider: EmbeddingProvider,
    pending: list[tuple[ChunkDraft, DocumentVersion]],
    *,
    dataset_id: str,
) -> None:
    for batch_number, start in enumerate(range(0, len(pending), EMBEDDING_BATCH_SIZE)):
        group = pending[start : start + EMBEDDING_BATCH_SIZE]
        batch = await provider.embed(
            [draft.content for draft, _ in group],
            operation_id=f"public:{dataset_id}:corpus:{batch_number}",
        )
        session.add_all(
            [
                DocumentChunk(
                    id=draft.id,
                    version_id=version.id,
                    section_id=draft.section_id,
                    ordinal=draft.ordinal,
                    section_chunk_index=draft.section_chunk_index,
                    page_number=draft.page_number,
                    section=draft.section,
                    section_path=list(draft.section_path),
                    source_path=draft.source_path,
                    source_token_start=draft.source_token_start,
                    source_token_end=draft.source_token_end,
                    content=draft.content,
                    token_count=draft.token_count,
                    content_hash=draft.content_hash,
                    embedding_model=batch.model,
                    embedding_dimensions=batch.dimensions,
                    embedding=list(vector),
                )
                for (draft, version), vector in zip(group, batch.vectors, strict=True)
            ]
        )
        await session.flush()


async def seed_public_corpus(
    database: Database,
    benchmark: PublicBenchmark,
    *,
    provider: EmbeddingProvider,
    embedding_model: str,
    chunking: ChunkingConfig,
) -> tuple[Department, dict[str, str], int]:
    """Index the full public corpus and return internal-to-official document mapping."""

    key_to_official_id: dict[str, str] = {}
    pending_chunks: list[tuple[ChunkDraft, DocumentVersion]] = []
    async with database.session() as session, session.begin():
        department = Department(key="public-eval", name="Public benchmark evaluation")
        session.add(department)
        await session.flush()
        for item in benchmark.documents:
            key = _document_key(benchmark.manifest.dataset_id, item.document_id)
            key_to_official_id[key] = item.document_id
            content = item.retrieval_text
            document = Document(
                document_key=key,
                title=(item.title.strip() or item.document_id)[:240],
                visibility=DocumentVisibility.COMPANY,
                department_id=None,
            )
            session.add(document)
            await session.flush()
            version = DocumentVersion(
                document_id=document.id,
                version_label="official",
                status=DocumentVersionStatus.PUBLISHED,
                authority=benchmark.manifest.display_name[:80],
                language="en",
                media_type="application/json",
                source_checksum=_checksum(content),
                storage_key=f"beir/{benchmark.manifest.dataset_id}/{item.document_id}",
                source_url=benchmark.manifest.homepage_url,
                effective_at=EVALUATION_TIME,
                expires_at=None,
                parser_version="beir-jsonl-v1",
                chunker_version=chunking.version,
                embedding_model=embedding_model,
                embedding_dimensions=1536,
            )
            session.add(version)
            await session.flush()
            source_path = f"beir/{benchmark.manifest.dataset_id}/{item.document_id}"
            block = SourceBlock(
                text=content,
                page_number=None,
                section=item.title[:240] or None,
                source_path=source_path[:500],
                section_path=(item.title[:240],) if item.title else (),
                section_level=1 if item.title else 0,
                content_types=("benchmark-document",),
            )
            section_drafts = build_section_drafts(version_id=version.id, blocks=[block])
            session.add_all(
                [
                    DocumentSection(
                        id=draft.id,
                        version_id=version.id,
                        parent_id=draft.parent_id,
                        ordinal=draft.ordinal,
                        level=draft.level,
                        title=draft.title,
                        section_path=list(draft.section_path),
                        content_types=list(draft.content_types),
                        content=draft.content,
                        token_count=draft.token_count,
                        page_number=draft.page_number,
                        source_path=draft.source_path,
                    )
                    for draft in section_drafts
                ]
            )
            drafts = chunk_blocks(
                version_id=version.id, blocks=[block], config=chunking
            )
            # The schema intentionally rejects duplicate chunks within one document version.
            unique_drafts = list(
                {draft.content_hash: draft for draft in drafts}.values()
            )
            pending_chunks.extend((draft, version) for draft in unique_drafts)
            document.current_version_id = version.id
        await _embed_chunks(
            session,
            provider,
            pending_chunks,
            dataset_id=benchmark.manifest.dataset_id,
        )
    return department, key_to_official_id, len(pending_chunks)


async def _precompute_query_embeddings(
    provider: EmbeddingProvider,
    benchmark: PublicBenchmark,
) -> _PrecomputedQueryEmbeddingProvider:
    analyzer = DeterministicQueryAnalyzer()
    rewrite_policy = QueryRewritePolicy()
    retry = LowConfidenceRetry()
    texts = tuple(
        dict.fromkeys(
            semantic_query
            for query in benchmark.queries
            for semantic_query in retry.semantic_queries(
                analyzer.analyze(RetrievalRequest(raw_query=query.text)),
                policy=rewrite_policy,
            )
        )
    )
    vectors: dict[str, tuple[float, ...]] = {}
    model = ""
    dimensions = 0
    for batch_number, start in enumerate(range(0, len(texts), EMBEDDING_BATCH_SIZE)):
        group = list(texts[start : start + EMBEDDING_BATCH_SIZE])
        batch = await provider.embed(
            group,
            operation_id=(
                f"public:{benchmark.manifest.dataset_id}:queries:{batch_number}"
            ),
        )
        model = batch.model
        dimensions = batch.dimensions
        vectors.update(zip(group, batch.vectors, strict=True))
    return _PrecomputedQueryEmbeddingProvider(
        vectors=vectors,
        model=model,
        dimensions=dimensions,
    )


async def evaluate(
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
        seed_started_at = time.monotonic()
        department, key_to_official_id, chunk_count = await seed_public_corpus(
            database,
            benchmark,
            provider=provider,
            embedding_model=embedding_model,
            chunking=chunking,
        )
        indexing_seconds = time.monotonic() - seed_started_at
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
        retriever = HybridRetriever(
            embedding_provider=query_provider,
            diversity_selector=DocumentDiversitySelector(
                max_chunks_per_document=1,
                adaptive_max_chunks_per_document=1,
            ),
            branch_limit=BRANCH_LIMIT,
            candidate_limit=CANDIDATE_LIMIT,
            result_limit=RESULT_LIMIT,
            expansion_per_hit=0,
        )
        principal = Principal(
            user_id=uuid4(),
            session_id=uuid4(),
            email="public-eval@example.com",
            display_name="Public retrieval benchmark",
            role=UserRole.EMPLOYEE,
            department_id=department.id,
            department_key=department.key,
        )
        rankings: dict[str, list[str]] = {}
        query_results: list[dict[str, Any]] = []
        latencies_ms: list[float] = []
        async with database.session() as session:
            query_started_all = time.monotonic()
            for query_number, query in enumerate(selected_queries, start=1):
                query_started_at = time.monotonic()
                hits = await retriever.search(
                    session,
                    query=query.text,
                    principal=principal,
                    operation_id=f"public:{benchmark.manifest.dataset_id}:query:{query.query_id}",
                    now=EVALUATION_TIME,
                )
                latency_ms = (time.monotonic() - query_started_at) * 1_000
                latencies_ms.append(latency_ms)
                ranking = [key_to_official_id[hit.document_key] for hit in hits]
                rankings[query.query_id] = ranking
                per_query_metrics = query_metrics(
                    ranking, selected_qrels[query.query_id]
                )
                query_results.append(
                    {
                        "query_id": query.query_id,
                        "query": query.text,
                        "ranking": ranking,
                        "relevant_documents": sorted(
                            document_id
                            for document_id, score in selected_qrels[
                                query.query_id
                            ].items()
                            if score > 0
                        ),
                        "metrics": asdict(per_query_metrics),
                        "latency_ms": latency_ms,
                    }
                )
                if query_number % 25 == 0 or query_number == len(selected_queries):
                    elapsed = time.monotonic() - query_started_all
                    print(
                        f"public benchmark progress: {query_number}/{len(selected_queries)} "
                        f"queries ({elapsed:.1f}s)",
                        file=sys.stderr,
                        flush=True,
                    )
        metrics = aggregate_metrics(rankings, selected_qrels)
        full_split = len(selected_queries) == len(benchmark.queries)
        return {
            "schema_version": "public-retrieval-report-v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "dataset": {
                "id": benchmark.manifest.dataset_id,
                "name": benchmark.manifest.display_name,
                "split": benchmark.split,
                "source_url": benchmark.manifest.source_url,
                "homepage_url": benchmark.manifest.homepage_url,
                "checksum": {
                    "algorithm": benchmark.manifest.checksum_algorithm,
                    "value": benchmark.manifest.checksum,
                },
                "citation_url": benchmark.manifest.citation_url,
                "license_note": benchmark.manifest.license_note,
                "corpus_documents": len(benchmark.documents),
                "official_split_queries": len(benchmark.queries),
                "evaluated_queries": len(selected_queries),
                "full_official_split": full_split,
            },
            "system": {
                "pipeline": "HybridRetriever",
                "embedding_provider": provider_name,
                "embedding_model": embedding_model,
                "reranker": "weighted_feature_v1",
                "result_limit": RESULT_LIMIT,
                "branch_limit": BRANCH_LIMIT,
                "candidate_limit": CANDIDATE_LIMIT,
                "chunk_target_tokens": chunking.target_tokens,
                "chunk_overlap_tokens": chunking.overlap_tokens,
                "indexed_chunks": chunk_count,
            },
            "metrics": metrics,
            "timing": {
                "indexing_seconds": indexing_seconds,
                "evaluation_seconds": sum(latencies_ms) / 1_000,
                "total_seconds": time.monotonic() - started_at,
                "mean_query_latency_ms": statistics.fmean(latencies_ms),
                "median_query_latency_ms": statistics.median(latencies_ms),
                "p95_query_latency_ms": sorted(latencies_ms)[
                    max(0, int(len(latencies_ms) * 0.95) - 1)
                ],
            },
            "results": query_results,
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
    metrics = report["metrics"]
    dataset = report["dataset"]
    markdown = output.with_suffix(".md")
    markdown.write_text(
        "\n".join(
            (
                f"# {dataset['name']} retrieval benchmark",
                "",
                f"- Split: `{dataset['split']}`",
                f"- Corpus: {dataset['corpus_documents']} documents",
                f"- Queries: {dataset['evaluated_queries']} / {dataset['official_split_queries']}",
                f"- Full official split: `{str(dataset['full_official_split']).lower()}`",
                f"- Usage: {report['report_usage']}",
                "",
                "## Metrics",
                "",
                "| Metric | Score |",
                "|---|---:|",
                *(f"| {name} | {value:.4f} |" for name, value in metrics.items()),
                "",
                "## Provenance",
                "",
                f"- Source: {dataset['source_url']}",
                f"- Checksum: `{dataset['checksum']['algorithm']}:{dataset['checksum']['value']}`",
                f"- Citation: {dataset['citation_url']}",
                f"- License note: {dataset['license_note']}",
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
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(os.getenv("PUBLIC_RETRIEVAL_CACHE_DIR", DEFAULT_CACHE_DIR)),
    )
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="JSON report path; defaults under reports/public/<dataset>/",
    )
    parser.add_argument("--chunk-target-tokens", type=int, default=500)
    parser.add_argument("--chunk-overlap-tokens", type=int, default=60)
    args = parser.parse_args()
    if args.query_limit is not None and args.query_limit < 1:
        parser.error("--query-limit must be positive")
    return args


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
            "Set TEST_DATABASE_ADMIN_URL to run the isolated public benchmark"
        )
    admin_url = make_url(configured).set(
        drivername="postgresql+psycopg", database="postgres"
    )
    database_name = f"test_public_retrieval_{uuid4().hex}"
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
            evaluate(
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
            / f"{args.embedding_provider}-{args.split}-retrieval.json"
        )
        write_report(report, output)
    finally:
        if database_created:
            with admin_engine.connect() as connection:
                connection.execute(
                    text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
                )
        admin_engine.dispose()
    print(json.dumps(report["metrics"], indent=2))


if __name__ == "__main__":
    main()
