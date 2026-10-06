"""Validated, provider-neutral contract for public information-retrieval datasets."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class PublicBenchmarkManifest:
    dataset_id: str
    display_name: str
    source_url: str
    homepage_url: str
    checksum_algorithm: str
    checksum: str
    license_note: str
    citation_url: str
    supported_splits: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.dataset_id or not self.source_url or not self.checksum:
            raise ValueError("Public benchmark manifest identifiers cannot be empty")
        if self.checksum_algorithm not in {"md5", "sha256"}:
            raise ValueError("Public benchmark checksum must use md5 or sha256")
        if not self.supported_splits:
            raise ValueError("Public benchmark must declare at least one split")


@dataclass(frozen=True, slots=True)
class PublicDocument:
    document_id: str
    title: str
    text: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.document_id.strip():
            raise ValueError("Public document ID cannot be empty")
        if not self.text.strip() and not self.title.strip():
            raise ValueError(f"Public document {self.document_id!r} has no content")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def retrieval_text(self) -> str:
        return "\n\n".join(
            part.strip() for part in (self.title, self.text) if part.strip()
        )


@dataclass(frozen=True, slots=True)
class PublicQuery:
    query_id: str
    text: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.query_id.strip() or not self.text.strip():
            raise ValueError("Public query ID and text cannot be empty")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PublicBenchmark:
    manifest: PublicBenchmarkManifest
    split: str
    documents: tuple[PublicDocument, ...]
    queries: tuple[PublicQuery, ...]
    qrels: Mapping[str, Mapping[str, int]]

    def __post_init__(self) -> None:
        if self.split not in self.manifest.supported_splits:
            raise ValueError(
                f"Split {self.split!r} is not supported by {self.manifest.dataset_id}"
            )
        document_ids = [item.document_id for item in self.documents]
        query_ids = [item.query_id for item in self.queries]
        if len(document_ids) != len(set(document_ids)):
            raise ValueError("Public benchmark document IDs must be unique")
        if len(query_ids) != len(set(query_ids)):
            raise ValueError("Public benchmark query IDs must be unique")

        known_documents = set(document_ids)
        known_queries = set(query_ids)
        frozen_qrels: dict[str, Mapping[str, int]] = {}
        for query_id, judgments in self.qrels.items():
            if query_id not in known_queries:
                raise ValueError(f"Qrels references unknown query {query_id!r}")
            unknown_documents = set(judgments) - known_documents
            if unknown_documents:
                unknown = min(unknown_documents)
                raise ValueError(f"Qrels references unknown document {unknown!r}")
            normalized = {
                document_id: int(score) for document_id, score in judgments.items()
            }
            if any(score < 0 for score in normalized.values()):
                raise ValueError("Qrels relevance scores cannot be negative")
            frozen_qrels[query_id] = MappingProxyType(normalized)
        missing_qrels = known_queries - set(frozen_qrels)
        if missing_qrels:
            missing = min(missing_qrels)
            raise ValueError(f"Public query {missing!r} has no relevance judgments")
        object.__setattr__(self, "qrels", MappingProxyType(frozen_qrels))
