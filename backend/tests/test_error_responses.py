from __future__ import annotations

from typing import Annotated

import pytest
from fastapi import FastAPI, HTTPException, Query
from fastapi.testclient import TestClient

from app.api.errors import register_error_handlers
from app.request_id import RequestIdMiddleware


def error_app() -> FastAPI:
    application = FastAPI()
    application.add_middleware(RequestIdMiddleware)
    register_error_handlers(application)

    @application.get("/errors/{status_code}")
    async def raise_http_error(status_code: int) -> None:
        detail: str | dict[str, str] = "Safe route message"
        headers: dict[str, str] | None = None
        if status_code == 413:
            detail = {"code": "pdf_too_large", "message": "PDF exceeds the limit"}
        if status_code == 429:
            headers = {"Retry-After": "17"}
        raise HTTPException(status_code=status_code, detail=detail, headers=headers)

    @application.get("/validation")
    async def validate_query(limit: Annotated[int, Query(gt=0)]) -> dict[str, int]:
        return {"limit": limit}

    @application.get("/crash")
    async def crash() -> None:
        raise RuntimeError("secret internal exception")

    return application


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [
        (401, "NOT_AUTHENTICATED"),
        (403, "FORBIDDEN"),
        (404, "NOT_FOUND"),
        (409, "CONFLICT"),
        (410, "GONE"),
        (413, "PDF_TOO_LARGE"),
        (429, "RATE_LIMITED"),
        (503, "SERVICE_UNAVAILABLE"),
    ],
)
def test_http_errors_use_the_safe_envelope(
    status_code: int,
    expected_code: str,
) -> None:
    with TestClient(error_app(), raise_server_exceptions=False) as client:
        response = client.get(f"/errors/{status_code}")

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == expected_code
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
    assert set(response.json()) == {"error"}
    assert set(response.json()["error"]) == {"code", "message", "request_id"}


def test_retry_after_is_preserved_or_added_for_transient_errors() -> None:
    with TestClient(error_app(), raise_server_exceptions=False) as client:
        rate_limited = client.get("/errors/429")
        unavailable = client.get("/errors/503")

    assert rate_limited.headers["Retry-After"] == "17"
    assert unavailable.headers["Retry-After"] == "5"


def test_validation_errors_do_not_echo_invalid_input() -> None:
    with TestClient(error_app(), raise_server_exceptions=False) as client:
        response = client.get("/validation", params={"limit": "secret-value"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["message"] == "The request payload is invalid"
    assert "secret-value" not in response.text


def test_unhandled_errors_return_a_safe_message() -> None:
    with TestClient(error_app(), raise_server_exceptions=False) as client:
        response = client.get("/crash")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "secret internal exception" not in response.text


def test_framework_404_uses_the_same_envelope() -> None:
    with TestClient(error_app(), raise_server_exceptions=False) as client:
        response = client.get("/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
