"""Run a reproducible whole-document BM25 anchor on a public BEIR split."""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import bm25s  # type: ignore[import-untyped]
import Stemmer  # type: ignore[import-not-found]

from evals.public.adapters.beir import BEIR_DATASETS, load_beir_dataset
from evals.public.contracts import PublicBenchmark
from evals.public.metrics import aggregate_metrics, query_metrics

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = ROOT / ".cache" / "public-benchmarks"
DEFAULT_REPORT_DIR = ROOT / "reports" / "public"
RESULT_LIMIT = 10
DEFAULT_K1 = 0.9
DEFAULT_B = 0.4
SCIFACT_ANSERINI_FLAT_NDCG_AT_10 = 0.6789
SCIFACT_ANSERINI_REFERENCE = (
    "https://github.com/castorini/anserini/blob/master/docs/reproduce/"
    "from-document-collection/beir-v1.0.0-scifact.flat.md"
)


def run_bm25(
    benchmark: PublicBenchmark,
    *,
    k1: float = DEFAULT_K1,
    b: float = DEFAULT_B,
) -> dict[str, Any]:
    started_at = time.monotonic()
    corpus = [document.retrieval_text for document in benchmark.documents]
    document_ids = [document.document_id for document in benchmark.documents]
    queries = [query.text for query in benchmark.queries]
    stemmer = Stemmer.Stemmer("english")

    indexing_started_at = time.monotonic()
    corpus_tokens = bm25s.tokenize(
        corpus,
        stopwords="en",
        stemmer=stemmer,
        show_progress=False,
    )
    retriever = bm25s.BM25(k1=k1, b=b, method="lucene")
    retriever.index(corpus_tokens, show_progress=False)
    indexing_seconds = time.monotonic() - indexing_started_at

    query_tokens = bm25s.tokenize(
        queries,
        stopwords="en",
        stemmer=stemmer,
        show_progress=False,
    )
    retrieval_started_at = time.monotonic()
    retrieved = retriever.retrieve(
        query_tokens,
        corpus=document_ids,
        k=min(RESULT_LIMIT, len(document_ids)),
        show_progress=False,
    )
    retrieval_seconds = time.monotonic() - retrieval_started_at

    rankings: dict[str, list[str]] = {}
    results: list[dict[str, Any]] = []
    per_query_latency_ms = retrieval_seconds * 1_000 / len(benchmark.queries)
    for query_index, query in enumerate(benchmark.queries):
        ranking = [str(item) for item in retrieved.documents[query_index].tolist()]
        scores = [float(item) for item in retrieved.scores[query_index].tolist()]
        rankings[query.query_id] = ranking
        results.append(
            {
                "query_id": query.query_id,
                "query": query.text,
                "ranking": ranking,
                "scores": scores,
                "relevant_documents": sorted(
                    document_id
                    for document_id, score in benchmark.qrels[query.query_id].items()
                    if score > 0
                ),
                "metrics": asdict(
                    query_metrics(ranking, benchmark.qrels[query.query_id])
                ),
            }
        )
    metrics = aggregate_metrics(rankings, benchmark.qrels)
    reference_score = (
        SCIFACT_ANSERINI_FLAT_NDCG_AT_10
        if benchmark.manifest.dataset_id == "scifact" and benchmark.split == "test"
        else None
    )
    return {
        "schema_version": "public-retrieval-report-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": {
            "id": benchmark.manifest.dataset_id,
            "name": benchmark.manifest.display_name,
            "split": benchmark.split,
            "source_url": benchmark.manifest.source_url,
            "checksum": {
                "algorithm": benchmark.manifest.checksum_algorithm,
                "value": benchmark.manifest.checksum,
            },
            "corpus_documents": len(benchmark.documents),
            "official_split_queries": len(benchmark.queries),
            "evaluated_queries": len(benchmark.queries),
            "full_official_split": True,
        },
        "system": {
            "pipeline": "bm25s",
            "version": bm25s.__version__,
            "method": "lucene",
            "k1": k1,
            "b": b,
            "tokenization": "english stopwords + PyStemmer english",
            "document_granularity": "whole_document",
            "result_limit": RESULT_LIMIT,
        },
        "metrics": metrics,
        "reference": {
            "system": "Anserini flat BM25",
            "ndcg_at_10": reference_score,
            "absolute_difference": (
                metrics["ndcg_at_10"] - reference_score
                if reference_score is not None
                else None
            ),
            "url": SCIFACT_ANSERINI_REFERENCE,
        },
        "timing": {
            "indexing_seconds": indexing_seconds,
            "evaluation_seconds": retrieval_seconds,
            "total_seconds": time.monotonic() - started_at,
            "mean_query_latency_ms": per_query_latency_ms,
            "median_query_latency_ms": per_query_latency_ms,
            "p95_query_latency_ms": per_query_latency_ms,
        },
        "results": results,
        "report_usage": "Comparable full-split public benchmark run",
    }


def write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    dataset = report["dataset"]
    metrics = report["metrics"]
    reference = report["reference"]
    output.with_suffix(".md").write_text(
        "\n".join(
            (
                f"# {dataset['name']} BM25 anchor",
                "",
                f"- Split: `{dataset['split']}`",
                f"- Corpus: {dataset['corpus_documents']} whole documents",
                f"- Queries: {dataset['evaluated_queries']}",
                f"- Full official split: `{str(dataset['full_official_split']).lower()}`",
                "",
                "## Metrics",
                "",
                "| Metric | Score |",
                "|---|---:|",
                *(f"| {name} | {value:.4f} |" for name, value in metrics.items()),
                "",
                "## External anchor",
                "",
                f"- System: {reference['system']}",
                f"- Published nDCG@10: {reference['ndcg_at_10']:.4f}",
                f"- Absolute difference: {reference['absolute_difference']:+.4f}",
                f"- Reproduction page: {reference['url']}",
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
        "--cache-dir",
        type=Path,
        default=Path(os.getenv("PUBLIC_RETRIEVAL_CACHE_DIR", DEFAULT_CACHE_DIR)),
    )
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--k1", type=float, default=DEFAULT_K1)
    parser.add_argument("--b", type=float, default=DEFAULT_B)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.k1 <= 0 or not 0 <= args.b <= 1:
        raise SystemExit("BM25 requires k1 > 0 and 0 <= b <= 1")
    benchmark = load_beir_dataset(
        args.dataset,
        split=args.split,
        cache_dir=args.cache_dir,
        allow_download=not args.no_download,
    )
    report = run_bm25(benchmark, k1=args.k1, b=args.b)
    output = args.output or (
        DEFAULT_REPORT_DIR / args.dataset / f"bm25-{args.split}-retrieval.json"
    )
    write_report(report, output)
    print(json.dumps(report["metrics"], indent=2))


if __name__ == "__main__":
    main()
