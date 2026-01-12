"""Tests for enumeration protection middleware."""
import time
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.enumeration_protection import (
    EnumerationProtectionMiddleware,
    AccessPattern,
    MAX_NOT_FOUND_PER_WINDOW,
    WINDOW_SECONDS,
    BLOCK_SECONDS,
)


class TestAccessPattern:
    """Tests for the AccessPattern dataclass."""

    def test_blocks_after_threshold(self):
        """Pattern should block after MAX_NOT_FOUND_PER_WINDOW 404s."""
        pattern = AccessPattern()

        for i in range(MAX_NOT_FOUND_PER_WINDOW - 1):
            assert not pattern.record_not_found()
            assert not pattern.is_blocked()

        # This one should trigger block
        assert pattern.record_not_found()
        assert pattern.is_blocked()

    def test_window_reset(self):
        """Pattern should reset after window expires."""
        pattern = AccessPattern()
        pattern.window_start = 0  # Expired window (long ago)

        # Should reset and not immediately block
        assert not pattern.record_not_found()
        assert pattern.not_found_count == 1

    def test_block_expires(self):
        """Block should expire after BLOCK_SECONDS."""
        pattern = AccessPattern()
        pattern.blocked_until = time.time() - 1  # Expired block

        assert not pattern.is_blocked()
        assert pattern.blocked_until is None  # Should be cleared

    def test_block_active(self):
        """Block should be active within BLOCK_SECONDS."""
        pattern = AccessPattern()
        pattern.blocked_until = time.time() + 100  # Block in future

        assert pattern.is_blocked()

    def test_not_blocked_initially(self):
        """New pattern should not be blocked."""
        pattern = AccessPattern()
        assert not pattern.is_blocked()


class TestEnumerationProtectionMiddleware:
    """Tests for the EnumerationProtectionMiddleware."""

    @pytest.fixture
    def test_app(self):
        """Create a test FastAPI app with enumeration protection middleware."""
        app = FastAPI()
        app.add_middleware(EnumerationProtectionMiddleware)

        @app.get("/cards/{card_id}")
        async def get_card(card_id: int):
            # Simulate 404 for odd IDs
            if card_id % 2 == 1:
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Card not found")
            return {"id": card_id, "name": "Test Card"}

        @app.get("/users/{user_id}")
        async def get_user(user_id: int):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="User not found")

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        @app.get("/search")
        async def search():
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="No results")

        return app

    def test_allows_normal_requests(self, test_app):
        """Normal requests should pass through."""
        client = TestClient(test_app)
        response = client.get("/cards/2")  # Even ID returns 200
        assert response.status_code == 200

    def test_allows_few_404s(self, test_app):
        """A few 404s should not trigger blocking."""
        client = TestClient(test_app)

        # Make a few 404 requests (less than threshold)
        for i in range(3):
            response = client.get(f"/cards/{2*i + 1}")  # Odd IDs return 404
            assert response.status_code == 404

        # Should still allow requests
        response = client.get("/cards/2")
        assert response.status_code == 200

    def test_blocks_after_threshold(self, test_app):
        """Should block after MAX_NOT_FOUND_PER_WINDOW 404s on ID-based paths."""
        client = TestClient(test_app)

        # Make enough 404 requests to trigger block
        for i in range(MAX_NOT_FOUND_PER_WINDOW):
            response = client.get(f"/users/{i}")
            # May be 404 or 429 depending on when block kicks in
            assert response.status_code in [404, 429]

        # Next request should be blocked
        response = client.get("/users/999")
        assert response.status_code == 429
        assert "Too many failed requests" in response.json()["detail"]
        assert "Retry-After" in response.headers

    def test_does_not_track_non_id_paths(self, test_app):
        """404s on non-ID paths should not count toward enumeration."""
        client = TestClient(test_app)

        # Make many 404 requests on non-ID path
        for i in range(MAX_NOT_FOUND_PER_WINDOW + 5):
            response = client.get("/search")
            # Should never block because path has no numeric ID
            assert response.status_code == 404

    def test_all_requests_blocked_once_flagged(self, test_app):
        """Once blocked, all requests from client should be blocked.

        This is correct security behavior - once an attacker is flagged,
        they should be blocked entirely, not just from ID-based paths.
        Health checks are typically accessed from infrastructure (load balancers),
        not from the attacker's IP.
        """
        client = TestClient(test_app)

        # Trigger block
        for i in range(MAX_NOT_FOUND_PER_WINDOW + 1):
            client.get(f"/users/{i}")

        # Verify blocked on ID-based path
        response = client.get("/users/999")
        assert response.status_code == 429

        # All requests from this client should be blocked
        response = client.get("/health")
        assert response.status_code == 429

    def test_retry_after_header(self, test_app):
        """429 response should include Retry-After header."""
        client = TestClient(test_app)

        # Trigger block
        for i in range(MAX_NOT_FOUND_PER_WINDOW + 1):
            client.get(f"/users/{i}")

        response = client.get("/users/999")
        assert response.status_code == 429
        retry_after = response.headers.get("Retry-After")
        assert retry_after is not None
        assert int(retry_after) == BLOCK_SECONDS


class TestClientKeyExtraction:
    """Tests for client key extraction logic."""

    @pytest.fixture
    def middleware(self):
        """Create a middleware instance for testing."""
        from fastapi import FastAPI
        app = FastAPI()
        return EnumerationProtectionMiddleware(app)

    def test_uses_ip_when_no_user(self, middleware):
        """Should use IP address when no user is authenticated."""
        request = MagicMock()
        request.state = MagicMock()
        del request.state.user  # No user attribute
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "192.168.1.100"

        key = middleware._get_client_key(request)
        assert key == "ip:192.168.1.100"

    def test_uses_forwarded_ip(self, middleware):
        """Should use X-Forwarded-For header when present."""
        request = MagicMock()
        request.state = MagicMock()
        del request.state.user
        request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}
        request.client = MagicMock()
        request.client.host = "192.168.1.100"

        key = middleware._get_client_key(request)
        assert key == "ip:10.0.0.1"  # First IP in chain

    def test_uses_user_id_when_authenticated(self, middleware):
        """Should use user ID when user is authenticated."""
        request = MagicMock()
        request.state = MagicMock()
        request.state.user = MagicMock()
        request.state.user.id = 12345
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "192.168.1.100"

        key = middleware._get_client_key(request)
        assert key == "user:12345"


class TestPathDetection:
    """Tests for ID-based path detection."""

    @pytest.fixture
    def middleware(self):
        """Create a middleware instance for testing."""
        from fastapi import FastAPI
        app = FastAPI()
        return EnumerationProtectionMiddleware(app)

    def test_detects_id_paths(self, middleware):
        """Should detect paths with numeric IDs."""
        assert middleware._is_id_based_path("/cards/123")
        assert middleware._is_id_based_path("/api/users/456/inventory")
        assert middleware._is_id_based_path("/cards/123/prices/789")

    def test_ignores_non_id_paths(self, middleware):
        """Should not flag paths without numeric IDs."""
        assert not middleware._is_id_based_path("/cards")
        assert not middleware._is_id_based_path("/api/health")
        assert not middleware._is_id_based_path("/search")
        assert not middleware._is_id_based_path("/users/me")
