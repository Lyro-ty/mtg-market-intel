"""
Tests for notification API endpoints.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType, NotificationPriority
from app.models.user import User


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4GQJfIK1R1MBfG.",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def auth_headers(test_user: User, client: AsyncClient) -> dict:
    """Create auth headers with a mock current user."""
    from app.api.deps import get_current_user
    from app.main import app

    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield {}
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def test_notifications(
    db_session: AsyncSession,
    test_user: User,
) -> list[Notification]:
    """Create test notifications in the database."""
    notifications = [
        Notification(
            user_id=test_user.id,
            type=NotificationType.PRICE_ALERT,
            priority=NotificationPriority.HIGH,
            title="Price Target Hit",
            message="Card reached your target price",
            read=False,
        ),
        Notification(
            user_id=test_user.id,
            type=NotificationType.PRICE_SPIKE,
            priority=NotificationPriority.MEDIUM,
            title="Price Spike Detected",
            message="A card in your collection spiked 20%",
            read=False,
        ),
        Notification(
            user_id=test_user.id,
            type=NotificationType.MILESTONE,
            priority=NotificationPriority.LOW,
            title="Milestone Achieved",
            message="Your collection reached 100 cards!",
            read=True,
        ),
    ]
    db_session.add_all(notifications)
    await db_session.commit()
    for n in notifications:
        await db_session.refresh(n)
    return notifications


@pytest.mark.asyncio
class TestListNotifications:
    """Test GET /api/notifications endpoint."""

    async def test_list_notifications(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_notifications: list[Notification],
    ):
        """Should return all user notifications."""
        response = await client.get(
            "/api/notifications",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "unread_count" in data
        assert data["total"] == 3
        assert data["unread_count"] == 2
        assert len(data["items"]) == 3

    async def test_list_notifications_filter_unread(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_notifications: list[Notification],
    ):
        """Should only return unread notifications when filtered."""
        response = await client.get(
            "/api/notifications?unread_only=true",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert all(item["read"] is False for item in data["items"])

    async def test_list_notifications_filter_type(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_notifications: list[Notification],
    ):
        """Should filter notifications by type."""
        response = await client.get(
            "/api/notifications?type=price_alert",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["type"] == "price_alert"
        assert data["items"][0]["title"] == "Price Target Hit"

    async def test_list_notifications_invalid_type(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_notifications: list[Notification],
    ):
        """Should return 400 for invalid notification type."""
        response = await client.get(
            "/api/notifications?type=invalid_type",
            headers=auth_headers,
        )

        assert response.status_code == 400
        data = response.json()
        assert "Invalid notification type" in data["detail"]


@pytest.mark.asyncio
class TestUnreadCount:
    """Test GET /api/notifications/unread-count endpoint."""

    async def test_get_unread_count(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_notifications: list[Notification],
    ):
        """Should return unread count with breakdown by type."""
        response = await client.get(
            "/api/notifications/unread-count",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert data["by_type"] is not None
        assert data["by_type"]["price_alert"] == 1
        assert data["by_type"]["price_spike"] == 1

    async def test_get_unread_count_empty(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
    ):
        """Should return zero when no unread notifications exist."""
        response = await client.get(
            "/api/notifications/unread-count",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0


@pytest.mark.asyncio
class TestMarkNotificationRead:
    """Test PATCH /api/notifications/{id} endpoint."""

    async def test_mark_notification_read(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_notifications: list[Notification],
    ):
        """Should mark a notification as read."""
        notification_id = test_notifications[0].id
        response = await client.patch(
            f"/api/notifications/{notification_id}",
            json={"read": True},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["read"] is True
        assert data["read_at"] is not None

    async def test_mark_notification_unread(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_notifications: list[Notification],
    ):
        """Should mark a notification as unread."""
        # Use the notification that is already read
        notification_id = test_notifications[2].id
        response = await client.patch(
            f"/api/notifications/{notification_id}",
            json={"read": False},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["read"] is False
        assert data["read_at"] is None

    async def test_notification_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
    ):
        """Should return 404 for non-existent notification."""
        response = await client.patch(
            "/api/notifications/99999",
            json={"read": True},
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Notification not found"


@pytest.mark.asyncio
class TestMarkAllRead:
    """Test POST /api/notifications/mark-all-read endpoint."""

    async def test_mark_all_read(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_notifications: list[Notification],
    ):
        """Should mark all notifications as read."""
        response = await client.post(
            "/api/notifications/mark-all-read",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["marked_count"] == 2  # 2 were unread

        # Verify all are now read
        list_response = await client.get(
            "/api/notifications/unread-count",
            headers=auth_headers,
        )
        assert list_response.json()["count"] == 0

    async def test_mark_all_read_when_empty(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
    ):
        """Should return 0 count when no unread notifications."""
        response = await client.post(
            "/api/notifications/mark-all-read",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["marked_count"] == 0


@pytest.mark.asyncio
class TestDeleteNotification:
    """Test DELETE /api/notifications/{id} endpoint."""

    async def test_delete_notification(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_notifications: list[Notification],
    ):
        """Should delete a notification and return 204."""
        notification_id = test_notifications[0].id
        response = await client.delete(
            f"/api/notifications/{notification_id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verify it's deleted
        list_response = await client.get(
            "/api/notifications",
            headers=auth_headers,
        )
        assert list_response.json()["total"] == 2

    async def test_delete_notification_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
    ):
        """Should return 404 for non-existent notification."""
        response = await client.delete(
            "/api/notifications/99999",
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Notification not found"


@pytest.mark.asyncio
class TestUnauthenticatedAccess:
    """Test that endpoints require authentication."""

    async def test_unauthenticated_list_notifications(self, client: AsyncClient):
        """Should return 401 when not authenticated."""
        response = await client.get("/api/notifications")
        assert response.status_code == 401

    async def test_unauthenticated_unread_count(self, client: AsyncClient):
        """Should return 401 when not authenticated."""
        response = await client.get("/api/notifications/unread-count")
        assert response.status_code == 401

    async def test_unauthenticated_mark_read(self, client: AsyncClient):
        """Should return 401 when not authenticated."""
        response = await client.patch(
            "/api/notifications/1",
            json={"read": True},
        )
        assert response.status_code == 401

    async def test_unauthenticated_mark_all_read(self, client: AsyncClient):
        """Should return 401 when not authenticated."""
        response = await client.post("/api/notifications/mark-all-read")
        assert response.status_code == 401

    async def test_unauthenticated_delete(self, client: AsyncClient):
        """Should return 401 when not authenticated."""
        response = await client.delete("/api/notifications/1")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestNotificationOwnership:
    """Test that users can only access their own notifications."""

    async def test_cannot_access_other_users_notification(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        auth_headers: dict,
        test_user: User,
    ):
        """Should return 404 when accessing another user's notification."""
        # Create another user with a notification
        other_user = User(
            email="other@example.com",
            username="otheruser",
            hashed_password="$2b$12$hash",
            is_active=True,
        )
        db_session.add(other_user)
        await db_session.flush()

        other_notification = Notification(
            user_id=other_user.id,
            type=NotificationType.SYSTEM,
            priority=NotificationPriority.LOW,
            title="Other User Notification",
            message="This belongs to another user",
            read=False,
        )
        db_session.add(other_notification)
        await db_session.commit()
        await db_session.refresh(other_notification)

        # Try to access it as the test user
        response = await client.patch(
            f"/api/notifications/{other_notification.id}",
            json={"read": True},
            headers=auth_headers,
        )

        assert response.status_code == 404

    async def test_list_only_shows_own_notifications(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        auth_headers: dict,
        test_user: User,
        test_notifications: list[Notification],
    ):
        """Should only list notifications belonging to the authenticated user."""
        # Create another user with a notification
        other_user = User(
            email="other@example.com",
            username="otheruser",
            hashed_password="$2b$12$hash",
            is_active=True,
        )
        db_session.add(other_user)
        await db_session.flush()

        other_notification = Notification(
            user_id=other_user.id,
            type=NotificationType.SYSTEM,
            priority=NotificationPriority.LOW,
            title="Other User Notification",
            message="This belongs to another user",
            read=False,
        )
        db_session.add(other_notification)
        await db_session.commit()

        # List notifications as test user
        response = await client.get(
            "/api/notifications",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Should only see test_user's 3 notifications, not other_user's
        assert data["total"] == 3
        for item in data["items"]:
            assert item["user_id"] == test_user.id
