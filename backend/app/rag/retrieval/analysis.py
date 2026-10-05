"""Deterministic query analysis for dense and sparse retrieval branches."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, cast

from app.providers.structured import QueryAnalysisResponse
from app.rag.retrieval.models import (
    QueryIntent,
    QuerySpec,
    RetrievalFilters,
    RetrievalRequest,
    VersionScope,
)

_TERM_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
_EXACT_IDENTIFIER_PATTERN = re.compile(
    r"\b(?=[A-Za-z0-9._-]*[A-Za-z])(?=[A-Za-z0-9._-]*\d)"
    r"[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)+\b"
)
_UPPER_EXACT_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]+(?:[_-][A-Z0-9]+)+\b")
_HTTP_STATUS_PATTERN = re.compile(r"\bHTTP(?:[-_ ]?)(?:[1-5]\d\d|[1-5]xx)\b", re.IGNORECASE)
_HEX_ERROR_PATTERN = re.compile(r"\b0x[0-9A-Fa-f]{4,}\b")
_EXPLICIT_VERSION_PATTERN = re.compile(
    r"\b(?:v\s*\d+(?:\.\d+){0,2}|version\s+\d+(?:\.\d+){0,2}|"
    r"phiên\s+bản\s+\d+(?:\.\d+){0,2})\b",
    re.IGNORECASE,
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
_SERVICE_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("vpn", ("vpn", "globalprotect", "gateway")),
    ("registry", ("docker registry", "registry", "container registry")),
    ("gitlab", ("gitlab",)),
)
_PRODUCT_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("globalprotect", ("globalprotect",)),
    ("docker", ("docker", "docker registry")),
    ("gitlab", ("gitlab",)),
)
_OS_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ubuntu", ("ubuntu",)),
    ("windows", ("windows", "win 10", "win10", "win 11", "win11")),
    ("macos", ("macos", "mac os", "osx", "macbook")),
    ("linux", ("linux",)),
)

_INTENT_MARKERS: dict[QueryIntent, tuple[str, ...]] = {
    "identity": (
        "tên tôi",
        "ten toi",
        "họ của tôi",
        "ho cua toi",
        "tên đệm của tôi",
        "ten dem cua toi",
        "tên đầy đủ của tôi",
        "ten day du cua toi",
        "tôi là ai",
        "toi la ai",
        "who am i",
        "my name",
        "my surname",
        "my full name",
        "tài khoản của tôi",
    ),
    "ticket_create": (
        "tạo ticket",
        "tao ticket",
        "mở ticket",
        "mo ticket",
        "create ticket",
        "create a ticket",
        "open ticket",
        "draft ticket",
        "submit ticket",
    ),
    "ticket_read": (
        "ticket của tôi",
        "ticket cua toi",
        "ticket đang mở",
        "ticket dang mo",
        "ticket gần đây",
        "ticket gan day",
        "my tickets",
        "open tickets",
        "recent tickets",
        "liệt kê ticket",
        "liet ke ticket",
        "xem ticket",
    ),
    "service_status": (
        "trạng thái",
        "trang thai",
        "hoạt động không",
        "hoat dong khong",
        "đang hoạt động",
        "dang hoat dong",
        "service status",
        "outage",
        "is down",
        "down không",
    ),
    "memory": (
        "ghi nhớ",
        "ghi nho",
        "hãy nhớ",
        "hay nho",
        "remember",
        "xóa memory",
        "xoa memory",
        "delete memory",
    ),
    "incident": (
        "không kết nối",
        "khong ket noi",
        "không truy cập",
        "khong truy cap",
        "không đăng nhập",
        "khong dang nhap",
        "bị lỗi",
        "bi loi",
        "error",
        "failed",
        "failure",
        "cannot",
        "can't",
        "timeout",
        "certificate warning",
        "certificate",
        "err_",
        "khắc phục",
        "khac phuc",
        "troubleshoot",
    ),
    "knowledge": (
        "cách ",
        "cach ",
        "hướng dẫn",
        "huong dan",
        "làm sao",
        "lam sao",
        "how ",
        "install",
        "configure",
        "setup",
        "truy cập",
        "truy cap",
        "kết nối",
        "ket noi",
        "cài ",
        "cai ",
        "cấu hình",
        "cau hinh",
    ),
}
_SOCIAL_EXACT = frozenset(
    {
        "xin chào",
        "xin chao",
        "chào bạn",
        "chao ban",
        "hello",
        "hi",
        "cảm ơn",
        "cảm ơn bạn",
        "cam on",
        "cam on ban",
        "thank you",
        "thanks",
        "tạm biệt",
        "tam biet",
        "goodbye",
    }
)
_SELF_INTRODUCTION_MARKERS = (
    "tôi tên là",
    "toi ten la",
    "tên tôi là",
    "ten toi la",
    "tên đầy đủ là",
    "ten day du la",
    "tên đầy đủ của tôi là",
    "ten day du cua toi la",
    "họ tên là",
    "ho ten la",
    "my name is",
    "my full name is",
    "i am ",
    "i'm ",
)
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

    matches: list[tuple[int, str]] = []
    for pattern in (
        _EXACT_IDENTIFIER_PATTERN,
        _UPPER_EXACT_PATTERN,
        _HTTP_STATUS_PATTERN,
        _HEX_ERROR_PATTERN,
    ):
        matches.extend((match.start(), match.group(0)) for match in pattern.finditer(value))
    return tuple(dict.fromkeys(item for _, item in sorted(matches)))


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


def _contains_any(value: str, markers: tuple[str, ...]) -> bool:
    return any(marker in value for marker in markers)


def _values_for_aliases(
    normalized: str, aliases: tuple[tuple[str, tuple[str, ...]], ...]
) -> tuple[str, ...]:
    return tuple(
        canonical for canonical, values in aliases if any(value in normalized for value in values)
    )


def _error_codes(value: str, exact_terms: tuple[str, ...]) -> tuple[str, ...]:
    codes = [
        term
        for term in exact_terms
        if term.upper().startswith(("ERR_", "HTTP", "VPN-")) or term.casefold().startswith("0x")
    ]
    return tuple(dict.fromkeys(codes))


def _versions(value: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            match.group(0).replace(" ", "") for match in _EXPLICIT_VERSION_PATTERN.finditer(value)
        )
    )


def _intent(normalized: str, *, has_domain: bool) -> tuple[QueryIntent, float]:
    stripped = normalized.strip(" .!?,")
    asks_support = has_domain or any(
        _contains_any(normalized, markers)
        for intent, markers in _INTENT_MARKERS.items()
        if intent in {"knowledge", "incident"}
    )
    if stripped in _SOCIAL_EXACT:
        return "social", 1.0
    identity_language = _contains_any(
        normalized, _INTENT_MARKERS["identity"]
    ) or (
        not asks_support and _contains_any(normalized, _SELF_INTRODUCTION_MARKERS)
    )
    if identity_language and any(
        marker in normalized for marker in ("?", " gì", " gi", "what", "who")
    ):
        return "identity", 0.98
    if _contains_any(normalized, _SELF_INTRODUCTION_MARKERS) and not asks_support:
        return "social", 0.98
    for intent in (
        "ticket_create",
        "ticket_read",
        "identity",
        "memory",
        "service_status",
        "incident",
        "knowledge",
    ):
        if _contains_any(normalized, _INTENT_MARKERS[intent]):
            confidence = 0.96 if intent not in {"incident", "knowledge"} else 0.9
            return intent, confidence
    if has_domain:
        return "knowledge", 0.65
    return "unknown", 0.2


class QueryAnalyzer(Protocol):
    def analyze(self, request: RetrievalRequest) -> QuerySpec: ...


class DeterministicQueryAnalyzer:
    """Extract intent and technical entities without changing the raw query."""

    def analyze(self, request: RetrievalRequest) -> QuerySpec:
        raw_query = request.raw_query.strip()
        normalized = " ".join(raw_query.casefold().split())
        exact_terms = exact_identifiers(raw_query)
        services = _values_for_aliases(normalized, _SERVICE_ALIASES)
        products = _values_for_aliases(normalized, _PRODUCT_ALIASES)
        operating_systems = _values_for_aliases(normalized, _OS_ALIASES)
        error_codes = _error_codes(raw_query, exact_terms)
        versions = _versions(raw_query)
        version_scope: VersionScope = (
            "historical"
            if any(marker in normalized for marker in ("năm 20", "historical", "cũ", "cu "))
            else "specific"
            if versions
            else "current"
        )
        intent, confidence = _intent(normalized, has_domain=bool(services or products))
        filters = RetrievalFilters(
            services=services,
            products=products,
            operating_systems=operating_systems,
            error_codes=error_codes,
            version_labels=versions,
            version_scope=version_scope,
        )
        metadata_filters = tuple(
            (key, value)
            for key, values in (
                ("service", services),
                ("product", products),
                ("operating_system", operating_systems),
                ("error_code", error_codes),
                ("version", versions),
            )
            for value in values
        )
        if intent == "ticket_read":
            ticket_scope = (
                "open"
                if any(marker in normalized for marker in ("đang mở", "dang mo", "open"))
                else "recent"
            )
            metadata_filters = (*metadata_filters, ("ticket_scope", ticket_scope))
        return QuerySpec.from_request(
            request,
            semantic_query=expand_query_for_retrieval(raw_query),
            exact_terms=exact_terms,
            intent=intent,
            confidence=confidence,
            filters=filters,
            metadata_filters=metadata_filters,
        )


RuleBasedQueryAnalyzer = DeterministicQueryAnalyzer


class QueryAnalysisModel(Protocol):
    async def analyze_query(
        self,
        query: str,
        *,
        deterministic: object,
        max_output_tokens: int,
        operation_id: str,
    ) -> QueryAnalysisResponse: ...


@dataclass(frozen=True, slots=True)
class QueryRewritePolicy:
    model_confidence_threshold: float = 0.7
    retry_confidence_threshold: float = 0.75
    max_model_calls: int = 1
    max_semantic_queries: int = 2

    def use_model(self, spec: QuerySpec) -> bool:
        return (
            self.max_model_calls > 0
            and spec.confidence < self.model_confidence_threshold
            and spec.intent in {"knowledge", "incident", "unknown"}
        )

    def allow_retry(self, spec: QuerySpec) -> bool:
        return self.max_semantic_queries > 1 and spec.confidence < self.retry_confidence_threshold


class ModelQueryAnalyzer:
    """Apply at most one bounded model analysis and preserve deterministic exact terms."""

    def __init__(
        self,
        model: QueryAnalysisModel,
        *,
        max_output_tokens: int = 180,
        max_calls: int = 1,
    ) -> None:
        if max_calls < 0:
            raise ValueError("Model query analysis call limit cannot be negative")
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._max_calls = max_calls
        self._calls_used = 0

    @property
    def calls_used(self) -> int:
        return self._calls_used

    async def analyze(
        self, request: RetrievalRequest, deterministic: QuerySpec, *, operation_id: str
    ) -> QuerySpec:
        if self._calls_used >= self._max_calls:
            return deterministic
        self._calls_used += 1
        response = await self._model.analyze_query(
            request.raw_query,
            deterministic=deterministic,
            max_output_tokens=self._max_output_tokens,
            operation_id=operation_id,
        )
        output = response.analysis
        raw_query_folded = request.raw_query.casefold()
        model_exact_terms = tuple(
            term for term in output.exact_terms if term.casefold() in raw_query_folded
        )
        model_error_codes = tuple(
            code for code in output.error_codes if code.casefold() in raw_query_folded
        )
        model_versions = tuple(
            version for version in output.versions if version.casefold() in raw_query_folded
        )
        semantic_query = output.semantic_query.strip() or deterministic.semantic_query
        missing_exact = [
            token for token in deterministic.exact_terms if token not in semantic_query
        ]
        if missing_exact:
            semantic_query = " ".join((semantic_query, *missing_exact))
        filters = RetrievalFilters(
            services=tuple(dict.fromkeys((*deterministic.filters.services, *output.services))),
            products=tuple(dict.fromkeys((*deterministic.filters.products, *output.products))),
            operating_systems=tuple(
                dict.fromkeys((*deterministic.filters.operating_systems, *output.operating_systems))
            ),
            error_codes=tuple(
                dict.fromkeys((*deterministic.filters.error_codes, *model_error_codes))
            ),
            version_labels=tuple(
                dict.fromkeys((*deterministic.filters.version_labels, *model_versions))
            ),
            version_scope=(
                deterministic.filters.version_scope
                if deterministic.filters.version_scope != "current"
                else cast(VersionScope, output.version_scope)
            ),
        )
        metadata_filters = tuple(
            (key, value)
            for key, values in (
                ("service", filters.services),
                ("product", filters.products),
                ("operating_system", filters.operating_systems),
                ("error_code", filters.error_codes),
                ("version", filters.version_labels),
            )
            for value in values
        )
        return QuerySpec.from_request(
            request,
            intent=output.intent,
            confidence=max(deterministic.confidence, output.confidence),
            semantic_query=semantic_query,
            exact_terms=tuple(dict.fromkeys((*deterministic.exact_terms, *model_exact_terms))),
            filters=filters,
            metadata_filters=metadata_filters,
            analyzer="deterministic+model",
        )


class LowConfidenceRetry:
    """Build one entity-focused dense-query variant for low-confidence analysis."""

    def semantic_queries(self, spec: QuerySpec, *, policy: QueryRewritePolicy) -> tuple[str, ...]:
        primary = spec.semantic_query.strip()
        if not policy.allow_retry(spec):
            return (primary,)
        focused_parts = (
            *spec.exact_terms,
            *spec.filters.error_codes,
            *spec.filters.services,
            *spec.filters.products,
            *spec.filters.operating_systems,
            *spec.filters.version_labels,
            *meaningful_terms(spec.raw_query),
        )
        focused = " ".join(dict.fromkeys(item for item in focused_parts if item)).strip()
        if not focused or focused.casefold() == primary.casefold():
            return (primary,)
        return (primary, focused)[: policy.max_semantic_queries]
