"""Resource-constrained subprocess entry point for PDF extraction."""

from __future__ import annotations

import json
import resource
import sys
from pathlib import Path

from app.rag.ingestion.pdf_parser import PdfExtractionError, extract_pdf_in_process


def _set_limits(memory_bytes: int, cpu_seconds: int) -> None:
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


def main() -> int:
    if len(sys.argv) != 7:
        return 2
    path = Path(sys.argv[1])
    max_bytes, max_pages, max_text_bytes, memory_bytes, cpu_seconds = map(int, sys.argv[2:])
    try:
        _set_limits(memory_bytes, cpu_seconds)
        extracted = extract_pdf_in_process(
            path,
            max_bytes=max_bytes,
            max_pages=max_pages,
            max_text_bytes=max_text_bytes,
        )
    except PdfExtractionError as error:
        print(json.dumps({"error": error.code.value, "message": str(error)}))
        return 1
    except (MemoryError, OSError):
        print(json.dumps({"error": "pdf_resource_limit", "message": "Resource limit exceeded"}))
        return 1
    print(
        json.dumps(
            {
                "pages": [
                    {"page_number": page.page_number, "text": page.text} for page in extracted.pages
                ]
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
