"""Bounded PDF text extraction with stable, non-sensitive error codes."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

PARSER_VERSION = "pypdf-subprocess-v2"


class PdfErrorCode(StrEnum):
    NOT_FOUND = "pdf_not_found"
    TOO_LARGE = "pdf_too_large"
    INVALID_SIGNATURE = "pdf_invalid_signature"
    MALFORMED = "pdf_malformed"
    ENCRYPTED = "pdf_encrypted"
    TOO_MANY_PAGES = "pdf_too_many_pages"
    TEXT_TOO_LARGE = "pdf_text_too_large"
    NO_TEXT = "pdf_no_text"
    TIMEOUT = "pdf_parse_timeout"
    RESOURCE_LIMIT = "pdf_resource_limit"
    WORKER_FAILED = "pdf_worker_failed"


class PdfExtractionError(ValueError):
    def __init__(self, code: PdfErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class ExtractedPdf:
    pages: tuple[ExtractedPage, ...]
    parser_version: str
    byte_size: int

    @property
    def text(self) -> str:
        return "\n\n".join(page.text for page in self.pages)


class PdfParser:
    def __init__(
        self,
        *,
        max_bytes: int = 10 * 1024 * 1024,
        max_pages: int = 100,
        max_text_bytes: int = 1024 * 1024,
        timeout_seconds: float = 10.0,
        memory_limit_bytes: int = 512 * 1024 * 1024,
    ) -> None:
        if min(max_bytes, max_pages, max_text_bytes, timeout_seconds, memory_limit_bytes) <= 0:
            raise ValueError("PDF parser limits must be positive")
        self._max_bytes = max_bytes
        self._max_pages = max_pages
        self._max_text_bytes = max_text_bytes
        self._timeout_seconds = timeout_seconds
        self._memory_limit_bytes = memory_limit_bytes

    def parse(self, path: Path) -> ExtractedPdf:
        size = _validate_path(path, max_bytes=self._max_bytes)
        command = [
            sys.executable,
            "-m",
            "app.rag.ingestion.pdf_worker",
            str(path),
            str(self._max_bytes),
            str(self._max_pages),
            str(self._max_text_bytes),
            str(self._memory_limit_bytes),
            str(max(1, int(self._timeout_seconds))),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
                timeout=self._timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            raise PdfExtractionError(
                PdfErrorCode.TIMEOUT, "PDF parsing exceeded the time limit"
            ) from error
        if completed.returncode < 0:
            raise PdfExtractionError(
                PdfErrorCode.RESOURCE_LIMIT, "PDF parser exceeded a resource limit"
            )
        try:
            payload = json.loads(completed.stdout)
        except (json.JSONDecodeError, TypeError) as error:
            raise PdfExtractionError(
                PdfErrorCode.WORKER_FAILED, "PDF parser worker failed"
            ) from error
        if not isinstance(payload, dict):
            raise PdfExtractionError(PdfErrorCode.WORKER_FAILED, "PDF parser worker failed")
        if completed.returncode != 0:
            try:
                code = PdfErrorCode(payload["error"])
            except (KeyError, TypeError, ValueError) as error:
                raise PdfExtractionError(
                    PdfErrorCode.WORKER_FAILED, "PDF parser worker failed"
                ) from error
            raise PdfExtractionError(code, str(payload.get("message") or "PDF parsing failed"))
        try:
            pages = tuple(
                ExtractedPage(page_number=int(page["page_number"]), text=str(page["text"]))
                for page in payload["pages"]
            )
        except (KeyError, TypeError, ValueError) as error:
            raise PdfExtractionError(
                PdfErrorCode.WORKER_FAILED, "PDF parser worker returned invalid output"
            ) from error
        return ExtractedPdf(pages=pages, parser_version=PARSER_VERSION, byte_size=size)


def _validate_path(path: Path, *, max_bytes: int) -> int:
    try:
        size = path.stat().st_size
    except FileNotFoundError as error:
        raise PdfExtractionError(PdfErrorCode.NOT_FOUND, "PDF file does not exist") from error
    if size > max_bytes:
        raise PdfExtractionError(PdfErrorCode.TOO_LARGE, "PDF exceeds the upload size limit")
    return size


def extract_pdf_in_process(
    path: Path,
    *,
    max_bytes: int,
    max_pages: int,
    max_text_bytes: int,
) -> ExtractedPdf:
    """Worker-only extraction entry point; callers should use ``PdfParser``."""

    size = _validate_path(path, max_bytes=max_bytes)

    data = path.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise PdfExtractionError(PdfErrorCode.INVALID_SIGNATURE, "File signature is not a PDF")
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise PdfExtractionError(PdfErrorCode.ENCRYPTED, "Encrypted PDFs are not supported")
        if len(reader.pages) > max_pages:
            raise PdfExtractionError(PdfErrorCode.TOO_MANY_PAGES, "PDF exceeds the page limit")

        pages: list[ExtractedPage] = []
        extracted_bytes = 0
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").replace("\x00", "").strip()
            extracted_bytes += len(text.encode("utf-8"))
            if extracted_bytes > max_text_bytes:
                raise PdfExtractionError(
                    PdfErrorCode.TEXT_TOO_LARGE, "Extracted PDF text exceeds the limit"
                )
            pages.append(ExtractedPage(page_number=index, text=text))
    except PdfExtractionError:
        raise
    except (PdfReadError, ValueError, TypeError, KeyError) as error:
        raise PdfExtractionError(
            PdfErrorCode.MALFORMED, "PDF structure could not be read"
        ) from error

    if not any(page.text for page in pages):
        raise PdfExtractionError(
            PdfErrorCode.NO_TEXT, "PDF has no extractable text; OCR is not supported"
        )
    return ExtractedPdf(pages=tuple(pages), parser_version=PARSER_VERSION, byte_size=size)
