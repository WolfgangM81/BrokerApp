"""HTTP middleware: request id, structured logging, basic timing."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request_id to the request, log start/end, set response header."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        log = structlog.get_logger("api.request")
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            log.error("request_failed", duration_ms=round(duration_ms, 1))
            structlog.contextvars.clear_contextvars()
            raise
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["x-request-id"] = request_id
        log.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=round(duration_ms, 1),
        )
        structlog.contextvars.clear_contextvars()
        return response
