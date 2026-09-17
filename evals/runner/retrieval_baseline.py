"""Run the M2 retrieval baseline against an isolated migrated PostgreSQL database."""

from __future__ import annotations

import asyncio
import hashlib
import json
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
    chunk_blocks,
)
from app.rag.citations.sources import build_evidence_output
from app.rag.ingestion.markdown_parser import MarkdownParser
from app.rag.retrieval.query import HybridRetriever
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
MANIFEST_PATH = ROOT / "data" / "manifests" / "documents.json"
CASES_PATH = ROOT / "evals" / "cases" / "retrieval-baseline.jsonl"
REPORT_JSON = ROOT / "reports" / "retrieval-baseline.json"
REPORT_MARKDOWN = ROOT / "reports" / "retrieval-baseline.md"
EVALUATION_TIME = datetime(2026, 9, 16, tzinfo=UTC)


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


def load_cases() -> list[RetrievalCase]:
    return [
        RetrievalCase(**json.loads(line))
        for line in CASES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def markdown_blocks(path: Path) -> list[SourceBlock]:
    extracted = MarkdownParser().parse(path)
    return [
        SourceBlock(section.text, None, section.title, path.name)
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
                    parser_version="markdown-v1",
                    chunker_version=CHUNKER_VERSION,
                    embedding_model="fake-embedding-v2",
                    embedding_dimensions=1536,
                )
                session.add(version)
                await session.flush()
                versions[item["version_label"]] = version
                drafts = chunk_blocks(
                    version_id=version.id,
                    blocks=markdown_blocks(ROOT / "data" / "knowledge" / item["path"]),
                    config=ChunkingConfig(target_tokens=120, overlap_tokens=20),
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
                            ordinal=draft.ordinal,
                            page_number=draft.page_number,
                            section=draft.section,
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
        recall_hits = 0
        reciprocal_rank_sum = 0.0
        answerable_count = 0
        no_answer_correct = 0
        no_answer_count = 0
        scope_leaks = 0
        scope_count = 0
        retriever = HybridRetriever(embedding_provider=provider)
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
                rank: int | None = None
                if case.expected_document_key:
                    answerable_count += 1
                    expected = (
                        f"{case.expected_document_key}:{case.expected_version_label}"
                    )
                    if expected in ranked:
                        rank = ranked.index(expected) + 1
                        recall_hits += 1
                        reciprocal_rank_sum += 1 / rank
                forbidden_returned = sorted(
                    {hit.document_key for hit in hits}
                    & set(case.forbidden_document_keys)
                )
                if case.forbidden_document_keys:
                    scope_count += 1
                    scope_leaks += bool(forbidden_returned)
                evidence = build_evidence_output(hits)
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
                        "top5": ranked,
                        "forbidden_returned": forbidden_returned,
                    }
                )
        recall = recall_hits / answerable_count
        return {
            "report_version": "retrieval-baseline-v1",
            "evaluated_at": EVALUATION_TIME.isoformat(),
            "corpus_snapshot": "m2-corpus-v1",
            "corpus_manifest_sha256": hashlib.sha256(
                MANIFEST_PATH.read_bytes()
            ).hexdigest(),
            "configuration": {
                "embedding": "fake-embedding-v2/1536",
                "parser": "markdown-v1",
                "chunker": CHUNKER_VERSION,
                "vector": "exact cosine top20",
                "lexical": "PostgreSQL simple FTS OR meaningful terms top20",
                "fusion": "max lexical coverage/cosine confidence; RRF(k=60) tie-break",
                "minimum_lexical_coverage": 0.5,
                "minimum_vector_similarity": 0.75,
            },
            "metrics": {
                "recall_at_5": {
                    "numerator": recall_hits,
                    "denominator": answerable_count,
                    "value": recall,
                },
                "mrr_at_5": {
                    "numerator_reciprocal_rank_sum": reciprocal_rank_sum,
                    "denominator": answerable_count,
                    "value": reciprocal_rank_sum / answerable_count,
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
                "g04_recall_gate": {"threshold": 0.85, "passed": recall >= 0.85},
            },
            "limitations": [
                "Fake hash embeddings validate wiring and reproducibility, not semantic quality.",
                "No-answer uses the retrieval/citation threshold; claim support needs WP-06.",
                "The dataset is development-only and must not be treated as a holdout set.",
            ],
            "cases": results,
        }
    finally:
        await database.close()


def write_report(report: dict[str, Any]) -> None:
    REPORT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    metrics = report["metrics"]
    failed = [
        case
        for case in report["cases"]
        if case["rank"] is None and case["expected_document"]
    ]
    false_answers = [
        case
        for case in report["cases"]
        if case["expected_outcome"] == "no_answer"
        and not case["forbidden_returned"]
        and case["retrieval_outcome"] != "no_answer"
    ]
    recall = metrics["recall_at_5"]
    mrr = metrics["mrr_at_5"]
    no_answer = metrics["no_answer_accuracy"]
    leakage = metrics["scope_leakage"]
    recall_row = f"| Recall@5 | {recall['numerator']} | {recall['denominator']} | {recall['value']:.3f} |"
    mrr_row = (
        f"| MRR@5 (sum RR / answerable) | {mrr['numerator_reciprocal_rank_sum']:.3f} "
        f"| {mrr['denominator']} | {mrr['value']:.3f} |"
    )
    no_answer_row = (
        f"| No-answer accuracy | {no_answer['numerator']} | {no_answer['denominator']} "
        f"| {no_answer['value']:.3f} |"
    )
    leakage_row = (
        f"| Scope leakage | {leakage['leaks']} | {leakage['denominator']} "
        f"| {leakage['value']:.3f} |"
    )
    markdown = f"""# Retrieval baseline — M2

Run against an isolated, freshly migrated PostgreSQL/pgvector database at
`{report["evaluated_at"]}` using corpus `{report["corpus_snapshot"]}`.

| Metric | Numerator | Denominator | Result |
|---|---:|---:|---:|
{recall_row}
{mrr_row}
{no_answer_row}
{leakage_row}

G-04 (`Recall@5 >= 0.85`): **{"PASS" if metrics["g04_recall_gate"]["passed"] else "FAIL"}**.

Answerable misses: {", ".join(case["case_id"] for case in failed) or "none"}.
No-answer false positives: {", ".join(case["case_id"] for case in false_answers) or "none"}.

## Limitations

""" + "".join(f"- {item}\n" for item in report["limitations"])
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
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
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
        with admin_engine.connect() as connection:
            connection.execute(
                text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
            )
        admin_engine.dispose()
    print(json.dumps(report["metrics"], indent=2))


if __name__ == "__main__":
    main()
