import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from app.rag.ingestion.pdf_parser import PdfErrorCode, PdfExtractionError, PdfParser
from tests.unit.pdf_factory import build_text_pdf


def write_fixture(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


def test_extracts_text_and_physical_page_numbers(tmp_path: Path) -> None:
    path = write_fixture(
        tmp_path / "self-authored.pdf",
        build_text_pdf("VPN setup page", "Registry setup page"),
    )

    result = PdfParser().parse(path)

    assert [page.page_number for page in result.pages] == [1, 2]
    assert [page.text for page in result.pages] == ["VPN setup page", "Registry setup page"]
    assert result.parser_version == "pypdf-subprocess-v2"


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"not a pdf", PdfErrorCode.INVALID_SIGNATURE),
        (b"%PDF-broken", PdfErrorCode.MALFORMED),
    ],
)
def test_reports_stable_errors(tmp_path: Path, content: bytes, code: PdfErrorCode) -> None:
    path = write_fixture(tmp_path / "invalid.pdf", content)

    with pytest.raises(PdfExtractionError) as raised:
        PdfParser().parse(path)

    assert raised.value.code is code


def test_rejects_oversize_before_parsing(tmp_path: Path) -> None:
    path = write_fixture(tmp_path / "large.pdf", b"%PDF-" + b"x" * 20)

    with pytest.raises(PdfExtractionError) as raised:
        PdfParser(max_bytes=10).parse(path)

    assert raised.value.code is PdfErrorCode.TOO_LARGE


def test_rejects_pages_without_extractable_text(tmp_path: Path) -> None:
    path = write_fixture(tmp_path / "blank.pdf", build_text_pdf(""))

    with pytest.raises(PdfExtractionError) as raised:
        PdfParser().parse(path)

    assert raised.value.code is PdfErrorCode.NO_TEXT


def test_reports_timeout_with_a_stable_error_code(tmp_path: Path) -> None:
    path = write_fixture(tmp_path / "slow.pdf", build_text_pdf("slow"))

    with (
        patch(
            "app.rag.ingestion.pdf_parser.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["pdf-worker"], timeout=0.01),
        ),
        pytest.raises(PdfExtractionError) as raised,
    ):
        PdfParser(timeout_seconds=0.01).parse(path)

    assert raised.value.code is PdfErrorCode.TIMEOUT
