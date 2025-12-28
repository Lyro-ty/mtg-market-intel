"""
Tests for Want List API endpoints.

Tests CRUD operations for the /api/want-list endpoints including
authentication, validation, and proper user scoping.
"""
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card
from app.models.user import User
from app.models.want_list import WantListItem


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        email="wantlist-test@example.com",
        username="wantlistuser",
        hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4GQJfIK1R1MBfG.",  # 'password'
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_card(db_session: AsyncSession) -> Card:
    """Create a test card."""
    card = Card(
        scryfall_id="want-list-test-card-001",
        name="Test Want Card",
        set_code="TST",
        collector_number="1",
        rarity="rare",
    )
    db_session.add(card)
    await db_session.commit()
    await db_session.refresh(card)
    return card


@pytest.fixture
async def second_test_card(db_session: AsyncSession) -> Card:
    """Create a second test card for duplicate tests."""
    card = Card(
        scryfall_id="want-list-test-card-002",
        name="Second Test Card",
        set_code="TST",
        collector_number="2",
        rarity="uncommon",
    )
    db_session.add(card)
    await db_session.commit()
    await db_session.refresh(card)
    return card


@pytest.fixture
async def auth_headers(test_user: User, client: AsyncClient) -> dict:
    """Create auth headers by overriding the get_current_user dependency."""
    from app.api.deps import get_current_user
    from app.main import app

    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield {}
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def existing_want_list_item(
    db_session: AsyncSession,
    test_user: User,
    test_card: Card,
) -> WantListItem:
    """Create an existing want list item for testing retrieval/update/delete."""
    item = WantListItem(
        user_id=test_user.id,
        card_id=test_card.id,
        target_price=Decimal("10.00"),
        priority="medium",
        alert_enabled=True,
        notes="Test notes",
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return item


@pytest.mark.asyncio
class TestCreateWantListItem:
    """Tests for POST /api/want-list"""

    async def test_create_want_list_item(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        auth_headers: dict,
        test_card: Card,
    ):
        """POST creates item with 201."""
        response = await client.post(
            "/api/want-list",
            headers=auth_headers,
            json={
                "card_id": test_card.id,
                "target_price": 15.50,
                "priority": "high",
                "alert_enabled": True,
                "notes": "Need this for my deck",
            },
        )

        assert response.status_code == 201
        data = response.json()

        assert data["card_id"] == test_card.id
        assert data["target_price"] == "15.50"
        assert data["priority"] == "high"
        assert data["alert_enabled"] is True
        assert data["notes"] == "Need this for my deck"
        assert "id" in data
        assert "created_at" in data
        assert data["card"]["name"] == "Test Want Card"
        assert data["card"]["set_code"] == "TST"

    async def test_create_want_list_item_duplicate(
        self,
        client: AsyncClient,
        auth_headers: dict,
        existing_want_list_item: WantListItem,
        test_card: Card,
    ):
        """POST returns 400 for duplicate card."""
        response = await client.post(
            "/api/want-list",
            headers=auth_headers,
            json={
                "card_id": test_card.id,
                "target_price": 20.00,
            },
        )

        assert response.status_code == 400
        assert "already on your want list" in response.json()["detail"]

    async def test_create_want_list_item_card_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """POST returns 404 for non-existent card."""
        response = await client.post(
            "/api/want-list",
            headers=auth_headers,
            json={
                "card_id": 999999,
                "target_price": 10.00,
            },
        )

        assert response.status_code == 404
        assert "Card not found" in response.json()["detail"]


@pytest.mark.asyncio
class TestListWantListItems:
    """Tests for GET /api/want-list"""

    async def test_list_want_list_items(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        auth_headers: dict,
        test_user: User,
        test_card: Card,
        second_test_card: Card,
    ):
        """GET returns paginated list."""
        # Create multiple want list items
        item1 = WantListItem(
            user_id=test_user.id,
            card_id=test_card.id,
            target_price=Decimal("10.00"),
            priority="high",
        )
        item2 = WantListItem(
            user_id=test_user.id,
            card_id=second_test_card.id,
            target_price=Decimal("5.00"),
            priority="low",
        )
        db_session.add_all([item1, item2])
        await db_session.commit()

        response = await client.get(
            "/api/want-list",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "has_more" in data

        assert data["total"] == 2
        assert len(data["items"]) == 2
        # High priority should come first
        assert data["items"][0]["priority"] == "high"

    async def test_list_want_list_items_empty(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """GET returns empty list for new user."""
        response = await client.get(
            "/api/want-list",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["items"] == []
        assert data["total"] == 0
        assert data["has_more"] is False

    async def test_list_want_list_items_with_pagination(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        auth_headers: dict,
        test_user: User,
    ):
        """GET respects pagination parameters."""
        # Create 5 cards and want list items
        for i in range(5):
            card = Card(
                scryfall_id=f"pagination-test-{i}",
                name=f"Pagination Card {i}",
                set_code="TST",
                collector_number=str(100 + i),
            )
            db_session.add(card)
            await db_session.flush()

            item = WantListItem(
                user_id=test_user.id,
                card_id=card.id,
                target_price=Decimal("10.00"),
            )
            db_session.add(item)

        await db_session.commit()

        response = await client.get(
            "/api/want-list?page=1&page_size=2",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["has_more"] is True

    async def test_list_want_list_items_filter_by_priority(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        auth_headers: dict,
        test_user: User,
        test_card: Card,
        second_test_card: Card,
    ):
        """GET filters by priority when specified."""
        # Create items with different priorities
        item1 = WantListItem(
            user_id=test_user.id,
            card_id=test_card.id,
            target_price=Decimal("10.00"),
            priority="high",
        )
        item2 = WantListItem(
            user_id=test_user.id,
            card_id=second_test_card.id,
            target_price=Decimal("5.00"),
            priority="low",
        )
        db_session.add_all([item1, item2])
        await db_session.commit()

        response = await client.get(
            "/api/want-list?priority=high",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 1
        assert data["items"][0]["priority"] == "high"


@pytest.mark.asyncio
class TestGetWantListItem:
    """Tests for GET /api/want-list/{item_id}"""

    async def test_get_want_list_item(
        self,
        client: AsyncClient,
        auth_headers: dict,
        existing_want_list_item: WantListItem,
    ):
        """GET single item by ID."""
        response = await client.get(
            f"/api/want-list/{existing_want_list_item.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == existing_want_list_item.id
        assert data["target_price"] == "10.00"
        assert data["priority"] == "medium"
        assert data["notes"] == "Test notes"
        assert "card" in data

    async def test_get_want_list_item_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """GET returns 404 for non-existent item."""
        response = await client.get(
            "/api/want-list/999999",
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    async def test_get_want_list_item_other_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        auth_headers: dict,
        test_card: Card,
    ):
        """GET returns 403 for item owned by another user."""
        # Create another user and their want list item
        other_user = User(
            email="other@example.com",
            username="otheruser",
            hashed_password="$2b$12$hash",
            is_active=True,
        )
        db_session.add(other_user)
        await db_session.flush()

        other_item = WantListItem(
            user_id=other_user.id,
            card_id=test_card.id,
            target_price=Decimal("50.00"),
        )
        db_session.add(other_item)
        await db_session.commit()
        await db_session.refresh(other_item)

        response = await client.get(
            f"/api/want-list/{other_item.id}",
            headers=auth_headers,
        )

        assert response.status_code == 403
        assert "Not authorized" in response.json()["detail"]


@pytest.mark.asyncio
class TestUpdateWantListItem:
    """Tests for PATCH /api/want-list/{item_id}"""

    async def test_update_want_list_item(
        self,
        client: AsyncClient,
        auth_headers: dict,
        existing_want_list_item: WantListItem,
    ):
        """PATCH updates fields."""
        response = await client.patch(
            f"/api/want-list/{existing_want_list_item.id}",
            headers=auth_headers,
            json={
                "target_price": 25.00,
                "priority": "high",
                "alert_enabled": False,
                "notes": "Updated notes",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["target_price"] == "25.00"
        assert data["priority"] == "high"
        assert data["alert_enabled"] is False
        assert data["notes"] == "Updated notes"

    async def test_update_want_list_item_partial(
        self,
        client: AsyncClient,
        auth_headers: dict,
        existing_want_list_item: WantListItem,
    ):
        """PATCH allows partial updates."""
        response = await client.patch(
            f"/api/want-list/{existing_want_list_item.id}",
            headers=auth_headers,
            json={
                "priority": "low",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Updated field
        assert data["priority"] == "low"
        # Unchanged fields
        assert data["target_price"] == "10.00"
        assert data["alert_enabled"] is True

    async def test_update_want_list_item_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """PATCH returns 404 for non-existent item."""
        response = await client.patch(
            "/api/want-list/999999",
            headers=auth_headers,
            json={"target_price": 50.00},
        )

        assert response.status_code == 404

    async def test_update_want_list_item_other_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        auth_headers: dict,
        test_card: Card,
    ):
        """PATCH returns 403 for item owned by another user."""
        other_user = User(
            email="other2@example.com",
            username="otheruser2",
            hashed_password="$2b$12$hash",
            is_active=True,
        )
        db_session.add(other_user)
        await db_session.flush()

        other_item = WantListItem(
            user_id=other_user.id,
            card_id=test_card.id,
            target_price=Decimal("50.00"),
        )
        db_session.add(other_item)
        await db_session.commit()
        await db_session.refresh(other_item)

        response = await client.patch(
            f"/api/want-list/{other_item.id}",
            headers=auth_headers,
            json={"target_price": 100.00},
        )

        assert response.status_code == 403


@pytest.mark.asyncio
class TestDeleteWantListItem:
    """Tests for DELETE /api/want-list/{item_id}"""

    async def test_delete_want_list_item(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        auth_headers: dict,
        existing_want_list_item: WantListItem,
    ):
        """DELETE returns 204."""
        item_id = existing_want_list_item.id

        response = await client.delete(
            f"/api/want-list/{item_id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verify item is actually deleted
        deleted_item = await db_session.get(WantListItem, item_id)
        assert deleted_item is None

    async def test_delete_want_list_item_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """DELETE returns 404 for non-existent item."""
        response = await client.delete(
            "/api/want-list/999999",
            headers=auth_headers,
        )

        assert response.status_code == 404

    async def test_delete_want_list_item_other_user(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        auth_headers: dict,
        test_card: Card,
    ):
        """DELETE returns 403 for item owned by another user."""
        other_user = User(
            email="other3@example.com",
            username="otheruser3",
            hashed_password="$2b$12$hash",
            is_active=True,
        )
        db_session.add(other_user)
        await db_session.flush()

        other_item = WantListItem(
            user_id=other_user.id,
            card_id=test_card.id,
            target_price=Decimal("50.00"),
        )
        db_session.add(other_item)
        await db_session.commit()
        await db_session.refresh(other_item)

        response = await client.delete(
            f"/api/want-list/{other_item.id}",
            headers=auth_headers,
        )

        assert response.status_code == 403


@pytest.mark.asyncio
class TestUnauthenticatedAccess:
    """Tests for unauthenticated requests."""

    async def test_list_without_auth(self, client: AsyncClient):
        """GET /api/want-list returns 401 without auth."""
        response = await client.get("/api/want-list")
        assert response.status_code == 401

    async def test_create_without_auth(self, client: AsyncClient):
        """POST /api/want-list returns 401 without auth."""
        response = await client.post(
            "/api/want-list",
            json={"card_id": 1, "target_price": 10.00},
        )
        assert response.status_code == 401

    async def test_get_item_without_auth(self, client: AsyncClient):
        """GET /api/want-list/{id} returns 401 without auth."""
        response = await client.get("/api/want-list/1")
        assert response.status_code == 401

    async def test_update_without_auth(self, client: AsyncClient):
        """PATCH /api/want-list/{id} returns 401 without auth."""
        response = await client.patch(
            "/api/want-list/1",
            json={"target_price": 20.00},
        )
        assert response.status_code == 401

    async def test_delete_without_auth(self, client: AsyncClient):
        """DELETE /api/want-list/{id} returns 401 without auth."""
        response = await client.delete("/api/want-list/1")
        assert response.status_code == 401
