from __future__ import annotations

from pathlib import Path

import pytest
from evals.public.contracts import (
    PublicBenchmark,
    PublicBenchmarkManifest,
    PublicDocument,
    PublicQuery,
)


def manifest() -> PublicBenchmarkManifest:
    return PublicBenchmarkManifest(
        dataset_id="fixture",
        display_name="Fixture",
        source_url="https://example.com/fixture.zip",
        homepage_url="https://example.com",
        checksum_algorithm="md5",
        checksum="0" * 32,
        license_note="fixture only",
        citation_url="https://example.com/paper",
        supported_splits=("test",),
    )


def test_public_benchmark_freezes_and_validates_qrels() -> None:
    benchmark = PublicBenchmark(
        manifest=manifest(),
        split="test",
        documents=(PublicDocument("d1", "Title", "Body"),),
        queries=(PublicQuery("q1", "question"),),
        qrels={"q1": {"d1": 2}},
    )

    assert benchmark.documents[0].retrieval_text == "Title\n\nBody"
    assert benchmark.qrels["q1"]["d1"] == 2
    with pytest.raises(TypeError):
        benchmark.qrels["q1"]["d1"] = 1  # type: ignore[index]


def test_public_benchmark_rejects_unknown_qrel_document() -> None:
    with pytest.raises(ValueError, match="unknown document"):
        PublicBenchmark(
            manifest=manifest(),
            split="test",
            documents=(PublicDocument("d1", "", "Body"),),
            queries=(PublicQuery("q1", "question"),),
            qrels={"q1": {"missing": 1}},
        )


def test_manifest_rejects_unknown_checksum_algorithm() -> None:
    values = manifest()
    with pytest.raises(ValueError, match="md5 or sha256"):
        PublicBenchmarkManifest(
            dataset_id=values.dataset_id,
            display_name=values.display_name,
            source_url=values.source_url,
            homepage_url=values.homepage_url,
            checksum_algorithm="crc32",
            checksum=values.checksum,
            license_note=values.license_note,
            citation_url=values.citation_url,
            supported_splits=values.supported_splits,
        )


def test_public_cache_path_is_not_part_of_document_contract(tmp_path: Path) -> None:
    document = PublicDocument("d1", "", "Body", {"cache": str(tmp_path)})
    assert document.metadata["cache"] == str(tmp_path)
