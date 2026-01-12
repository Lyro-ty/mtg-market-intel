"""
Tests for Redis singleton pattern.

Ensures thread-safe initialization of Redis client with proper
asyncio.Lock usage to prevent TOCTOU race conditions.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from app.api.deps import get_redis, _reset_redis_client


@pytest.fixture(autouse=True)
def reset_redis():
    """Reset Redis singleton before each test."""
    _reset_redis_client()
    yield
    _reset_redis_client()


@pytest.mark.asyncio
async def test_redis_singleton_returns_same_instance():
    """Multiple calls should return the same Redis client."""
    mock_client = AsyncMock()

    async def mock_create():
        return mock_client

    with patch("app.api.deps._create_redis_client", side_effect=mock_create) as mock_create_fn:
        client1 = await get_redis()
        client2 = await get_redis()

        assert client1 is client2
        assert mock_create_fn.call_count == 1  # Only created once


@pytest.mark.asyncio
async def test_redis_singleton_concurrent_access():
    """Concurrent access should not create multiple clients."""
    call_count = 0
    mock_client = AsyncMock()

    async def slow_redis_create():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)  # Simulate slow initialization
        return mock_client

    with patch("app.api.deps._create_redis_client", side_effect=slow_redis_create):
        # Launch 10 concurrent requests
        tasks = [get_redis() for _ in range(10)]
        clients = await asyncio.gather(*tasks)

        # All should get the same client
        assert all(c is clients[0] for c in clients)
        # Only one initialization should have happened
        assert call_count == 1


@pytest.mark.asyncio
async def test_redis_fast_path_skips_lock():
    """After initialization, subsequent calls should use fast path without locking."""
    mock_client = AsyncMock()

    async def mock_create():
        return mock_client

    with patch("app.api.deps._create_redis_client", side_effect=mock_create) as mock_create_fn:
        # First call initializes
        client1 = await get_redis()

        # Subsequent calls should be fast and return same instance
        for _ in range(100):
            client = await get_redis()
            assert client is client1

        # Only one Redis client was created
        assert mock_create_fn.call_count == 1
