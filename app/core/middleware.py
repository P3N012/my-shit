"""Middleware: request-scoped ID + request/response log line."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import request_id_var

logger = logging.getLogger("api.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Assigns a request ID to every request (preferring an upstream
    `X-Request-Id` header if present, otherwise a fresh UUID4), stores
    it in a contextvar so downstream logs can include it, echoes it
    back on the response, and emits one structured access log per
    request.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            elapsed = (time.perf_counter() - started) * 1000
            logger.exception(
                f"{request.method} {request.url.path} 500 {elapsed:.1f}ms"
            )
            request_id_var.reset(token)
            raise

        elapsed = (time.perf_counter() - started) * 1000
        response.headers["X-Request-Id"] = request_id
        logger.info(
            f"{request.method} {request.url.path} {response.status_code} {elapsed:.1f}ms"
        )
        request_id_var.reset(token)
        return response
