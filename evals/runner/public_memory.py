"""Run fast, provider-free retrieval evaluation on public memory datasets."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.public.metrics import aggregate_metrics, query_metrics
from evals.public_memory.adapters import MEMORY_DATASETS, load_memory_benchmark
from evals.public_memory.contracts import MemoryRecord, MemoryRetrievalBenchmark

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / ".cache" / "public-benchmarks"
DEFAULT_REPORT_DIR = ROOT / "reports" / "public" / "memory"
RESULT_LIMIT = 10
_TOKEN = re.compile(r"[\w.-]+", re.UNICODE)


def _terms(value: str) -> list[str]:
    return [item.casefold() for item in _TOKEN.findall(value) if len(item) > 1]


def _lexical_rank(
    query: str, records: Sequence[MemoryRecord]
) -> tuple[list[str], list[float]]:
    query_terms = set(_terms(query))
    scored = [
        (
            len(query_terms.intersection(_terms(record.text)))
            / max(1, min(8, len(query_terms))),
            record.record_id,
        )
        for record in records
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return (
        [record_id for _, record_id in scored[:RESULT_LIMIT]],
        [score for score, _ in scored[:RESULT_LIMIT]],
    )


def _bm25_rank(
    query: str,
    records: Sequence[MemoryRecord],
    *,
    k1: float = 0.9,
    b: float = 0.4,
) -> tuple[list[str], list[float]]:
    tokenized = [_terms(record.text) for record in records]
    document_frequencies: Counter[str] = Counter()
    for tokens in tokenized:
        document_frequencies.update(set(tokens))
    document_count = len(records)
    average_length = sum(map(len, tokenized)) / max(1, document_count)
    query_terms = set(_terms(query))
    scored: list[tuple[float, str]] = []
    for record, tokens in zip(records, tokenized, strict=True):
        frequencies = Counter(tokens)
        length_normalization = 1 - b + b * len(tokens) / max(1.0, average_length)
        score = 0.0
        for term in query_terms:
            frequency = frequencies.get(term, 0)
            if frequency == 0:
                continue
            document_frequency = document_frequencies[term]
            inverse_document_frequency = math.log(
                1
                + (document_count - document_frequency + 0.5)
                / (document_frequency + 0.5)
            )
            score += inverse_document_frequency * (
                frequency * (k1 + 1) / (frequency + k1 * length_normalization)
            )
        scored.append((score, record.record_id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return (
        [record_id for _, record_id in scored[:RESULT_LIMIT]],
        [score for score, _ in scored[:RESULT_LIMIT]],
    )


def _select_queries(
    benchmark: MemoryRetrievalBenchmark,
    *,
    query_limit: int | None,
    seed: int,
) -> tuple[Any, ...]:
    if query_limit is None or query_limit >= len(benchmark.queries):
        return benchmark.queries
    if query_limit < 1:
        raise ValueError("Query limit must be positive")
    ranked = sorted(
        benchmark.queries,
        key=lambda query: hashlib.sha256(f"{seed}:{query.query_id}".encode()).digest(),
    )
    return tuple(ranked[:query_limit])


def _evaluate_variant(
    benchmark: MemoryRetrievalBenchmark,
    *,
    queries: Sequence[Any],
    name: str,
    ranker: Callable[[str, Sequence[MemoryRecord]], tuple[list[str], list[float]]],
    include_results: bool,
) -> dict[str, Any]:
    records_by_id = {record.record_id: record for record in benchmark.records}
    started_at = time.monotonic()
    rankings: dict[str, list[str]] = {}
    qrels: dict[str, dict[str, int]] = {}
    results: list[dict[str, Any]] = []
    category_rankings: defaultdict[str, dict[str, list[str]]] = defaultdict(dict)
    category_qrels: defaultdict[str, dict[str, dict[str, int]]] = defaultdict(dict)
    for query in queries:
        candidates = [records_by_id[record_id] for record_id in query.candidate_ids]
        ranking, scores = ranker(query.text, candidates)
        judgments = {record_id: 1 for record_id in query.relevant_ids}
        rankings[query.query_id] = ranking
        qrels[query.query_id] = judgments
        category_rankings[query.category][query.query_id] = ranking
        category_qrels[query.category][query.query_id] = judgments
        if include_results:
            results.append(
                {
                    "query_id": query.query_id,
                    "category": query.category,
                    "query": query.text,
                    "answer": query.answer,
                    "candidate_count": len(candidates),
                    "relevant_records": list(query.relevant_ids),
                    "ranking": ranking,
                    "scores": scores,
                    "metrics": asdict(query_metrics(ranking, judgments)),
                }
            )
    duration = time.monotonic() - started_at
    result: dict[str, Any] = {
        "name": name,
        "metrics": aggregate_metrics(rankings, qrels),
        "metrics_by_category": {
            category: aggregate_metrics(
                category_rankings[category], category_qrels[category]
            )
            for category in sorted(category_rankings)
        },
        "timing": {
            "evaluation_seconds": duration,
            "mean_query_latency_ms": duration * 1_000 / max(1, len(queries)),
        },
    }
    if include_results:
        result["results"] = results
    return result


def run_benchmark(
    benchmark: MemoryRetrievalBenchmark,
    *,
    variants: Sequence[str],
    query_limit: int | None,
    seed: int,
    include_results: bool = False,
) -> dict[str, Any]:
    rankers: Mapping[
        str, Callable[[str, Sequence[MemoryRecord]], tuple[list[str], list[float]]]
    ] = {
        "lexical": _lexical_rank,
        "bm25": _bm25_rank,
    }
    unknown = set(variants) - set(rankers)
    if unknown:
        raise ValueError(f"Unknown retrieval variant: {min(unknown)!r}")
    queries = _select_queries(benchmark, query_limit=query_limit, seed=seed)
    return {
        "schema_version": "public-memory-retrieval-report-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": {
            "id": benchmark.manifest.dataset_id,
            "name": benchmark.manifest.display_name,
            "source_url": benchmark.manifest.source_url,
            "homepage_url": benchmark.manifest.homepage_url,
            "citation_url": benchmark.manifest.citation_url,
            "checksum": {
                "algorithm": benchmark.manifest.checksum_algorithm,
                "value": benchmark.manifest.checksum,
            },
            "benchmark_scope": benchmark.manifest.benchmark_scope,
            "paper_comparable": benchmark.manifest.paper_comparable,
            "license_note": benchmark.manifest.license_note,
            "official_queries": benchmark.official_query_count,
            "retrieval_eligible_queries": len(benchmark.queries),
            "excluded_queries": benchmark.excluded_query_count,
            "evaluated_queries": len(queries),
            "full_retrieval_split": len(queries) == len(benchmark.queries),
            "indexed_records": len(benchmark.records),
        },
        "sampling": {"query_limit": query_limit, "seed": seed},
        "includes_per_query_results": include_results,
        "derivation": dict(benchmark.derivation),
        "systems": {
            "lexical": (
                "Current episodic-memory token-overlap formula without service or recency boost"
            ),
            "bm25": "Dependency-free Okapi BM25 (k1=0.9, b=0.4) over candidate sessions",
        },
        "variants": {
            variant: _evaluate_variant(
                benchmark,
                queries=queries,
                name=variant,
                ranker=rankers[variant],
                include_results=include_results,
            )
            for variant in variants
        },
    }


def _write_markdown(report: Mapping[str, Any], destination: Path) -> None:
    dataset = report["dataset"]
    lines = [
        f"# {dataset['name']} memory retrieval",
        "",
        f"- Scope: {dataset['benchmark_scope']}",
        f"- Paper comparable: **{str(dataset['paper_comparable']).lower()}**",
        (
            f"- Evaluated queries: {dataset['evaluated_queries']} / "
            f"{dataset['retrieval_eligible_queries']}"
        ),
        f"- Indexed records: {dataset['indexed_records']}",
        "",
        "| Variant | nDCG@10 | MAP@10 | Recall@5 | Recall@10 | MRR@10 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, result in report["variants"].items():
        metrics = result["metrics"]
        lines.append(
            f"| {name} | {metrics['ndcg_at_10']:.4f} | {metrics['map_at_10']:.4f} | "
            f"{metrics['recall_at_5']:.4f} | {metrics['recall_at_10']:.4f} | "
            f"{metrics['mrr_at_10']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            str(report["derivation"].get("warning", dataset["benchmark_scope"])),
            "",
            f"Source: {dataset['homepage_url']}",
        ]
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(MEMORY_DATASETS), required=True)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--query-limit", type=int)
    parser.add_argument("--distractors", type=int, default=31)
    parser.add_argument("--seed", type=int, default=20261008)
    parser.add_argument("--variant", action="append", choices=("lexical", "bm25"))
    parser.add_argument(
        "--include-results",
        action="store_true",
        help="Include per-query rankings in JSON (large on full runs)",
    )
    parser.add_argument("--no-download", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    benchmark = load_memory_benchmark(
        args.dataset,
        cache_dir=args.cache_dir,
        distractor_count=args.distractors,
        seed=args.seed,
        allow_download=not args.no_download,
    )
    report = run_benchmark(
        benchmark,
        variants=tuple(args.variant or ("lexical", "bm25")),
        query_limit=args.query_limit,
        seed=args.seed,
        include_results=args.include_results,
    )
    destination = args.report_dir / args.dataset
    destination.mkdir(parents=True, exist_ok=True)
    report_stem = (
        f"retrieval-smoke-{args.query_limit}"
        if args.query_limit is not None
        else "retrieval"
    )
    json_path = destination / f"{report_stem}.json"
    markdown_path = destination / f"{report_stem}.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_markdown(report, markdown_path)
    summary = {
        "dataset": report["dataset"],
        "metrics": {
            name: result["metrics"] for name, result in report["variants"].items()
        },
        "reports": {"json": str(json_path), "markdown": str(markdown_path)},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
