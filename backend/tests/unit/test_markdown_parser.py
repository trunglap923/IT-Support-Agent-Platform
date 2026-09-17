from pathlib import Path

import pytest

from app.rag.ingestion.markdown_parser import MarkdownExtractionError, MarkdownParser


def test_markdown_parser_preserves_heading_sections(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    path.write_text(
        "Intro text.\n\n# VPN guide\nSetup steps.\n\n## Verification\nCheck status.",
        encoding="utf-8",
    )

    extracted = MarkdownParser(max_bytes=1024).parse(path)

    assert extracted.parser_version == "markdown-sections-v1"
    assert [section.title for section in extracted.sections] == [
        None,
        "VPN guide",
        "Verification",
    ]
    assert [section.section_number for section in extracted.sections] == [1, 2, 3]
    assert "Setup steps" in extracted.sections[1].text


def test_markdown_parser_rejects_empty_invalid_and_oversized_files(tmp_path: Path) -> None:
    empty = tmp_path / "empty.md"
    empty.write_bytes(b"")
    invalid = tmp_path / "invalid.md"
    invalid.write_bytes(b"\xff")
    large = tmp_path / "large.md"
    large.write_text("too large", encoding="utf-8")
    parser = MarkdownParser(max_bytes=4)

    with pytest.raises(MarkdownExtractionError, match="empty"):
        parser.parse(empty)
    with pytest.raises(MarkdownExtractionError, match="valid UTF-8"):
        MarkdownParser(max_bytes=10).parse(invalid)
    with pytest.raises(MarkdownExtractionError, match="size limit"):
        parser.parse(large)
