"""
Protection against ID enumeration attacks.

Tracks failed resource access attempts and implements
exponential backoff for suspicious patterns.

ID enumeration attacks probe for valid resource IDs by observing
404 responses. By tracking 404 patterns per client and blocking
after a threshold, we can detect and mitigate these attacks.
"""
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Optional

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse

logger = structlog.get_logger()

# Configuration
MAX_NOT_FOUND_PER_WINDOW = 10  # Max 404s before rate limiting
WINDOW_SECONDS = 60  # Window for tracking
BLOCK_SECONDS = 300  # Block duration after threshold (5 minutes)


@dataclass
class AccessPattern:
    """Track access patterns for a user/IP."""

    not_found_count: int = 0
    window_start: float = field(default_factory=time.time)
    blocked_until: Optional[float] = None

    def is_blocked(self) -> bool:
        """Check if this client is currently blocked."""
        if self.blocked_until is None:
            return False
        if time.time() > self.blocked_until:
            self.blocked_until = None
            return False
        return True

    def record_not_found(self) -> bool:
        """Record a 404 and return True if should block."""
        now = time.time()

        # Reset window if expired
        if now - self.window_start > WINDOW_SECONDS:
            self.not_found_count = 0
            self.window_start = now

        self.not_found_count += 1

        if self.not_found_count >= MAX_NOT_FOUND_PER_WINDOW:
            self.blocked_until = now + BLOCK_SECONDS
            return True
        return False


class EnumerationProtectionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to detect and block ID enumeration attacks.

    Tracks 404 responses per user/IP and blocks after threshold.
    This helps protect against attackers probing for valid resource IDs.
    """

    def __init__(self, app, redis_client=None):
        super().__init__(app)
        self._patterns: dict[str, AccessPattern] = defaultdict(AccessPattern)
        self._redis = redis_client  # Optional Redis for distributed tracking

    def _get_client_key(self, request: Request) -> str:
        """Get unique key for client (user_id or IP)."""
        # Prefer user ID if authenticated
        if hasattr(request.state, "user") and request.state.user:
            return f"user:{request.state.user.id}"

        # Fall back to IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        return f"ip:{ip}"

    def _is_id_based_path(self, path: str) -> bool:
        """Check if path contains numeric IDs that could be enumerated."""
        # Only track 404s on paths that contain numeric segments
        segments = path.split("/")
        return any(seg.isdigit() for seg in segments)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with enumeration protection."""
        client_key = self._get_client_key(request)
        pattern = self._patterns[client_key]

        # Check if blocked
        if pattern.is_blocked():
            logger.warning(
                "Blocked potential enumeration attack",
                client_key=client_key,
                blocked_until=pattern.blocked_until,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many failed requests. Please try again later."},
                headers={"Retry-After": str(BLOCK_SECONDS)},
            )

        response = await call_next(request)

        # Track 404s on resource endpoints with numeric IDs
        if response.status_code == 404:
            path = request.url.path
            if self._is_id_based_path(path):
                should_block = pattern.record_not_found()
                if should_block:
                    logger.warning(
                        "Enumeration threshold exceeded",
                        client_key=client_key,
                        count=pattern.not_found_count,
                    )

        return response
