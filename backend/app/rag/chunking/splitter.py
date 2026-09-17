"""Deterministic token-window chunking with source metadata."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from uuid import UUID, uuid5

CHUNK_NAMESPACE = UUID("95dce5a9-6821-52dc-b74d-c655b842ef57")
CHUNKER_VERSION = "semantic-window-v2"
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


@dataclass(frozen=True, slots=True)
class _SemanticUnit:
    text: str
    start: int
    end: int
    protected: bool = False


def normalize_text(value: str) -> str:
    lines: list[str] = []
    fenced = False
    for raw_line in value.splitlines():
        if raw_line.strip().startswith("```"):
            fenced = not fenced
            lines.append(raw_line.strip())
        elif fenced:
            lines.append(raw_line.rstrip())
        else:
            lines.append(re.sub(r"[ \t]+", " ", raw_line).strip())
    normalized: list[str] = []
    previous_blank = False
    for line in lines:
        is_blank = not line
        if is_blank and previous_blank:
            continue
        normalized.append(line)
        previous_blank = is_blank
    return "\n".join(normalized).strip()


def _semantic_units(value: str, *, hard_cap: int) -> list[_SemanticUnit]:
    raw_units: list[tuple[str, bool]] = []
    paragraph: list[str] = []
    code: list[str] = []
    fenced = False

    def flush_paragraph() -> None:
        if paragraph:
            raw_units.append(("\n".join(paragraph), False))
            paragraph.clear()

    for line in value.splitlines():
        if line.startswith("```"):
            if not fenced:
                flush_paragraph()
                code = [line]
                fenced = True
            else:
                code.append(line)
                raw_units.append(("\n".join(code), True))
                code = []
                fenced = False
            continue
        if fenced:
            code.append(line)
        elif not line:
            flush_paragraph()
        elif line.startswith("#"):
            flush_paragraph()
            raw_units.append((line, False))
        else:
            paragraph.append(line)
    if code:
        raw_units.append(("\n".join(code), True))
    flush_paragraph()

    merged: list[tuple[str, bool]] = []
    for text, protected in raw_units:
        if protected and merged and not merged[-1][0].startswith("#"):
            combined = f"{merged[-1][0]}\n\n{text}"
            if len(TOKEN_PATTERN.findall(combined)) <= hard_cap:
                merged[-1] = (combined, True)
                continue
        merged.append((text, protected))

    units: list[_SemanticUnit] = []
    cursor = 0
    for text, protected in merged:
        token_count = len(TOKEN_PATTERN.findall(text))
        if token_count:
            units.append(
                _SemanticUnit(
                    text=text,
                    start=cursor,
                    end=cursor + token_count,
                    protected=protected,
                )
            )
            cursor += token_count
    return units


def _flush_packed_units(
    packed: list[_SemanticUnit],
    candidates: list[tuple[str, int, int]],
) -> None:
    if not packed:
        return
    candidates.append(("\n\n".join(unit.text for unit in packed), packed[0].start, packed[-1].end))
    packed.clear()


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
        units = _semantic_units(normalized, hard_cap=selected.hard_cap_tokens)
        candidates: list[tuple[str, int, int]] = []
        packed: list[_SemanticUnit] = []

        for unit in units:
            unit_tokens = TOKEN_PATTERN.findall(unit.text)
            if len(unit_tokens) > selected.target_tokens and not (
                unit.protected and len(unit_tokens) <= selected.hard_cap_tokens
            ):
                _flush_packed_units(packed, candidates)
                for offset in range(0, len(unit_tokens), step):
                    window = unit_tokens[offset : offset + selected.target_tokens]
                    if not window:
                        break
                    candidates.append(
                        (" ".join(window), unit.start + offset, unit.start + offset + len(window))
                    )
                    if offset + selected.target_tokens >= len(unit_tokens):
                        break
                continue
            packed_tokens = sum(item.end - item.start for item in packed)
            limit = selected.hard_cap_tokens if unit.protected else selected.target_tokens
            if packed and packed_tokens + len(unit_tokens) > limit:
                _flush_packed_units(packed, candidates)
            packed.append(unit)
        _flush_packed_units(packed, candidates)

        for content, start, end in candidates:
            token_count = len(TOKEN_PATTERN.findall(content))
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
                    token_count=token_count,
                    page_number=block.page_number,
                    section=block.section,
                    source_path=block.source_path,
                    source_token_start=start,
                    source_token_end=end,
                    chunker_version=selected.version,
                )
            )
            ordinal += 1

    if any(chunk.token_count > selected.hard_cap_tokens for chunk in chunks):
        raise AssertionError("Chunker emitted a chunk above its hard cap")
    return chunks
