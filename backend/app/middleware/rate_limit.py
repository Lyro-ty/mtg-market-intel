"""Rate limiting middleware using Redis."""
import time
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse
import redis.asyncio as redis

from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit requests by IP address."""

    def __init__(
        self,
        app,
        redis_url: str = None,
        requests_per_minute: int = 60,
        auth_requests_per_minute: int = 5,
    ):
        super().__init__(app)
        self.redis_url = redis_url or settings.redis_url
        self.requests_per_minute = requests_per_minute
        self.auth_requests_per_minute = auth_requests_per_minute
        self._redis: redis.Redis | None = None

    async def get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url)
        return self._redis

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/api/health"]:
            return await call_next(request)

        # Handle X-Forwarded-For for proxy detection
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        # Use stricter limits for sensitive auth endpoints (login, register, oauth)
        # Exclude /auth/me which is called frequently for session checks
        path = request.url.path
        is_auth_endpoint = (
            ("/auth/" in path or "/login" in path)
            and "/auth/me" not in path  # /auth/me is not a login attempt
        )
        limit = self.auth_requests_per_minute if is_auth_endpoint else self.requests_per_minute

        # Create rate limit key
        window = int(time.time() // 60)  # 1-minute window
        key = f"rate_limit:{client_ip}:{window}"
        if is_auth_endpoint:
            key = f"rate_limit:auth:{client_ip}:{window}"

        try:
            r = await self.get_redis()
            # Use pipelining to avoid race condition between INCR and EXPIRE
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, 60)
            results = await pipe.execute()
            current = results[0]

            if current > limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please try again later."},
                    headers={"Retry-After": "60"},
                )
        except redis.RedisError:
            # If Redis is down, allow the request (fail open)
            pass

        response = await call_next(request)
        return response
