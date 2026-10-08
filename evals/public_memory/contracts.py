"""Provider-neutral contracts for conversational-memory retrieval benchmarks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class MemoryBenchmarkManifest:
    dataset_id: str
    display_name: str
    source_url: str
    homepage_url: str
    checksum_algorithm: str
    checksum: str
    license_note: str
    citation_url: str
    benchmark_scope: str
    paper_comparable: bool

    def __post_init__(self) -> None:
        if not self.dataset_id or not self.source_url or not self.checksum:
            raise ValueError("Memory benchmark manifest identifiers cannot be empty")
        if self.checksum_algorithm not in {"md5", "sha256"}:
            raise ValueError("Memory benchmark checksum must use md5 or sha256")


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    record_id: str
    text: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.record_id.strip() or not self.text.strip():
            raise ValueError("Memory record ID and text cannot be empty")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MemoryRetrievalQuery:
    query_id: str
    text: str
    answer: str
    category: str
    candidate_ids: tuple[str, ...]
    relevant_ids: tuple[str, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.query_id.strip() or not self.text.strip():
            raise ValueError("Memory query ID and text cannot be empty")
        if not self.candidate_ids or not self.relevant_ids:
            raise ValueError(f"Memory query {self.query_id!r} has no candidates or gold evidence")
        if not set(self.relevant_ids).issubset(self.candidate_ids):
            raise ValueError(f"Gold evidence is outside candidate set for {self.query_id!r}")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MemoryRetrievalBenchmark:
    manifest: MemoryBenchmarkManifest
    records: tuple[MemoryRecord, ...]
    queries: tuple[MemoryRetrievalQuery, ...]
    official_query_count: int
    excluded_query_count: int = 0
    derivation: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        record_ids = [record.record_id for record in self.records]
        query_ids = [query.query_id for query in self.queries]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("Memory record IDs must be unique")
        if len(query_ids) != len(set(query_ids)):
            raise ValueError("Memory query IDs must be unique")
        known_records = set(record_ids)
        for query in self.queries:
            unknown = set(query.candidate_ids) - known_records
            if unknown:
                raise ValueError(
                    f"Memory query {query.query_id!r} references unknown record {min(unknown)!r}"
                )
        if self.official_query_count < len(self.queries):
            raise ValueError("Official query count cannot be smaller than loaded queries")
        object.__setattr__(self, "derivation", MappingProxyType(dict(self.derivation)))
