"""
Tests for N+1 query prevention via eager loading.

These tests verify that list endpoints execute a constant number of queries
regardless of the number of items returned, preventing N+1 query problems.
"""
from decimal import Decimal
from typing import List
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, User, WantListItem, InventoryItem, Recommendation, Marketplace


class QueryCounter:
    """
    Tracks SQL queries executed during a code block.

    Usage:
        async with QueryCounter(engine) as counter:
            # execute queries
        assert counter.count <= 3
    """

    def __init__(self, engine):
        self.engine = engine
        self.queries: List[str] = []
        self._sync_engine = None

    async def __aenter__(self):
        # Get the sync engine from async engine
        self._sync_engine = self.engine.sync_engine
        event.listen(self._sync_engine, "before_cursor_execute", self._on_query)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        event.remove(self._sync_engine, "before_cursor_execute", self._on_query)

    def _on_query(self, conn, cursor, statement, parameters, context, executemany):
        # Filter out internal SQLAlchemy queries and commits
        if not statement.strip().upper().startswith(("BEGIN", "COMMIT", "ROLLBACK", "RELEASE")):
            self.queries.append(statement)

    @property
    def count(self) -> int:
        return len(self.queries)

    def print_queries(self):
        """Print all captured queries for debugging."""
        for i, q in enumerate(self.queries, 1):
            print(f"{i}. {q[:200]}...")


# -----------------------------------------------------------------------------
# Test Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
async def test_user_for_perf(db_session: AsyncSession) -> User:
    """Create a test user for performance tests."""
    user = User(
        email="perf-test@example.com",
        username="perfuser",
        hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4GQJfIK1R1MBfG.",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_cards_for_perf(db_session: AsyncSession) -> List[Card]:
    """Create multiple test cards for N+1 testing."""
    cards = []
    for i in range(10):
        card = Card(
            scryfall_id=f"perf-test-card-{i:03d}",
            name=f"Performance Test Card {i}",
            set_code="TST",
            collector_number=str(200 + i),
            rarity="rare",
            image_url=f"https://cards.scryfall.io/normal/front/test{i}.jpg",
            image_url_small=f"https://cards.scryfall.io/small/front/test{i}.jpg",
        )
        db_session.add(card)
        cards.append(card)
    await db_session.commit()
    for card in cards:
        await db_session.refresh(card)
    return cards


@pytest.fixture
async def test_marketplace_for_perf(db_session: AsyncSession) -> Marketplace:
    """Create a test marketplace for recommendations."""
    marketplace = Marketplace(
        name="Test Marketplace",
        slug="test-marketplace",
        base_url="https://test.example.com",
        is_enabled=True,
    )
    db_session.add(marketplace)
    await db_session.commit()
    await db_session.refresh(marketplace)
    return marketplace


@pytest.fixture
async def inventory_items_for_perf(
    db_session: AsyncSession,
    test_user_for_perf: User,
    test_cards_for_perf: List[Card],
) -> List[InventoryItem]:
    """Create multiple inventory items for N+1 testing."""
    items = []
    for i, card in enumerate(test_cards_for_perf):
        item = InventoryItem(
            user_id=test_user_for_perf.id,
            card_id=card.id,
            quantity=i + 1,
            condition="NEAR_MINT",
            is_foil=(i % 2 == 0),
            acquisition_price=Decimal(f"{10 + i}.00"),
            current_value=Decimal(f"{12 + i}.50"),
        )
        db_session.add(item)
        items.append(item)
    await db_session.commit()
    for item in items:
        await db_session.refresh(item)
    return items


@pytest.fixture
async def want_list_items_for_perf(
    db_session: AsyncSession,
    test_user_for_perf: User,
    test_cards_for_perf: List[Card],
) -> List[WantListItem]:
    """Create multiple want list items for N+1 testing."""
    items = []
    for i, card in enumerate(test_cards_for_perf):
        item = WantListItem(
            user_id=test_user_for_perf.id,
            card_id=card.id,
            target_price=Decimal(f"{5 + i}.00"),
            priority=["high", "medium", "low"][i % 3],
            alert_enabled=True,
        )
        db_session.add(item)
        items.append(item)
    await db_session.commit()
    for item in items:
        await db_session.refresh(item)
    return items


@pytest.fixture
async def recommendations_for_perf(
    db_session: AsyncSession,
    test_cards_for_perf: List[Card],
    test_marketplace_for_perf: Marketplace,
) -> List[Recommendation]:
    """Create multiple recommendations for N+1 testing."""
    items = []
    for i, card in enumerate(test_cards_for_perf):
        rec = Recommendation(
            card_id=card.id,
            marketplace_id=test_marketplace_for_perf.id if i % 2 == 0 else None,
            action=["BUY", "SELL", "HOLD"][i % 3],
            confidence=Decimal("0.85"),
            horizon_days=7,
            current_price=Decimal(f"{10 + i}.00"),
            target_price=Decimal(f"{15 + i}.00"),
            rationale=f"Test rationale for card {i}",
            is_active=True,
        )
        db_session.add(rec)
        items.append(rec)
    await db_session.commit()
    for item in items:
        await db_session.refresh(item)
    return items


@pytest.fixture
async def auth_headers_for_perf(test_user_for_perf: User, client: AsyncClient) -> dict:
    """Create auth headers by overriding the get_current_user dependency."""
    from app.api.deps import get_current_user
    from app.main import app

    async def override_get_current_user():
        return test_user_for_perf

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield {}
    app.dependency_overrides.pop(get_current_user, None)


# -----------------------------------------------------------------------------
# N+1 Query Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
class TestInventoryQueryCount:
    """Tests to verify inventory endpoints don't have N+1 queries."""

    async def test_inventory_list_no_n_plus_one(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_engine,
        auth_headers_for_perf: dict,
        inventory_items_for_perf: List[InventoryItem],
    ):
        """
        GET /api/inventory should execute at most 3 queries regardless of item count.

        Expected queries:
        1. Count query for pagination
        2. Stats aggregation query
        3. Main items query (with eager loaded cards)
        """
        async with QueryCounter(test_engine) as counter:
            response = await client.get(
                "/api/inventory",
                headers=auth_headers_for_perf,
            )

        assert response.status_code == 200
        data = response.json()

        # Verify we got all items
        assert len(data["items"]) == 10

        # Verify each item has card data (no lazy loading)
        for item in data["items"]:
            assert "card_name" in item
            assert "card_set" in item
            assert item["card_name"] is not None

        # Check query count - should be at most 3 queries
        # Allow some flexibility for transaction management
        if counter.count > 3:
            counter.print_queries()
        assert counter.count <= 3, f"Expected max 3 queries, got {counter.count}"


@pytest.mark.asyncio
class TestWantListQueryCount:
    """Tests to verify want list endpoints don't have N+1 queries."""

    async def test_want_list_no_n_plus_one(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_engine,
        auth_headers_for_perf: dict,
        want_list_items_for_perf: List[WantListItem],
    ):
        """
        GET /api/want-list should execute at most 4 queries regardless of item count.

        Expected queries:
        1. Count query for pagination
        2. Main items query
        3. Cards query (selectinload)
        4. Batched price lookups (single query)
        """
        async with QueryCounter(test_engine) as counter:
            response = await client.get(
                "/api/want-list",
                headers=auth_headers_for_perf,
            )

        assert response.status_code == 200
        data = response.json()

        # Verify we got all items
        assert len(data["items"]) == 10

        # Verify each item has card data (no lazy loading)
        for item in data["items"]:
            assert "card" in item
            assert item["card"]["name"] is not None

        # Check query count
        # With selectinload for cards and batched price lookups:
        # 1. Count query for pagination
        # 2. Main items query
        # 3. Cards via selectinload (separate batch query)
        # 4. Batched price lookups (single query)
        if counter.count > 4:
            counter.print_queries()
        assert counter.count <= 4, f"Expected max 4 queries, got {counter.count}"


@pytest.mark.asyncio
class TestRecommendationsQueryCount:
    """Tests to verify recommendations endpoints don't have N+1 queries."""

    async def test_recommendations_list_no_n_plus_one(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_engine,
        recommendations_for_perf: List[Recommendation],
    ):
        """
        GET /api/recommendations should execute at most 5 queries regardless of item count.

        Expected queries:
        1. Count query for pagination
        2. Buy count query
        3. Sell count query
        4. Hold count query
        5. Main items query (with eager loaded cards and marketplaces)
        """
        async with QueryCounter(test_engine) as counter:
            response = await client.get(
                "/api/recommendations",
            )

        assert response.status_code == 200
        data = response.json()

        # Verify we got all items
        assert len(data["recommendations"]) == 10

        # Verify each recommendation has card and marketplace data
        for rec in data["recommendations"]:
            assert "card_name" in rec
            assert "card_set" in rec
            assert rec["card_name"] is not None

        # Check query count - should be at most 5 queries
        if counter.count > 5:
            counter.print_queries()
        assert counter.count <= 5, f"Expected max 5 queries, got {counter.count}"
