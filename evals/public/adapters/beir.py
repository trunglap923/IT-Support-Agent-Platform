"""Checksum-verified loader for datasets distributed by the official BEIR project."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from evals.public.contracts import (
    PublicBenchmark,
    PublicBenchmarkManifest,
    PublicDocument,
    PublicQuery,
)

BEIR_DATASETS: dict[str, PublicBenchmarkManifest] = {
    "scifact": PublicBenchmarkManifest(
        dataset_id="scifact",
        display_name="BEIR SciFact",
        source_url=(
            "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/"
            "datasets/scifact.zip"
        ),
        homepage_url="https://github.com/allenai/scifact",
        checksum_algorithm="md5",
        checksum="5f7d1de60b170fc8027bb7898e2efca1",
        license_note=(
            "BEIR redistributes the public dataset but requires users to verify and comply "
            "with the original dataset license. Dataset files are cached locally and are not "
            "committed to this repository."
        ),
        citation_url="https://openreview.net/forum?id=wCu6T5xFjeJ",
        supported_splits=("train", "test"),
    )
}


def _file_checksum(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download(manifest: PublicBenchmarkManifest, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(f"{destination.suffix}.part")
    try:
        with (
            urllib.request.urlopen(manifest.source_url, timeout=120) as response,
            temporary.open("wb") as target,
        ):
            shutil.copyfileobj(response, target)
        actual = _file_checksum(temporary, manifest.checksum_algorithm)
        if actual != manifest.checksum:
            raise ValueError(
                f"Checksum mismatch for {manifest.dataset_id}: expected "
                f"{manifest.checksum}, received {actual}"
            )
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def _safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (destination / member.filename).resolve()
            if target != root and root not in target.parents:
                raise ValueError(
                    f"Unsafe path in benchmark archive: {member.filename!r}"
                )
        bundle.extractall(destination)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TypeError(f"{path}:{line_number} must contain a JSON object")
            rows.append(value)
    return rows


def _locate_dataset_root(extracted_root: Path, dataset_id: str) -> Path:
    candidates = (extracted_root / dataset_id, extracted_root)
    for candidate in candidates:
        if (candidate / "corpus.jsonl").is_file() and (
            candidate / "queries.jsonl"
        ).is_file():
            return candidate
    raise FileNotFoundError(f"Could not locate extracted BEIR dataset {dataset_id!r}")


def load_beir_dataset(
    dataset_id: str,
    *,
    split: str,
    cache_dir: Path,
    allow_download: bool = True,
) -> PublicBenchmark:
    """Load a BEIR dataset without importing the optional BEIR Python package."""

    try:
        manifest = BEIR_DATASETS[dataset_id]
    except KeyError as error:
        raise ValueError(f"Unsupported BEIR dataset: {dataset_id!r}") from error
    if split not in manifest.supported_splits:
        raise ValueError(f"Unsupported {dataset_id} split: {split!r}")

    dataset_cache = cache_dir / "beir" / dataset_id
    archive = dataset_cache / f"{dataset_id}.zip"
    extracted_root = dataset_cache / "extracted"
    if archive.exists():
        actual = _file_checksum(archive, manifest.checksum_algorithm)
        if actual != manifest.checksum:
            archive.unlink()
            shutil.rmtree(extracted_root, ignore_errors=True)
    if not archive.exists():
        if not allow_download:
            raise FileNotFoundError(
                f"Benchmark archive is not cached at {archive}; enable downloads first"
            )
        _download(manifest, archive)
    if not extracted_root.exists():
        _safe_extract(archive, extracted_root)

    root = _locate_dataset_root(extracted_root, dataset_id)
    documents = tuple(
        PublicDocument(
            document_id=str(row["_id"]),
            title=str(row.get("title", "")),
            text=str(row.get("text", "")),
            metadata=row.get("metadata", {}),
        )
        for row in _load_jsonl(root / "corpus.jsonl")
    )
    all_queries = {
        str(row["_id"]): PublicQuery(
            query_id=str(row["_id"]),
            text=str(row["text"]),
            metadata=row.get("metadata", {}),
        )
        for row in _load_jsonl(root / "queries.jsonl")
    }
    qrels_path = root / "qrels" / f"{split}.tsv"
    qrels: dict[str, dict[str, int]] = {}
    with qrels_path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        required = {"query-id", "corpus-id", "score"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"Unexpected BEIR qrels header in {qrels_path}")
        for row in reader:
            qrels.setdefault(row["query-id"], {})[row["corpus-id"]] = int(row["score"])
    queries = tuple(all_queries[query_id] for query_id in qrels)
    return PublicBenchmark(
        manifest=manifest,
        split=split,
        documents=documents,
        queries=queries,
        qrels=qrels,
    )
