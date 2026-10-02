from app.rag.retrieval.analysis import (
    RuleBasedQueryAnalyzer,
    exact_identifiers,
)
from app.rag.retrieval.models import RetrievalRequest
from app.rag.retrieval.query import expand_query_for_retrieval, meaningful_terms


def test_vietnamese_vpn_query_adds_bounded_english_aliases() -> None:
    expanded = expand_query_for_retrieval("Cách cấu hình VPN trên Ubuntu như thế nào?")
    terms = set(meaningful_terms(expanded))

    assert {"vpn", "ubuntu", "setup", "configure", "install"} <= terms
    assert {"thiết", "lập", "cài"} <= terms


def test_unaccented_docker_query_adds_registry_and_login_aliases() -> None:
    expanded = expand_query_for_retrieval("Lam sao dang nhap kho Docker?")
    terms = set(meaningful_terms(expanded))

    assert {"docker", "registry", "authentication", "login", "sso"} <= terms


def test_query_outside_supported_domains_is_not_expanded() -> None:
    query = "Máy in tầng 8 bị lỗi"

    assert expand_query_for_retrieval(query) == query


def test_query_analysis_preserves_raw_sparse_query_and_exact_identifiers() -> None:
    query = "VPN-1042 trên GlobalProtect-6.1 báo HTTP-502"

    spec = RuleBasedQueryAnalyzer().analyze(RetrievalRequest(raw_query=query))

    assert spec.sparse_query == query
    assert spec.raw_query == query
    assert spec.semantic_query.startswith(query)
    assert spec.exact_terms == ("VPN-1042", "GlobalProtect-6.1", "HTTP-502")
    assert exact_identifiers(query) == spec.exact_terms
