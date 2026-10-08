"""Checksum-verified adapters for LoCoMo and LongMemEval."""

from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
import urllib.request
from pathlib import Path
from typing import Any

from evals.public_memory.contracts import (
    MemoryBenchmarkManifest,
    MemoryRecord,
    MemoryRetrievalBenchmark,
    MemoryRetrievalQuery,
)

LOCOMO = MemoryBenchmarkManifest(
    dataset_id="locomo",
    display_name="LoCoMo",
    source_url="https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json",
    homepage_url="https://github.com/snap-research/locomo",
    checksum_algorithm="sha256",
    checksum="79fa87e90f04081343b8c8debecb80a9a6842b76a7aa537dc9fdf651ea698ff4",
    license_note=(
        "The source repository publishes the dataset for research use. The downloaded file is "
        "cached locally and is not committed to this repository; verify upstream terms before "
        "redistribution."
    ),
    citation_url="https://aclanthology.org/2024.acl-long.747/",
    benchmark_scope="Session-level retrieval derived from official turn-level evidence labels.",
    paper_comparable=False,
)

LONGMEMEVAL_ORACLE_MIX = MemoryBenchmarkManifest(
    dataset_id="longmemeval-oracle-mix",
    display_name="LongMemEval Oracle Mix",
    source_url=(
        "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/"
        "longmemeval_oracle.json"
    ),
    homepage_url="https://github.com/xiaowu0162/LongMemEval",
    checksum_algorithm="sha256",
    checksum="821a2034d219ab45846873dd14c14f12cfe7776e73527a483f9dac095d38620c",
    license_note=(
        "LongMemEval is distributed under MIT. The downloaded dataset is cached locally and is "
        "not committed to this repository."
    ),
    citation_url="https://arxiv.org/abs/2410.10813",
    benchmark_scope=(
        "Derived smoke retrieval task: official oracle evidence sessions mixed with fixed-seed "
        "distractor sessions."
    ),
    paper_comparable=False,
)

MEMORY_DATASETS = {
    LOCOMO.dataset_id: LOCOMO,
    LONGMEMEVAL_ORACLE_MIX.dataset_id: LONGMEMEVAL_ORACLE_MIX,
}

_SESSION_KEY = re.compile(r"session_(\d+)$")
_EVIDENCE_ID = re.compile(r"D(\d+):\d+", re.IGNORECASE)


def _file_checksum(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download(manifest: MemoryBenchmarkManifest, destination: Path) -> None:
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
                f"Checksum mismatch for {manifest.dataset_id}: expected {manifest.checksum}, "
                f"received {actual}"
            )
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def _load_source(
    manifest: MemoryBenchmarkManifest,
    *,
    path: Path,
    allow_download: bool,
) -> list[dict[str, Any]]:
    if (
        path.exists()
        and _file_checksum(path, manifest.checksum_algorithm) != manifest.checksum
    ):
        raise ValueError(f"Cached benchmark checksum does not match manifest: {path}")
    if not path.exists():
        if not allow_download:
            raise FileNotFoundError(
                f"Benchmark is not cached at {path}; enable downloads first"
            )
        _download(manifest, path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise TypeError(f"Expected a JSON array of objects in {path}")
    return value


def _render_dialogue(turns: list[dict[str, Any]], *, date: str | None = None) -> str:
    lines = [f"Date: {date}"] if date else []
    for turn in turns:
        speaker = str(turn.get("speaker") or turn.get("role") or "unknown")
        text = str(turn.get("text") or turn.get("content") or "").strip()
        if text:
            lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def load_locomo(
    *, cache_dir: Path, allow_download: bool = True
) -> MemoryRetrievalBenchmark:
    path = cache_dir / "memory" / "locomo" / "locomo10.json"
    rows = _load_source(LOCOMO, path=path, allow_download=allow_download)
    records: list[MemoryRecord] = []
    queries: list[MemoryRetrievalQuery] = []
    excluded = 0
    for sample in rows:
        sample_id = str(sample["sample_id"])
        conversation = sample["conversation"]
        if not isinstance(conversation, dict):
            raise TypeError(f"LoCoMo conversation {sample_id!r} must be an object")
        session_ids: dict[int, str] = {}
        for key, turns in conversation.items():
            match = _SESSION_KEY.fullmatch(key)
            if match is None:
                continue
            if not isinstance(turns, list):
                raise TypeError(f"LoCoMo {sample_id}/{key} must be a list")
            number = int(match.group(1))
            record_id = f"{sample_id}:session_{number}"
            session_ids[number] = record_id
            date = conversation.get(f"session_{number}_date_time")
            records.append(
                MemoryRecord(
                    record_id=record_id,
                    text=_render_dialogue(turns, date=str(date) if date else None),
                    metadata={"sample_id": sample_id, "session": number, "date": date},
                )
            )
        candidates = tuple(session_ids[number] for number in sorted(session_ids))
        raw_questions = sample.get("qa", [])
        if not isinstance(raw_questions, list):
            raise TypeError(f"LoCoMo QA {sample_id!r} must be a list")
        for index, item in enumerate(raw_questions):
            if not isinstance(item, dict):
                raise TypeError(f"LoCoMo QA {sample_id}/{index} must be an object")
            evidence = tuple(str(value) for value in item.get("evidence", []))
            relevant_numbers = {
                int(match.group(1))
                for evidence_id in evidence
                for match in _EVIDENCE_ID.finditer(evidence_id)
            }
            relevant = tuple(
                session_ids[number]
                for number in sorted(relevant_numbers)
                if number in session_ids
            )
            if not relevant:
                excluded += 1
                continue
            answer = item.get("answer", item.get("adversarial_answer", ""))
            queries.append(
                MemoryRetrievalQuery(
                    query_id=f"{sample_id}:qa:{index}",
                    text=str(item["question"]),
                    answer=str(answer),
                    category=str(item.get("category", "unknown")),
                    candidate_ids=candidates,
                    relevant_ids=relevant,
                    metadata={"evidence_turn_ids": evidence, "sample_id": sample_id},
                )
            )
    return MemoryRetrievalBenchmark(
        manifest=LOCOMO,
        records=tuple(records),
        queries=tuple(queries),
        official_query_count=sum(len(sample.get("qa", [])) for sample in rows),
        excluded_query_count=excluded,
        derivation={
            "retrieval_unit": "conversation session",
            "gold_mapping": "Official evidence turn D<n>:<turn> maps to session_<n>",
        },
    )


def _stable_sample(
    values: list[str], *, count: int, seed: int, query_id: str
) -> tuple[str, ...]:
    digest = hashlib.sha256(f"{seed}:{query_id}".encode()).digest()
    generator = random.Random(int.from_bytes(digest[:8], "big"))
    return tuple(generator.sample(values, k=min(count, len(values))))


def load_longmemeval_oracle_mix(
    *,
    cache_dir: Path,
    distractor_count: int = 31,
    seed: int = 20261008,
    allow_download: bool = True,
) -> MemoryRetrievalBenchmark:
    if distractor_count < 1:
        raise ValueError("LongMemEval oracle mix requires at least one distractor")
    path = cache_dir / "memory" / "longmemeval" / "longmemeval_oracle.json"
    rows = _load_source(
        LONGMEMEVAL_ORACLE_MIX, path=path, allow_download=allow_download
    )
    records_by_id: dict[str, MemoryRecord] = {}
    row_session_ids: dict[str, tuple[str, ...]] = {}
    for row in rows:
        query_id = str(row["question_id"])
        session_ids = row["haystack_session_ids"]
        dates = row["haystack_dates"]
        sessions = row["haystack_sessions"]
        if not (
            isinstance(session_ids, list)
            and isinstance(dates, list)
            and isinstance(sessions, list)
        ):
            raise TypeError("LongMemEval session fields must be lists")
        if not (len(session_ids) == len(dates) == len(sessions)):
            raise ValueError(
                f"LongMemEval session fields differ for {row['question_id']!r}"
            )
        namespaced_ids: list[str] = []
        for session_id, date, turns in zip(session_ids, dates, sessions, strict=True):
            if not isinstance(turns, list):
                raise TypeError(f"LongMemEval session {session_id!r} must be a list")
            record_id = f"{query_id}:{session_id}"
            record = MemoryRecord(
                record_id=record_id,
                text=_render_dialogue(turns, date=str(date)),
                metadata={
                    "date": str(date),
                    "official_session_id": str(session_id),
                    "source_query_id": query_id,
                },
            )
            records_by_id[record.record_id] = record
            namespaced_ids.append(record_id)
        row_session_ids[query_id] = tuple(namespaced_ids)

    all_record_ids = sorted(records_by_id)
    queries: list[MemoryRetrievalQuery] = []
    excluded = 0
    for row in rows:
        query_id = str(row["question_id"])
        if query_id.endswith("_abs"):
            excluded += 1
            continue
        official_gold = {str(value) for value in row["answer_session_ids"]}
        relevant = tuple(
            record_id
            for record_id in row_session_ids[query_id]
            if records_by_id[record_id].metadata["official_session_id"] in official_gold
        )
        distractor_pool = [
            record_id for record_id in all_record_ids if record_id not in relevant
        ]
        distractors = _stable_sample(
            distractor_pool,
            count=distractor_count,
            seed=seed,
            query_id=query_id,
        )
        queries.append(
            MemoryRetrievalQuery(
                query_id=query_id,
                text=str(row["question"]),
                answer=str(row["answer"]),
                category=str(row["question_type"]),
                candidate_ids=tuple(sorted((*relevant, *distractors))),
                relevant_ids=relevant,
                metadata={"question_date": str(row["question_date"])},
            )
        )
    return MemoryRetrievalBenchmark(
        manifest=LONGMEMEVAL_ORACLE_MIX,
        records=tuple(records_by_id[record_id] for record_id in all_record_ids),
        queries=tuple(queries),
        official_query_count=len(rows),
        excluded_query_count=excluded,
        derivation={
            "retrieval_unit": "conversation session",
            "gold_mapping": "Official answer_session_ids",
            "distractor_count": distractor_count,
            "distractor_seed": seed,
            "excluded": "Official abstention questions (*_abs) are excluded from retrieval",
            "warning": "Derived candidate pool; do not compare this score with the paper.",
        },
    )


def load_memory_benchmark(
    dataset_id: str,
    *,
    cache_dir: Path,
    distractor_count: int = 31,
    seed: int = 20261008,
    allow_download: bool = True,
) -> MemoryRetrievalBenchmark:
    if dataset_id == LOCOMO.dataset_id:
        return load_locomo(cache_dir=cache_dir, allow_download=allow_download)
    if dataset_id == LONGMEMEVAL_ORACLE_MIX.dataset_id:
        return load_longmemeval_oracle_mix(
            cache_dir=cache_dir,
            distractor_count=distractor_count,
            seed=seed,
            allow_download=allow_download,
        )
    raise ValueError(f"Unsupported memory benchmark: {dataset_id!r}")
