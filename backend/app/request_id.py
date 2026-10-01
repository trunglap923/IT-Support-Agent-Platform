"""Request identifiers and structured HTTP lifecycle diagnostics."""

import logging
import time
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.diagnostics import log_event

logger = logging.getLogger(__name__)


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        method = str(scope.get("method", ""))
        path = str(scope.get("path", ""))
        started_at = time.monotonic()
        status_code = 500
        log_level = logging.DEBUG if path.startswith("/api/v1/health/") else logging.INFO
        log_event(
            logger,
            "http.request.started",
            level=log_level,
            request_id=request_id,
            method=method,
            path=path,
        )

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = MutableHeaders(scope=message)
                headers.append("X-Request-ID", request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as error:
            log_event(
                logger,
                "http.request.failed",
                level=logging.ERROR,
                exc_info=True,
                request_id=request_id,
                method=method,
                path=path,
                duration_ms=round((time.monotonic() - started_at) * 1_000, 2),
                error_type=type(error).__name__,
                error=str(error),
            )
            raise
        log_event(
            logger,
            "http.request.completed",
            level=log_level,
            request_id=request_id,
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=round((time.monotonic() - started_at) * 1_000, 2),
        )
