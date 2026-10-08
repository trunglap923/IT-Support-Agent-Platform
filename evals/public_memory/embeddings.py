"""Cached production embeddings for public memory retrieval benchmarks."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.providers.embeddings import EmbeddingProvider

from evals.public_memory.contracts import (
    MemoryRetrievalBenchmark,
    MemoryRetrievalQuery,
)

EMBEDDING_BATCH_SIZE = 96


@dataclass(frozen=True, slots=True)
class BenchmarkEmbeddings:
    model: str
    dimensions: int
    record_vectors: dict[str, tuple[float, ...]]
    query_vectors: dict[str, tuple[float, ...]]
    cache_hits: int
    api_inputs: int
    input_tokens: int


class _EmbeddingCache:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_embeddings (
                model TEXT NOT NULL,
                dimensions INTEGER NOT NULL,
                text_hash TEXT NOT NULL,
                vector_json TEXT NOT NULL,
                PRIMARY KEY (model, dimensions, text_hash)
            )
            """
        )
        self._connection.commit()

    def load(
        self,
        *,
        model: str,
        dimensions: int,
        text_hashes: set[str],
    ) -> dict[str, tuple[float, ...]]:
        rows = self._connection.execute(
            """
            SELECT text_hash, vector_json
            FROM memory_embeddings
            WHERE model = ? AND dimensions = ?
            """,
            (model, dimensions),
        )
        values: dict[str, tuple[float, ...]] = {}
        for text_hash, raw_vector in rows:
            if text_hash not in text_hashes:
                continue
            decoded = json.loads(raw_vector)
            if not isinstance(decoded, list) or len(decoded) != dimensions:
                continue
            values[text_hash] = tuple(float(item) for item in decoded)
        return values

    def store(
        self,
        *,
        model: str,
        dimensions: int,
        values: Sequence[tuple[str, tuple[float, ...]]],
    ) -> None:
        self._connection.executemany(
            """
            INSERT INTO memory_embeddings(model, dimensions, text_hash, vector_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(model, dimensions, text_hash)
            DO UPDATE SET vector_json = excluded.vector_json
            """,
            (
                (
                    model,
                    dimensions,
                    text_hash,
                    json.dumps(vector, separators=(",", ":")),
                )
                for text_hash, vector in values
            ),
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def prepare_benchmark_embeddings(
    benchmark: MemoryRetrievalBenchmark,
    *,
    queries: Sequence[MemoryRetrievalQuery],
    provider: EmbeddingProvider,
    model: str,
    dimensions: int,
    cache_path: Path,
) -> BenchmarkEmbeddings:
    """Embed unique records and selected queries, resuming from a local SQLite cache."""

    texts = tuple(
        dict.fromkeys(
            [record.text for record in benchmark.records]
            + [query.text for query in queries]
        )
    )
    texts_by_hash = {_text_hash(text): text for text in texts}
    cache = _EmbeddingCache(cache_path)
    run_id = uuid4()
    api_inputs = 0
    input_tokens = 0
    try:
        vectors = cache.load(
            model=model,
            dimensions=dimensions,
            text_hashes=set(texts_by_hash),
        )
        cache_hits = len(vectors)
        missing = [
            (text_hash, text)
            for text_hash, text in texts_by_hash.items()
            if text_hash not in vectors
        ]
        for batch_number, start in enumerate(
            range(0, len(missing), EMBEDDING_BATCH_SIZE)
        ):
            group = missing[start : start + EMBEDDING_BATCH_SIZE]
            result = await provider.embed(
                [text for _, text in group],
                operation_id=(
                    f"public-memory:{benchmark.manifest.dataset_id}:"
                    f"{run_id}:batch:{batch_number}"
                ),
            )
            if result.model != model or result.dimensions != dimensions:
                raise RuntimeError(
                    "Embedding provider returned a different model or dimension than requested"
                )
            stored = list(
                zip(
                    (text_hash for text_hash, _ in group),
                    result.vectors,
                    strict=True,
                )
            )
            cache.store(model=model, dimensions=dimensions, values=stored)
            vectors.update(stored)
            api_inputs += len(group)
            input_tokens += result.input_tokens
    finally:
        cache.close()

    return BenchmarkEmbeddings(
        model=model,
        dimensions=dimensions,
        record_vectors={
            record.record_id: vectors[_text_hash(record.text)]
            for record in benchmark.records
        },
        query_vectors={
            query.text: vectors[_text_hash(query.text)] for query in queries
        },
        cache_hits=cache_hits,
        api_inputs=api_inputs,
        input_tokens=input_tokens,
    )
