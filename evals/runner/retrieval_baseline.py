"""Run the M2 retrieval baseline against an isolated migrated PostgreSQL database."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.auth.principal import Principal
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
from app.providers.embeddings import FakeEmbeddingProvider
from app.rag.chunking.splitter import (
    CHUNKER_VERSION,
    ChunkingConfig,
    SourceBlock,
    build_section_drafts,
    chunk_blocks,
)
from app.rag.citations.sources import build_evidence_output
from app.rag.ingestion.markdown_parser import MARKDOWN_PARSER_VERSION, MarkdownParser
from app.rag.retrieval.query import HybridRetriever
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from evals.runner.retrieval_metrics import (
    duplicate_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank_at_k,
    unique_at_k,
)

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
MANIFEST_PATH = ROOT / "data" / "manifests" / "documents.json"
CASES_PATH = ROOT / "evals" / "cases" / "retrieval-baseline.jsonl"
CASES_SCHEMA_PATH = ROOT / "evals" / "cases" / "retrieval-baseline.schema.json"
REPORT_ROOT = Path(os.getenv("RETRIEVAL_REPORT_DIR", ROOT / "reports"))
REPORT_JSON = REPORT_ROOT / "retrieval-baseline.json"
REPORT_MARKDOWN = REPORT_ROOT / "retrieval-baseline.md"
EVALUATION_TIME = datetime(2026, 9, 16, tzinfo=UTC)
RESULT_LIMIT = 5
BRANCH_LIMIT = 20
RRF_K = 60
CHUNK_TARGET_TOKENS = 120
CHUNK_OVERLAP_TOKENS = 20


@dataclass(frozen=True, slots=True)
class RelevantDocument:
    document_key: str
    version_label: str
    relevance: int

    @property
    def identifier(self) -> str:
        return f"{self.document_key}:{self.version_label}"


@dataclass(frozen=True, slots=True)
class RetrievalCase:
    case_id: str
    query: str
    role: str
    department_key: str
    expected_outcome: str
    expected_document_key: str | None
    expected_version_label: str | None
    forbidden_document_keys: list[str]
    relevant_documents: list[RelevantDocument]
    tags: list[str]


def load_cases() -> list[RetrievalCase]:
    cases: list[RetrievalCase] = []
    validator = Draft202012Validator(
        json.loads(CASES_SCHEMA_PATH.read_text(encoding="utf-8"))
    )
    for line_number, line in enumerate(
        CASES_PATH.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        raw = json.loads(line)
        errors = sorted(validator.iter_errors(raw), key=lambda error: list(error.path))
        if errors:
            details = "; ".join(error.message for error in errors)
            raise ValueError(f"{CASES_PATH}:{line_number}: {details}")
        relevant = [RelevantDocument(**item) for item in raw.pop("relevant_documents")]
        case = RetrievalCase(relevant_documents=relevant, **raw)
        expected = (
            f"{case.expected_document_key}:{case.expected_version_label}"
            if case.expected_document_key
            else None
        )
        if case.expected_outcome == "answered" and expected not in {
            item.identifier for item in relevant
        }:
            raise ValueError(
                f"{CASES_PATH}:{line_number}: expected document is not relevant"
            )
        cases.append(case)
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Retrieval case IDs must be unique")
    return cases


def markdown_blocks(path: Path) -> list[SourceBlock]:
    extracted = MarkdownParser().parse(path)
    return [
        SourceBlock(
            section.text,
            None,
            section.title,
            path.name,
            section.section_path,
            section.heading_level,
            section.content_types,
        )
        for section in extracted.sections
    ]


async def seed_corpus(database: Database) -> dict[str, Department]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    provider = FakeEmbeddingProvider(dimensions=1536)
    async with database.session() as session, session.begin():
        departments = {
            key: Department(key=key, name=key.title())
            for key in ("engineering", "operations")
        }
        session.add_all(departments.values())
        await session.flush()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in manifest["documents"]:
            grouped.setdefault(item["document_key"], []).append(item)

        for document_key, items in grouped.items():
            latest = max(
                (
                    item
                    for item in items
                    if datetime.fromisoformat(
                        item["effective_at"].replace("Z", "+00:00")
                    )
                    <= EVALUATION_TIME
                    and (
                        item["expires_at"] is None
                        or datetime.fromisoformat(
                            item["expires_at"].replace("Z", "+00:00")
                        )
                        > EVALUATION_TIME
                    )
                ),
                key=lambda item: int(item["version_label"][1:]),
            )
            visibility = DocumentVisibility(latest["visibility"])
            department = departments.get(latest["department_key"])
            document = Document(
                document_key=document_key,
                title=latest["title"],
                visibility=visibility,
                department_id=department.id if department else None,
            )
            session.add(document)
            await session.flush()
            versions: dict[str, DocumentVersion] = {}
            for item in items:
                is_current = item is latest
                version = DocumentVersion(
                    document_id=document.id,
                    version_label=item["version_label"],
                    status=(
                        DocumentVersionStatus.PUBLISHED
                        if is_current
                        else DocumentVersionStatus.SUPERSEDED
                    ),
                    authority=item["authority"],
                    language=item["language"],
                    media_type=item["media_type"],
                    source_checksum=item["checksum"].removeprefix("sha256:"),
                    storage_key=item["path"],
                    effective_at=datetime.fromisoformat(
                        item["effective_at"].replace("Z", "+00:00")
                    ),
                    expires_at=(
                        datetime.fromisoformat(
                            item["expires_at"].replace("Z", "+00:00")
                        )
                        if item["expires_at"]
                        else None
                    ),
                    parser_version=MARKDOWN_PARSER_VERSION,
                    chunker_version=CHUNKER_VERSION,
                    embedding_model="fake-embedding-v2",
                    embedding_dimensions=1536,
                )
                session.add(version)
                await session.flush()
                versions[item["version_label"]] = version
                blocks = markdown_blocks(ROOT / "data" / "knowledge" / item["path"])
                section_drafts = build_section_drafts(
                    version_id=version.id, blocks=blocks
                )
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
                await session.flush()
                drafts = chunk_blocks(
                    version_id=version.id,
                    blocks=blocks,
                    config=ChunkingConfig(
                        target_tokens=CHUNK_TARGET_TOKENS,
                        overlap_tokens=CHUNK_OVERLAP_TOKENS,
                    ),
                )
                batch = await provider.embed(
                    [draft.content for draft in drafts],
                    operation_id=f"seed:{document_key}:{item['version_label']}",
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
                        for draft, vector in zip(drafts, batch.vectors, strict=True)
                    ]
                )
            document.current_version_id = versions[latest["version_label"]].id
    return departments


async def evaluate(database_url: str) -> dict[str, Any]:
    database = Database(database_url)
    provider = FakeEmbeddingProvider(dimensions=1536)
    try:
        departments = await seed_corpus(database)
        cases = load_cases()
        results: list[dict[str, Any]] = []
        recall_sum = 0.0
        precision_sum = 0.0
        reciprocal_rank_sum = 0.0
        ndcg_sum = 0.0
        duplicate_rate_sum = 0.0
        answerable_count = 0
        no_answer_correct = 0
        no_answer_count = 0
        scope_leaks = 0
        scope_count = 0
        known_gap_count = 0
        known_gap_hits = 0
        citation_relevant_hits = 0
        citation_count_sum = 0
        citation_context_token_sum = 0
        citation_context_token_max = 0
        expanded_chunk_sum = 0
        retriever = HybridRetriever(
            embedding_provider=provider,
            branch_limit=BRANCH_LIMIT,
            result_limit=RESULT_LIMIT,
            candidate_limit=20,
            expansion_per_hit=2,
            rrf_k=RRF_K,
        )
        async with database.session() as session:
            for case in cases:
                department = departments[case.department_key]
                principal = Principal(
                    user_id=uuid4(),
                    session_id=uuid4(),
                    email=f"{case.case_id}@example.com",
                    display_name=case.case_id,
                    role=UserRole(case.role),
                    department_id=department.id,
                    department_key=department.key,
                )
                hits = await retriever.search(
                    session,
                    query=case.query,
                    principal=principal,
                    operation_id=f"baseline:{case.case_id}",
                    now=EVALUATION_TIME,
                )
                ranked = [f"{hit.document_key}:{hit.version_label}" for hit in hits]
                unique_ranked = unique_at_k(ranked, RESULT_LIMIT)
                relevant = {item.identifier for item in case.relevant_documents}
                relevance = {
                    item.identifier: item.relevance for item in case.relevant_documents
                }
                rank: int | None = None
                if case.expected_outcome == "answered":
                    answerable_count += 1
                    case_recall = recall_at_k(ranked, relevant, RESULT_LIMIT)
                    case_precision = precision_at_k(ranked, relevant, RESULT_LIMIT)
                    case_rr = reciprocal_rank_at_k(ranked, relevant, RESULT_LIMIT)
                    case_ndcg = ndcg_at_k(ranked, relevance, RESULT_LIMIT)
                    recall_sum += case_recall
                    precision_sum += case_precision
                    reciprocal_rank_sum += case_rr
                    ndcg_sum += case_ndcg
                    if case_rr:
                        rank = next(
                            index
                            for index, identifier in enumerate(unique_ranked, start=1)
                            if identifier in relevant
                        )
                elif case.expected_outcome == "known_gap":
                    known_gap_count += 1
                    known_gap_hits += bool(set(ranked) & relevant)
                case_duplicate_rate = duplicate_rate_at_k(ranked, RESULT_LIMIT)
                duplicate_rate_sum += case_duplicate_rate
                forbidden_returned = sorted(
                    {hit.document_key for hit in hits}
                    & set(case.forbidden_document_keys)
                )
                if case.forbidden_document_keys:
                    scope_count += 1
                    scope_leaks += bool(forbidden_returned)
                evidence = build_evidence_output(hits)
                expanded_count = sum(hit.expansion_kind is not None for hit in hits)
                expanded_chunk_sum += expanded_count
                evidence_tokens = sum(
                    max(1, math.ceil(len(item.encode("utf-8")) / 3))
                    for item in evidence.context
                )
                citation_context_token_sum += evidence_tokens
                citation_context_token_max = max(
                    citation_context_token_max, evidence_tokens
                )
                citation_count_sum += len(evidence.sources)
                relevant_citation = any(
                    f"{source.document_key}:{source.version_label}"
                    in {item.identifier for item in case.relevant_documents}
                    for source in evidence.sources
                )
                if case.expected_outcome == "answered" and relevant_citation:
                    citation_relevant_hits += 1
                if (
                    case.expected_outcome == "no_answer"
                    and not case.forbidden_document_keys
                ):
                    no_answer_count += 1
                    no_answer_correct += evidence.outcome == "no_answer"
                results.append(
                    {
                        "case_id": case.case_id,
                        "expected_outcome": case.expected_outcome,
                        "retrieval_outcome": evidence.outcome,
                        "expected_document": (
                            f"{case.expected_document_key}:{case.expected_version_label}"
                            if case.expected_document_key
                            else None
                        ),
                        "rank": rank,
                        "top5": ranked[:RESULT_LIMIT],
                        "retrieved_result_count": len(hits),
                        "primary_result_count": len(hits) - expanded_count,
                        "expanded_chunk_count": expanded_count,
                        "selected_citation_count": len(evidence.sources),
                        "selected_citation_documents": [
                            f"{source.document_key}:{source.version_label}"
                            for source in evidence.sources
                        ],
                        "citation_context_estimated_tokens": evidence_tokens,
                        "expected_document_cited": relevant_citation,
                        "tags": case.tags,
                        "relevant_documents": sorted(relevant),
                        "duplicate_rate_at_5": case_duplicate_rate,
                        "forbidden_returned": forbidden_returned,
                    }
                )
        recall = recall_sum / answerable_count
        case_count = len(cases)
        return {
            "report_version": "retrieval-baseline-v2",
            "evaluated_at": EVALUATION_TIME.isoformat(),
            "corpus_snapshot": "m2-corpus-v1",
            "corpus_manifest_sha256": hashlib.sha256(
                MANIFEST_PATH.read_bytes()
            ).hexdigest(),
            "dataset": {
                "path": str(CASES_PATH.relative_to(ROOT)),
                "sha256": hashlib.sha256(CASES_PATH.read_bytes()).hexdigest(),
                "case_count": case_count,
                "tags": sorted({tag for case in cases for tag in case.tags}),
            },
            "configuration": {
                "schema_version": "retrieval-config-v1",
                "embedding": {
                    "provider": "fake",
                    "model": "fake-embedding-v2",
                    "dimensions": 1536,
                },
                "parser": {"name": "markdown", "version": MARKDOWN_PARSER_VERSION},
                "chunking": {
                    "version": CHUNKER_VERSION,
                    "target_tokens": CHUNK_TARGET_TOKENS,
                    "overlap_tokens": CHUNK_OVERLAP_TOKENS,
                },
                "structure": {
                    "parent_store": "document_sections",
                    "leaf_store": "document_chunks",
                    "section_path_preserved": True,
                    "content_types_preserved": True,
                },
                "dense": {"strategy": "exact_cosine", "candidate_limit": BRANCH_LIMIT},
                "sparse": {
                    "strategy": "postgres_simple_fts_or_terms",
                    "candidate_limit": BRANCH_LIMIT,
                    "preserves_original_query": True,
                },
                "fusion": {
                    "strategy": "reciprocal_rank_fusion",
                    "rrf_k": RRF_K,
                },
                "reranker": {
                    "strategy": "weighted_feature_v1",
                    "candidate_limit": 20,
                    "weights": {
                        "query_term_coverage": 0.55,
                        "exact_identifier_match": 0.25,
                        "normalized_rrf": 0.15,
                        "dense_score": 0.05,
                    },
                },
                "context_expansion": {
                    "strategy": "acl_scoped_neighbor_and_parent_section",
                    "neighbors_per_seed_each_direction": 2,
                },
                "citation_selection": {
                    "max_sources": 5,
                    "estimated_context_token_budget": 6000,
                    "near_duplicate_jaccard_threshold": 0.82,
                    "near_duplicate_scope": "same_document_version",
                },
                "version_scope": "published_current_effective_unexpired",
                "result_limit": RESULT_LIMIT,
            },
            "metrics": {
                "recall_at_5": {
                    "numerator": recall_sum,
                    "denominator": answerable_count,
                    "value": recall,
                },
                "precision_at_5": {
                    "numerator_sum": precision_sum,
                    "denominator": answerable_count,
                    "value": precision_sum / answerable_count,
                },
                "mrr_at_5": {
                    "numerator_reciprocal_rank_sum": reciprocal_rank_sum,
                    "denominator": answerable_count,
                    "value": reciprocal_rank_sum / answerable_count,
                },
                "ndcg_at_5": {
                    "numerator_sum": ndcg_sum,
                    "denominator": answerable_count,
                    "value": ndcg_sum / answerable_count,
                },
                "duplicate_rate_at_5": {
                    "numerator_sum": duplicate_rate_sum,
                    "denominator": case_count,
                    "value": duplicate_rate_sum / case_count,
                },
                "known_gap_historical_version": {
                    "retrieved": known_gap_hits,
                    "denominator": known_gap_count,
                    "value": known_gap_hits / known_gap_count
                    if known_gap_count
                    else 0.0,
                },
                "no_answer_accuracy": {
                    "numerator": no_answer_correct,
                    "denominator": no_answer_count,
                    "value": no_answer_correct / no_answer_count,
                },
                "scope_leakage": {
                    "leaks": scope_leaks,
                    "denominator": scope_count,
                    "value": scope_leaks / scope_count,
                },
                "expected_document_citation_rate": {
                    "numerator": citation_relevant_hits,
                    "denominator": answerable_count,
                    "value": citation_relevant_hits / answerable_count
                    if answerable_count
                    else 0.0,
                },
                "selected_citations_per_case": {
                    "sum": citation_count_sum,
                    "denominator": case_count,
                    "mean": citation_count_sum / case_count if case_count else 0.0,
                },
                "citation_context_estimated_tokens": {
                    "sum": citation_context_token_sum,
                    "denominator": case_count,
                    "mean": citation_context_token_sum / case_count
                    if case_count
                    else 0.0,
                    "max_case": citation_context_token_max,
                    "budget": 6000,
                },
                "expanded_chunks_per_case": {
                    "sum": expanded_chunk_sum,
                    "denominator": case_count,
                    "mean": expanded_chunk_sum / case_count if case_count else 0.0,
                },
                "g04_recall_gate": {"threshold": 0.85, "passed": recall >= 0.85},
            },
            "limitations": [
                "Fake hash embeddings validate wiring and reproducibility, not semantic quality.",
                "Historical version requests are measured as a known gap and excluded from the release gate.",
                "Precision and duplicate rate are measured at document-version level.",
                "No-answer uses the retrieval/citation threshold; claim support needs WP-06.",
                "Citation quality is measured against expected document/version labels; chunk-level claim support is not labeled.",
                "The dataset is development-only and must not be treated as a holdout set.",
            ],
            "cases": results,
        }
    finally:
        await database.close()


def write_report(report: dict[str, Any]) -> None:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    metrics = report["metrics"]
    failed = [
        case
        for case in report["cases"]
        if case["rank"] is None
        and case["expected_document"]
        and case["expected_outcome"] == "answered"
    ]
    false_answers = [
        case
        for case in report["cases"]
        if case["expected_outcome"] == "no_answer"
        and not case["forbidden_returned"]
        and case["retrieval_outcome"] != "no_answer"
    ]
    recall = metrics["recall_at_5"]
    precision = metrics["precision_at_5"]
    mrr = metrics["mrr_at_5"]
    ndcg = metrics["ndcg_at_5"]
    duplicates = metrics["duplicate_rate_at_5"]
    historical = metrics["known_gap_historical_version"]
    no_answer = metrics["no_answer_accuracy"]
    leakage = metrics["scope_leakage"]
    citation_rate = metrics["expected_document_citation_rate"]
    citation_count = metrics["selected_citations_per_case"]
    citation_tokens = metrics["citation_context_estimated_tokens"]
    expansion = metrics["expanded_chunks_per_case"]
    recall_row = f"| Recall@5 | {recall['numerator']} | {recall['denominator']} | {recall['value']:.3f} |"
    mrr_row = (
        f"| MRR@5 (sum RR / answerable) | {mrr['numerator_reciprocal_rank_sum']:.3f} "
        f"| {mrr['denominator']} | {mrr['value']:.3f} |"
    )
    precision_row = (
        f"| Precision@5 (document-version) | {precision['numerator_sum']:.3f} "
        f"| {precision['denominator']} | {precision['value']:.3f} |"
    )
    ndcg_row = (
        f"| nDCG@5 | {ndcg['numerator_sum']:.3f} | {ndcg['denominator']} "
        f"| {ndcg['value']:.3f} |"
    )
    duplicate_row = (
        f"| Duplicate rate@5 | {duplicates['numerator_sum']:.3f} "
        f"| {duplicates['denominator']} | {duplicates['value']:.3f} |"
    )
    historical_row = (
        f"| Historical-version known gap | {historical['retrieved']} "
        f"| {historical['denominator']} | {historical['value']:.3f} |"
    )
    no_answer_row = (
        f"| No-answer accuracy | {no_answer['numerator']} | {no_answer['denominator']} "
        f"| {no_answer['value']:.3f} |"
    )
    leakage_row = (
        f"| Scope leakage | {leakage['leaks']} | {leakage['denominator']} "
        f"| {leakage['value']:.3f} |"
    )
    citation_row = (
        f"| Expected document cited | {citation_rate['numerator']} | "
        f"{citation_rate['denominator']} | {citation_rate['value']:.3f} |"
    )
    markdown = (
        f"""# Retrieval benchmark — Phase 3

Run against an isolated, freshly migrated PostgreSQL/pgvector database at
`{report["evaluated_at"]}` using corpus `{report["corpus_snapshot"]}`.

Configuration: reranker `{report["configuration"]["reranker"]["strategy"]}`, """
        + (
            f"candidate pool {report['configuration']['reranker']['candidate_limit']}, "
            f"neighbor/parent expansion up to "
            f"{report['configuration']['context_expansion']['neighbors_per_seed_each_direction']} "
            f"neighbors per seed, max {report['configuration']['citation_selection']['max_sources']} "
            f"citations and {report['configuration']['citation_selection']['estimated_context_token_budget']} "
            "estimated context tokens.\n\n"
        )
        + f"""| Metric | Numerator | Denominator | Result |
|---|---:|---:|---:|
{recall_row}
{precision_row}
{mrr_row}
{ndcg_row}
{duplicate_row}
{historical_row}
{no_answer_row}
{leakage_row}
{citation_row}

G-04 (`Recall@5 >= 0.85`): **{"PASS" if metrics["g04_recall_gate"]["passed"] else "FAIL"}**.

Phase 3 context: average {expansion["mean"]:.2f} expanded chunks per query; average
{citation_count["mean"]:.2f} selected citations; average {citation_tokens["mean"]:.0f}
estimated citation context tokens (maximum observed {citation_tokens["max_case"]}, budget
{citation_tokens["budget"]}).

Answerable misses: {", ".join(case["case_id"] for case in failed) or "none"}.
No-answer false positives: {", ".join(case["case_id"] for case in false_answers) or "none"}.

## Limitations

"""
        + "".join(f"- {item}\n" for item in report["limitations"])
    )
    REPORT_MARKDOWN.write_text(markdown, encoding="utf-8")


def main() -> None:
    configured = os.getenv("TEST_DATABASE_ADMIN_URL") or os.getenv(
        "MIGRATION_DATABASE_URL"
    )
    if not configured:
        raise SystemExit(
            "Set TEST_DATABASE_ADMIN_URL to run the isolated retrieval baseline"
        )
    admin_url = make_url(configured).set(
        drivername="postgresql+psycopg", database="postgres"
    )
    database_name = f"test_retrieval_eval_{uuid4().hex}"
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
                )
            )
        )
        write_report(report)
    finally:
        if not database_name.startswith("test_retrieval_eval_"):
            raise RuntimeError("Refusing to drop a database outside the eval namespace")
        if database_created:
            with admin_engine.connect() as connection:
                connection.execute(
                    text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
                )
        admin_engine.dispose()
    print(json.dumps(report["metrics"], indent=2))


if __name__ == "__main__":
    main()
