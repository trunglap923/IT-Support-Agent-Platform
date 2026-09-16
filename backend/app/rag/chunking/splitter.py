"""Deterministic token-window chunking with source metadata."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from uuid import UUID, uuid5

CHUNK_NAMESPACE = UUID("95dce5a9-6821-52dc-b74d-c655b842ef57")
CHUNKER_VERSION = "word-window-v1"
TOKEN_PATTERN = re.compile(r"\S+")


@dataclass(frozen=True, slots=True)
class SourceBlock:
    text: str
    page_number: int | None
    section: str | None
    source_path: str


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    id: UUID
    ordinal: int
    content: str
    content_hash: str
    token_count: int
    page_number: int | None
    section: str | None
    source_path: str
    source_token_start: int
    source_token_end: int
    chunker_version: str


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    target_tokens: int = 500
    overlap_tokens: int = 60
    hard_cap_tokens: int = 800
    version: str = CHUNKER_VERSION

    def __post_init__(self) -> None:
        if self.target_tokens <= 0 or self.hard_cap_tokens <= 0:
            raise ValueError("Chunk token limits must be positive")
        if self.target_tokens > self.hard_cap_tokens:
            raise ValueError("Chunk target cannot exceed the hard cap")
        if self.overlap_tokens < 0 or self.overlap_tokens >= self.target_tokens:
            raise ValueError("Chunk overlap must be between zero and target_tokens - 1")


def normalize_text(value: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.splitlines()]
    normalized: list[str] = []
    previous_blank = False
    for line in lines:
        is_blank = not line
        if is_blank and previous_blank:
            continue
        normalized.append(line)
        previous_blank = is_blank
    return "\n".join(normalized).strip()


def chunk_blocks(
    *,
    version_id: UUID,
    blocks: list[SourceBlock],
    config: ChunkingConfig | None = None,
) -> list[ChunkDraft]:
    selected = config or ChunkingConfig()
    chunks: list[ChunkDraft] = []
    ordinal = 0
    step = selected.target_tokens - selected.overlap_tokens

    for block_index, block in enumerate(blocks):
        normalized = normalize_text(block.text)
        tokens = TOKEN_PATTERN.findall(normalized)
        for start in range(0, len(tokens), step):
            window = tokens[start : start + selected.target_tokens]
            if not window:
                break
            content = " ".join(window)
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            identity = ":".join(
                [
                    str(version_id),
                    selected.version,
                    str(block_index),
                    str(start),
                    str(block.page_number),
                    block.section or "",
                    block.source_path,
                    content_hash,
                ]
            )
            chunks.append(
                ChunkDraft(
                    id=uuid5(CHUNK_NAMESPACE, identity),
                    ordinal=ordinal,
                    content=content,
                    content_hash=content_hash,
                    token_count=len(window),
                    page_number=block.page_number,
                    section=block.section,
                    source_path=block.source_path,
                    source_token_start=start,
                    source_token_end=start + len(window),
                    chunker_version=selected.version,
                )
            )
            ordinal += 1
            if start + selected.target_tokens >= len(tokens):
                break

    if any(chunk.token_count > selected.hard_cap_tokens for chunk in chunks):
        raise AssertionError("Chunker emitted a chunk above its hard cap")
    return chunks
