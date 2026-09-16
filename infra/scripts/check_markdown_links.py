"""Validate relative Markdown file links in tracked documentation."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def markdown_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "*.md"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item.decode() for item in result.stdout.split(b"\0") if item]


def link_target(raw: str) -> str | None:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        value = value[1 : value.index(">")]
    else:
        value = value.split(maxsplit=1)[0]
    value = unquote(value.split("#", 1)[0])
    if not value or value.startswith(("#", "http://", "https://", "mailto:")):
        return None
    return value


def main() -> None:
    failures: list[str] = []
    checked = 0
    for document in markdown_files():
        for line_number, line in enumerate(document.read_text(encoding="utf-8").splitlines(), 1):
            for match in LINK.finditer(line):
                value = link_target(match.group(1))
                if value is None:
                    continue
                checked += 1
                target = (document.parent / value).resolve()
                if not target.is_relative_to(ROOT) or not target.exists():
                    failures.append(
                        f"{document.relative_to(ROOT)}:{line_number}: missing {match.group(1)}"
                    )
    if failures:
        print("Markdown link validation failed:")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)
    print(f"Markdown link validation passed: {checked} relative links checked.")


if __name__ == "__main__":
    main()
