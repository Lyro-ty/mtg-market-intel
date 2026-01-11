# backend/tests/test_rate_limit.py
"""Tests for rate limiting middleware."""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
import redis.asyncio as redis

from app.middleware.rate_limit import RateLimitMiddleware


@pytest.fixture
def test_app():
    """Create a test FastAPI app with rate limiting middleware."""
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        redis_url="redis://localhost:6379/0",
        requests_per_minute=60,
        auth_requests_per_minute=5,
    )

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.get("/health")
    async def health_endpoint():
        return {"status": "healthy"}

    @app.post("/auth/login")
    async def login_endpoint():
        return {"status": "logged_in"}

    return app


def test_rate_limit_fails_closed_on_redis_error(test_app):
    """Rate limiting should deny requests when Redis is unavailable.

    This is a critical security test. If Redis is down, rate limiting
    must fail closed (deny requests) not fail open (allow requests).
    Failing open would allow attackers to bypass rate limits by
    taking down Redis.
    """
    client = TestClient(test_app)

    # Mock the get_redis method to raise RedisError
    with patch.object(
        RateLimitMiddleware,
        'get_redis',
        new_callable=AsyncMock,
        side_effect=redis.RedisError("Connection refused")
    ):
        response = client.get("/test")

        # Should return 503 Service Unavailable, NOT 200
        assert response.status_code == 503, (
            f"Expected 503 Service Unavailable when Redis is down, "
            f"got {response.status_code}. Rate limiting must fail closed!"
        )
        assert "temporarily unavailable" in response.json()["detail"].lower()
        assert "Retry-After" in response.headers


def test_rate_limit_fails_closed_on_connection_error(test_app):
    """Rate limiting should deny requests on Redis connection errors."""
    client = TestClient(test_app)

    with patch.object(
        RateLimitMiddleware,
        'get_redis',
        new_callable=AsyncMock,
        side_effect=redis.ConnectionError("Cannot connect to Redis")
    ):
        response = client.get("/test")

        assert response.status_code == 503
        assert "Retry-After" in response.headers


def test_rate_limit_allows_health_check_even_when_redis_down(test_app):
    """Health checks should bypass rate limiting entirely.

    Even if Redis is down, health checks need to work so load balancers
    can still check if the service is running.
    """
    client = TestClient(test_app)

    with patch.object(
        RateLimitMiddleware,
        'get_redis',
        new_callable=AsyncMock,
        side_effect=redis.RedisError("Connection refused")
    ):
        response = client.get("/health")

        # Health checks should always pass through
        assert response.status_code == 200


def test_rate_limit_returns_429_when_limit_exceeded(test_app):
    """Rate limiting should return 429 when limit is exceeded."""
    client = TestClient(test_app)

    # Create a mock Redis that returns a count over the limit
    mock_redis = AsyncMock()
    mock_pipeline = AsyncMock()
    mock_pipeline.execute = AsyncMock(return_value=[100, True])  # 100 requests > 60 limit
    mock_redis.pipeline = lambda: mock_pipeline

    with patch.object(
        RateLimitMiddleware,
        'get_redis',
        new_callable=AsyncMock,
        return_value=mock_redis
    ):
        response = client.get("/test")

        assert response.status_code == 429
        assert "Too many requests" in response.json()["detail"]
        assert response.headers.get("Retry-After") == "60"


def test_rate_limit_allows_request_under_limit(test_app):
    """Rate limiting should allow requests under the limit."""
    client = TestClient(test_app)

    # Create a mock Redis that returns a count under the limit
    mock_redis = AsyncMock()
    mock_pipeline = AsyncMock()
    mock_pipeline.execute = AsyncMock(return_value=[5, True])  # 5 requests < 60 limit
    mock_redis.pipeline = lambda: mock_pipeline

    with patch.object(
        RateLimitMiddleware,
        'get_redis',
        new_callable=AsyncMock,
        return_value=mock_redis
    ):
        response = client.get("/test")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_auth_endpoint_uses_stricter_limit(test_app):
    """Auth endpoints should use stricter rate limits."""
    client = TestClient(test_app)

    # Create a mock Redis that returns 6 requests (over auth limit of 5)
    mock_redis = AsyncMock()
    mock_pipeline = AsyncMock()
    mock_pipeline.execute = AsyncMock(return_value=[6, True])
    mock_redis.pipeline = lambda: mock_pipeline

    with patch.object(
        RateLimitMiddleware,
        'get_redis',
        new_callable=AsyncMock,
        return_value=mock_redis
    ):
        response = client.post("/auth/login")

        # Should be rate limited at 6 requests (> 5 auth limit)
        assert response.status_code == 429


def test_retry_after_header_on_redis_failure(test_app):
    """503 response should include Retry-After header."""
    client = TestClient(test_app)

    with patch.object(
        RateLimitMiddleware,
        'get_redis',
        new_callable=AsyncMock,
        side_effect=redis.RedisError("Connection refused")
    ):
        response = client.get("/test")

        assert response.status_code == 503
        retry_after = response.headers.get("Retry-After")
        assert retry_after is not None
        assert int(retry_after) > 0  # Should be a positive number
