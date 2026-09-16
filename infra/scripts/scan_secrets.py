"""Fail when tracked repository files contain common credential material."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_TRACKED_NAMES = {".env"}
FORBIDDEN_SUFFIXES = {".key", ".pem", ".p12", ".pfx"}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "OpenAI key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\b(?:gh[opsu]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
}
ASSIGNMENT = re.compile(r"(?m)^\s*(OPENAI_API_KEY|LANGFUSE_SECRET_KEY)\s*[=:]\s*([^\s#][^\r\n]*)$")
SAFE_PLACEHOLDERS = {"<secret>", "<redacted>", "changeme"}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / value.decode() for value in result.stdout.split(b"\0") if value]


def main() -> None:
    findings: list[str] = []
    for path in tracked_files():
        relative = path.relative_to(ROOT)
        if path.name in FORBIDDEN_TRACKED_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            findings.append(f"{relative}: forbidden credential file is tracked")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{relative}: possible {label}")
        if relative != Path(".env.example"):
            for match in ASSIGNMENT.finditer(text):
                value = match.group(2).strip().strip("\"'")
                if (
                    value
                    and value not in SAFE_PLACEHOLDERS
                    and not value.startswith(("${", "test-only-", "ci-only-"))
                ):
                    findings.append(f"{relative}: non-empty {match.group(1)} assignment")
    if findings:
        print("Secret scan failed:")
        for finding in sorted(set(findings)):
            print(f"- {finding}")
        raise SystemExit(1)
    print("Secret scan passed for tracked files.")


if __name__ == "__main__":
    main()
