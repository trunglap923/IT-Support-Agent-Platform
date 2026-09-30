"""Consistent, safe HTTP error responses for the public API."""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorEnvelope(BaseModel):
    error: ErrorBody


_STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "NOT_AUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    410: "GONE",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_SERVER_ERROR",
    503: "SERVICE_UNAVAILABLE",
}

_STATUS_MESSAGES = {
    400: "The request is invalid",
    401: "Authentication is required",
    403: "The requested operation is not allowed",
    404: "The requested resource was not found",
    405: "The HTTP method is not allowed for this resource",
    409: "The request conflicts with the current resource state",
    410: "The requested resource is no longer available",
    413: "The request payload is too large",
    422: "The request payload is invalid",
    429: "Too many requests",
    500: "The server could not complete the request",
    503: "The service is temporarily unavailable",
}


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unavailable"))


def _normalize_code(value: object, status_code: int) -> str:
    if isinstance(value, str) and value.strip():
        normalized = re.sub(r"[^A-Z0-9]+", "_", value.strip().upper()).strip("_")
        if normalized:
            return normalized
    return _STATUS_CODES.get(status_code, "HTTP_ERROR")


def _http_error_parts(exception: StarletteHTTPException) -> tuple[str, str]:
    detail = exception.detail
    if isinstance(detail, dict):
        return (
            _normalize_code(detail.get("code"), exception.status_code),
            str(
                detail.get("message")
                or _STATUS_MESSAGES.get(exception.status_code, "Request failed")
            ),
        )
    return (
        _STATUS_CODES.get(exception.status_code, "HTTP_ERROR"),
        str(detail)
        if isinstance(detail, str) and detail
        else _STATUS_MESSAGES.get(exception.status_code, "Request failed"),
    )


def _headers(exception: StarletteHTTPException) -> dict[str, str]:
    headers = dict(exception.headers or {})
    if exception.status_code == 429:
        headers.setdefault("Retry-After", "60")
    elif exception.status_code == 503:
        headers.setdefault("Retry-After", "5")
    return headers


def _response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    envelope = ErrorEnvelope(
        error=ErrorBody(code=code, message=message, request_id=_request_id(request))
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(),
        headers=headers,
    )


async def http_exception_handler(
    request: Request,
    exception: Exception,
) -> JSONResponse:
    if not isinstance(exception, StarletteHTTPException):
        raise exception
    code, message = _http_error_parts(exception)
    return _response(
        request,
        status_code=exception.status_code,
        code=code,
        message=message,
        headers=_headers(exception),
    )


async def validation_exception_handler(
    request: Request,
    exception: Exception,
) -> JSONResponse:
    if not isinstance(exception, RequestValidationError):
        raise exception
    return _response(
        request,
        status_code=422,
        code="VALIDATION_ERROR",
        message=_STATUS_MESSAGES[422],
    )


async def unhandled_exception_handler(
    request: Request,
    exception: Exception,
) -> JSONResponse:
    logger.exception(
        "Unhandled request failure request_id=%s",
        _request_id(request),
        exc_info=exception,
    )
    return _response(
        request,
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        message=_STATUS_MESSAGES[500],
    )


def register_error_handlers(application: FastAPI) -> None:
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_exception_handler(Exception, unhandled_exception_handler)


def error_response_examples() -> dict[int | str, dict[str, Any]]:
    """OpenAPI-ready examples shared by future route response declarations."""

    return {
        status_code: {
            "model": ErrorEnvelope,
            "description": _STATUS_MESSAGES[status_code],
        }
        for status_code in (401, 403, 404, 409, 410, 413, 422, 429, 503)
    }
