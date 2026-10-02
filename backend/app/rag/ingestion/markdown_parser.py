"""Bounded UTF-8 Markdown extraction with heading metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MARKDOWN_PARSER_VERSION = "markdown-structure-v2"


class MarkdownExtractionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MarkdownSection:
    section_number: int
    title: str | None
    heading_level: int
    section_path: tuple[str, ...]
    content_types: tuple[str, ...]
    text: str


@dataclass(frozen=True, slots=True)
class ExtractedMarkdown:
    byte_size: int
    parser_version: str
    sections: tuple[MarkdownSection, ...]


class MarkdownParser:
    def __init__(self, *, max_bytes: int = 1024 * 1024) -> None:
        if max_bytes <= 0:
            raise ValueError("Markdown size limit must be positive")
        self._max_bytes = max_bytes

    def parse(self, path: Path) -> ExtractedMarkdown:
        content = path.read_bytes()
        if not content:
            raise MarkdownExtractionError("Markdown document is empty")
        if len(content) > self._max_bytes:
            raise MarkdownExtractionError("Markdown document exceeds the text size limit")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise MarkdownExtractionError("Markdown document is not valid UTF-8") from error
        sections = self._sections(text)
        if not sections:
            raise MarkdownExtractionError("Markdown document contains no text")
        return ExtractedMarkdown(
            byte_size=len(content),
            parser_version=MARKDOWN_PARSER_VERSION,
            sections=tuple(sections),
        )

    @staticmethod
    def _sections(text: str) -> list[MarkdownSection]:
        sections: list[MarkdownSection] = []
        lines: list[str] = []
        title: str | None = None
        heading_level = 0
        heading_stack: list[str] = []

        def content_types(value: str) -> tuple[str, ...]:
            detected: list[str] = []
            if re.search(r"^```", value, re.MULTILINE):
                detected.append("code")
            if re.search(r"^\s*(?:[-*+] |\d+[.)] )", value, re.MULTILINE):
                detected.append("list")
            if re.search(r"^\s*\|.+\|\s*$", value, re.MULTILINE):
                detected.append("table")
            if re.search(
                r"^\s*>\s*(?:\[!(?:NOTE|WARNING|CAUTION)\]|(?:note|warning):)",
                value,
                re.MULTILINE | re.IGNORECASE,
            ):
                detected.append("admonition")
            if not detected or re.search(
                r"^(?!\s*(?:#|```|[-*+] |\d+[.)] |\||>)).+", value, re.MULTILINE
            ):
                detected.append("paragraph")
            return tuple(detected)

        def flush() -> None:
            value = "\n".join(lines).strip()
            if value:
                sections.append(
                    MarkdownSection(
                        section_number=len(sections) + 1,
                        title=title,
                        heading_level=heading_level,
                        section_path=tuple(heading_stack),
                        content_types=content_types(value),
                        text=value,
                    )
                )

        for line in text.splitlines():
            heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if heading:
                flush()
                heading_level = len(heading.group(1))
                title = heading.group(2)
                heading_stack[heading_level - 1 :] = [title]
                lines = [line]
            else:
                lines.append(line)
        flush()
        return sections
