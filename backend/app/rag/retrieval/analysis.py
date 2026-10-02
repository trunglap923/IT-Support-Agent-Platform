"""Deterministic query analysis for dense and sparse retrieval branches."""

from __future__ import annotations

import re
from typing import Protocol

from app.rag.retrieval.models import QuerySpec, RetrievalRequest

_TERM_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
_EXACT_IDENTIFIER_PATTERN = re.compile(
    r"\b(?=[A-Za-z0-9._-]*[A-Za-z])(?=[A-Za-z0-9._-]*\d)"
    r"[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)+\b"
)
_QUERY_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "can",
        "company",
        "demo",
        "does",
        "for",
        "from",
        "how",
        "i",
        "is",
        "of",
        "on",
        "the",
        "to",
        "use",
        "what",
        "which",
        "with",
        "báo",
        "bao",
        "bị",
        "bi",
        "cách",
        "cach",
        "cần",
        "cho",
        "có",
        "co",
        "dùng",
        "dung",
        "gì",
        "gi",
        "không",
        "khong",
        "là",
        "la",
        "lý",
        "ly",
        "nào",
        "nao",
        "như",
        "nhu",
        "thế",
        "thì",
        "thi",
        "tôi",
        "toi",
        "trên",
        "tren",
        "và",
        "va",
        "xử",
        "xu",
        "được",
        "duoc",
    }
)
_SUPPORTED_DOMAIN_PATTERN = re.compile(r"\b(?:vpn|docker|registry|gitlab)\b")
_VIETNAMESE_QUERY_EXPANSIONS: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (
        re.compile(
            r"\b(?:cấu\s+hình|cau\s+hinh|thiết\s+lập|thiet\s+lap|"
            r"cài(?:\s+đặt)?|cai(?:\s+dat)?)\b"
        ),
        ("thiết lập", "cài", "setup", "configure", "install"),
    ),
    (re.compile(r"\b(?:kết\s+nối|ket\s+noi)\b"), ("connect", "connection", "reconnect")),
    (
        re.compile(r"\b(?:đăng\s+nhập|dang\s+nhap|xác\s+thực|xac\s+thuc)\b"),
        ("authenticate", "authentication", "login", "sso"),
    ),
    (re.compile(r"\b(?:chứng\s+chỉ|chung\s+chi)\b"), ("certificate", "ca", "bundle")),
    (re.compile(r"\b(?:mã\s+truy\s+cập|ma\s+truy\s+cap|token)\b"), ("access", "token")),
    (re.compile(r"\b(?:kho\s+docker|kho\s+chứa|kho\s+chua)\b"), ("docker", "registry")),
    (
        re.compile(r"\b(?:xin\s+quyền|xin\s+quyen|yêu\s+cầu\s+quyền|yeu\s+cau\s+quyen)\b"),
        ("access", "permission", "role"),
    ),
    (re.compile(r"\b(?:dự\s+án|du\s+an)\b"), ("project",)),
    (re.compile(r"\b(?:lỗi|loi)\b"), ("error", "troubleshooting")),
)


def meaningful_terms(value: str, *, limit: int = 24) -> tuple[str, ...]:
    """Return stable Unicode search terms without natural-language filler words."""

    terms: list[str] = []
    seen: set[str] = set()
    for token in _TERM_PATTERN.findall(value.casefold()):
        if len(token) < 2 or token in _QUERY_STOP_WORDS or token in seen:
            continue
        seen.add(token)
        terms.append(token)
        if len(terms) == limit:
            break
    return tuple(terms)


def exact_identifiers(value: str) -> tuple[str, ...]:
    """Extract stable technical identifiers without normalizing their spelling."""

    return tuple(dict.fromkeys(_EXACT_IDENTIFIER_PATTERN.findall(value)))


def expand_query_for_retrieval(value: str) -> str:
    """Add bounded English aliases to the dense semantic query only."""

    normalized = " ".join(value.casefold().split())
    if not _SUPPORTED_DOMAIN_PATTERN.search(normalized):
        return value.strip()

    additions: list[str] = []
    seen = set(_TERM_PATTERN.findall(normalized))
    for pattern, aliases in _VIETNAMESE_QUERY_EXPANSIONS:
        if not pattern.search(normalized):
            continue
        for alias in aliases:
            if alias not in seen:
                additions.append(alias)
                seen.add(alias)
    return " ".join((value.strip(), *additions))


class QueryAnalyzer(Protocol):
    def analyze(self, request: RetrievalRequest) -> QuerySpec: ...


class RuleBasedQueryAnalyzer:
    """Baseline analyzer that preserves raw sparse text and expands dense semantics."""

    def analyze(self, request: RetrievalRequest) -> QuerySpec:
        return QuerySpec.from_request(
            request,
            semantic_query=expand_query_for_retrieval(request.raw_query),
            exact_terms=exact_identifiers(request.raw_query),
        )
