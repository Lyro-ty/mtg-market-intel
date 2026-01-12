"""
Tests for health check endpoints.
"""
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.main import app
from app.api.deps import get_redis


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint returns ok."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint returns API info."""
    response = await client.get("/api/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "MTG Market Intel API"
    assert "version" in data


# -----------------------------------------------------------------------------
# Detailed Health Check Tests
# -----------------------------------------------------------------------------


@pytest.fixture
def mock_redis_healthy():
    """Create a healthy mock Redis client."""
    mock = AsyncMock()
    mock.ping = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_redis_unhealthy():
    """Create an unhealthy mock Redis client."""
    mock = AsyncMock()
    mock.ping = AsyncMock(side_effect=Exception("Connection refused"))
    return mock


@pytest.mark.asyncio
async def test_detailed_health_check_returns_200(client: AsyncClient, mock_redis_healthy):
    """Test detailed health check endpoint returns 200."""
    app.dependency_overrides[get_redis] = lambda: mock_redis_healthy
    try:
        response = await client.get("/api/health/detailed")
        assert response.status_code == 200
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.asyncio
async def test_detailed_health_check_response_structure(client: AsyncClient, mock_redis_healthy):
    """Test detailed health check returns expected response structure."""
    app.dependency_overrides[get_redis] = lambda: mock_redis_healthy
    try:
        response = await client.get("/api/health/detailed")
        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "timestamp" in data
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0
        assert "dependencies" in data
        assert isinstance(data["dependencies"], list)
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.asyncio
async def test_detailed_health_check_includes_database(client: AsyncClient, mock_redis_healthy):
    """Test detailed health check includes database status."""
    app.dependency_overrides[get_redis] = lambda: mock_redis_healthy
    try:
        response = await client.get("/api/health/detailed")
        assert response.status_code == 200
        data = response.json()

        # Find database dependency
        db_deps = [d for d in data["dependencies"] if d["name"] == "database"]
        assert len(db_deps) == 1

        db_dep = db_deps[0]
        assert "status" in db_dep
        assert "latency_ms" in db_dep
        assert db_dep["status"] in ["healthy", "degraded", "unhealthy"]
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.asyncio
async def test_detailed_health_check_includes_redis(client: AsyncClient, mock_redis_healthy):
    """Test detailed health check includes Redis status."""
    app.dependency_overrides[get_redis] = lambda: mock_redis_healthy
    try:
        response = await client.get("/api/health/detailed")
        assert response.status_code == 200
        data = response.json()

        # Find Redis dependency
        redis_deps = [d for d in data["dependencies"] if d["name"] == "redis"]
        assert len(redis_deps) == 1

        redis_dep = redis_deps[0]
        assert "status" in redis_dep
        assert "latency_ms" in redis_dep
        assert redis_dep["status"] in ["healthy", "degraded", "unhealthy"]
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.asyncio
async def test_detailed_health_overall_status_healthy(client: AsyncClient, mock_redis_healthy):
    """Test overall status is healthy when all dependencies are healthy."""
    app.dependency_overrides[get_redis] = lambda: mock_redis_healthy
    try:
        response = await client.get("/api/health/detailed")
        assert response.status_code == 200
        data = response.json()

        # With mocked fast responses, status should be healthy
        # (database is real but in-memory SQLite, should be fast)
        assert data["status"] == "healthy"
    finally:
        app.dependency_overrides.pop(get_redis, None)


@pytest.mark.asyncio
async def test_detailed_health_overall_status_unhealthy_on_redis_failure(
    client: AsyncClient, mock_redis_unhealthy
):
    """Test overall status is unhealthy when Redis is down."""
    app.dependency_overrides[get_redis] = lambda: mock_redis_unhealthy
    try:
        response = await client.get("/api/health/detailed")
        assert response.status_code == 200
        data = response.json()

        # Overall status should be unhealthy
        assert data["status"] == "unhealthy"

        # Redis should show error
        redis_dep = next(d for d in data["dependencies"] if d["name"] == "redis")
        assert redis_dep["status"] == "unhealthy"
        assert redis_dep["latency_ms"] == -1
        assert redis_dep["message"] is not None
        assert "Connection refused" in redis_dep["message"]
    finally:
        app.dependency_overrides.pop(get_redis, None)

