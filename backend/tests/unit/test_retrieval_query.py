from app.providers.structured import QueryAnalysisOutput, QueryAnalysisResponse
from app.rag.retrieval.analysis import (
    DeterministicQueryAnalyzer,
    LowConfidenceRetry,
    ModelQueryAnalyzer,
    QueryRewritePolicy,
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


def test_analysis_extracts_error_version_os_service_and_product() -> None:
    query = "GlobalProtect v6.1 trên Ubuntu báo ERR_CERT_AUTHORITY_INVALID khi vào VPN"

    spec = DeterministicQueryAnalyzer().analyze(RetrievalRequest(raw_query=query))

    assert spec.intent == "incident"
    assert spec.exact_terms == ("v6.1", "ERR_CERT_AUTHORITY_INVALID")
    assert spec.filters.error_codes == ("ERR_CERT_AUTHORITY_INVALID",)
    assert spec.filters.version_labels == ("v6.1",)
    assert spec.filters.operating_systems == ("ubuntu",)
    assert spec.filters.services == ("vpn",)
    assert spec.filters.products == ("globalprotect",)
    assert spec.filters.version_scope == "specific"


def test_analysis_handles_mixed_vietnamese_english_without_losing_http_code() -> None:
    query = "Docker Registry bị timeout với HTTP-502 trên Windows"

    spec = DeterministicQueryAnalyzer().analyze(RetrievalRequest(raw_query=query))

    assert spec.intent == "incident"
    assert "HTTP-502" in spec.exact_terms
    assert spec.filters.error_codes == ("HTTP-502",)
    assert spec.filters.services == ("registry",)
    assert spec.filters.products == ("docker",)
    assert spec.filters.operating_systems == ("windows",)


def test_low_confidence_retry_is_bounded_and_preserves_exact_tokens() -> None:
    spec = DeterministicQueryAnalyzer().analyze(
        RetrievalRequest(raw_query="VPN-1042 GlobalProtect")
    )
    queries = LowConfidenceRetry().semantic_queries(spec, policy=QueryRewritePolicy())

    assert len(queries) == 2
    assert all("VPN-1042" in query for query in queries)


def test_model_analysis_cannot_drop_deterministic_exact_tokens() -> None:
    class StubModel:
        def __init__(self) -> None:
            self.calls = 0

        async def analyze_query(self, query: str, **kwargs: object) -> QueryAnalysisResponse:
            del query, kwargs
            self.calls += 1
            return QueryAnalysisResponse(
                analysis=QueryAnalysisOutput(
                    intent="incident",
                    semantic_query="VPN certificate failure",
                    exact_terms=["INCIDENT-999"],
                    services=["vpn"],
                    error_codes=["INCIDENT-999"],
                    versions=["9.9"],
                    confidence=0.86,
                ),
                provider_request_id="stub-query-analysis",
                input_tokens=10,
                output_tokens=5,
            )

    async def scenario() -> None:
        request = RetrievalRequest(raw_query="VPN-1042 báo lỗi")
        deterministic = DeterministicQueryAnalyzer().analyze(request)
        provider = StubModel()
        analyzer = ModelQueryAnalyzer(provider)
        modeled = await analyzer.analyze(
            request,
            deterministic,
            operation_id="test-query-analysis",
        )

        assert modeled.raw_query == request.raw_query
        assert modeled.sparse_query == request.raw_query
        assert modeled.exact_terms == ("VPN-1042",)
        assert modeled.filters.error_codes == ("VPN-1042",)
        assert modeled.filters.version_labels == ()
        assert "VPN-1042" in modeled.semantic_query
        assert modeled.analyzer == "deterministic+model"
        second = await analyzer.analyze(
            request,
            deterministic,
            operation_id="test-query-analysis-second",
        )
        assert second is deterministic
        assert provider.calls == 1

    import asyncio

    asyncio.run(scenario())
