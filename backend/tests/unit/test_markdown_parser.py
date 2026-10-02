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

    assert extracted.parser_version == "markdown-structure-v2"
    assert [section.title for section in extracted.sections] == [
        None,
        "VPN guide",
        "Verification",
    ]
    assert [section.section_number for section in extracted.sections] == [1, 2, 3]
    assert [section.heading_level for section in extracted.sections] == [0, 1, 2]
    assert [section.section_path for section in extracted.sections] == [
        (),
        ("VPN guide",),
        ("VPN guide", "Verification"),
    ]
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


def test_markdown_parser_preserves_structural_content_types(tmp_path: Path) -> None:
    path = tmp_path / "structured.md"
    path.write_text(
        """# Recovery

> [!WARNING] Restart requires approval.

- Check service status
- Record the ticket

| State | Action |
|---|---|
| down | escalate |

```bash
systemctl status vpn
```
""",
        encoding="utf-8",
    )

    section = MarkdownParser().parse(path).sections[0]

    assert section.section_path == ("Recovery",)
    assert set(section.content_types) == {"admonition", "list", "table", "code", "paragraph"}
