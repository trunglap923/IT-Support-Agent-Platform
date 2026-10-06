from __future__ import annotations

from evals.public.contracts import (
    PublicBenchmark,
    PublicBenchmarkManifest,
    PublicDocument,
    PublicQuery,
)
from evals.runner.public_bm25 import run_bm25


def test_bm25_anchor_ranks_matching_whole_document_first() -> None:
    manifest = PublicBenchmarkManifest(
        dataset_id="fixture",
        display_name="Fixture",
        source_url="https://example.com/fixture.zip",
        homepage_url="https://example.com",
        checksum_algorithm="md5",
        checksum="0" * 32,
        license_note="fixture",
        citation_url="https://example.com/paper",
        supported_splits=("test",),
    )
    benchmark = PublicBenchmark(
        manifest=manifest,
        split="test",
        documents=(
            PublicDocument("d1", "VPN certificate", "Renew the managed certificate."),
            PublicDocument("d2", "Printer", "Replace paper in the office printer."),
            PublicDocument("d3", "Email", "Reset an email password."),
        ),
        queries=(PublicQuery("q1", "managed VPN certificate renewal"),),
        qrels={"q1": {"d1": 1}},
    )

    report = run_bm25(benchmark)

    assert report["results"][0]["ranking"][0] == "d1"
    assert report["metrics"]["ndcg_at_10"] == 1.0
    assert report["system"]["document_granularity"] == "whole_document"
