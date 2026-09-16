"""Conservative deterministic candidate extraction used by fake mode and tests."""

from __future__ import annotations

import re

from app.memory.schemas import KEY_KIND, CandidateProposal, MemoryKey

_PATTERNS: tuple[tuple[MemoryKey, re.Pattern[str]], ...] = (
    (
        "preferred_language",
        re.compile(
            r"(?:ưu tiên|hãy)\s+(?:trả lời\s+)?(?:bằng\s+)?(tiếng\s+việt|english)",
            re.IGNORECASE,
        ),
    ),
    (
        "operating_system",
        re.compile(
            r"(?:tôi dùng|máy(?: của tôi)? (?:dùng|chạy))\s+"
            r"(windows\s+(?:10|11)|macos(?:\s+[\w.-]+)?|ubuntu(?:\s+[\w.-]+)?)",
            re.IGNORECASE,
        ),
    ),
    (
        "device_label",
        re.compile(
            r"(?:tên thiết bị|device label)(?: của tôi)?\s+(?:là|:)\s+"
            r"([\w][\w .-]{0,79})",
            re.IGNORECASE,
        ),
    ),
)


def _normalized(value: str) -> str:
    return " ".join(value.strip().rstrip(".,;!?").split())


def extract_candidate_proposals(text: str) -> list[CandidateProposal]:
    """Return only explicit, allowlisted user facts; never instructions or permissions."""

    source = " ".join(text.strip().split())
    if not source:
        return []
    proposals: list[CandidateProposal] = []
    for key, pattern in _PATTERNS:
        match = pattern.search(source)
        if match is None:
            continue
        value = _normalized(match.group(1))
        proposals.append(
            CandidateProposal(
                kind=KEY_KIND[key],
                key=key,
                value=value,
                evidence=source[:500],
            )
        )
    return proposals
