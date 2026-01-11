"""Request ID middleware for distributed tracing."""
import uuid
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import structlog


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Add unique request ID to each request for tracing.

    This middleware:
    1. Uses X-Request-ID header if provided by client/proxy, otherwise generates a new UUID
    2. Binds the request ID to structlog context for automatic inclusion in all logs
    3. Stores the request ID in request.state for access in route handlers
    4. Returns the request ID in response headers for client correlation
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Use X-Request-ID header if provided, otherwise generate
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Bind to structlog context for automatic inclusion in all log messages
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Store in request state for access in routes
        request.state.request_id = request_id

        response = await call_next(request)

        # Add to response headers for client correlation
        response.headers["X-Request-ID"] = request_id

        return response
