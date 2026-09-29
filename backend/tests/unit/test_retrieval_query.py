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
