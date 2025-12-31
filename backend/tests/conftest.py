"""
Pytest configuration and fixtures.

Provides fixtures for:
- Database sessions with automatic cleanup
- HTTP client with mocked rate limiting
- Test users with auth headers
- Test cards and inventory items
- Phase-specific fixtures (have list, want list, trades, etc.)
"""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.db.base import Base
from app.db.session import get_db

# Use SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )

    async with engine.begin() as conn:
        # Drop all tables first to ensure clean state
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with rate limiting disabled."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Mock Redis to disable rate limiting during tests
    mock_redis = AsyncMock()
    mock_pipeline = AsyncMock()
    mock_pipeline.execute = AsyncMock(return_value=[1, True])  # Always under limit
    mock_redis.pipeline = lambda: mock_pipeline

    with patch("app.middleware.rate_limit.redis.from_url", return_value=mock_redis):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()


# Alias for db_session to match test expectations
@pytest_asyncio.fixture
async def db(db_session) -> AsyncSession:
    """Alias for db_session."""
    return db_session


# -----------------------------------------------------------------------------
# User Fixtures
# -----------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_user(db_session) -> "User":
    """Create a test user."""
    from app.models import User
    from app.services.auth import hash_password

    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_2(db_session) -> "User":
    """Create a second test user for trading scenarios."""
    from app.models import User
    from app.services.auth import hash_password

    user = User(
        email="test2@example.com",
        username="testuser2",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user) -> dict:
    """Get auth headers for test user."""
    from app.services.auth import create_access_token
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers_2(test_user_2) -> dict:
    """Get auth headers for second test user."""
    from app.services.auth import create_access_token
    token = create_access_token(test_user_2.id)
    return {"Authorization": f"Bearer {token}"}


# -----------------------------------------------------------------------------
# Card Fixtures
# -----------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_card(db_session) -> "Card":
    """Create a test card."""
    from app.models import Card

    card = Card(
        id=1,
        scryfall_id="e0debb18-f57c-4b9c-9734-aef0dab42f6c",  # Required field
        name="Lightning Bolt",
        set_code="LEA",
        set_name="Limited Edition Alpha",
        collector_number="161",
        rarity="common",
        mana_cost="{R}",
        type_line="Instant",
        oracle_text="Lightning Bolt deals 3 damage to any target.",
        image_url="https://cards.scryfall.io/normal/front/example.jpg",
    )
    db_session.add(card)
    await db_session.commit()
    await db_session.refresh(card)
    return card


@pytest_asyncio.fixture
async def test_card_2(db_session) -> "Card":
    """Create a second test card."""
    from app.models import Card

    card = Card(
        id=2,
        scryfall_id="93f9e4e4-a7e8-4c7c-a3c5-123456789abc",  # Required field
        name="Counterspell",
        set_code="LEA",
        set_name="Limited Edition Alpha",
        collector_number="54",
        rarity="uncommon",
        mana_cost="{U}{U}",
        type_line="Instant",
        oracle_text="Counter target spell.",
        image_url="https://cards.scryfall.io/normal/front/example2.jpg",
    )
    db_session.add(card)
    await db_session.commit()
    await db_session.refresh(card)
    return card


# -----------------------------------------------------------------------------
# Inventory Fixtures
# -----------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_inventory_item(db_session, test_user, test_card) -> dict:
    """Create a test inventory item."""
    from app.models import InventoryItem

    item = InventoryItem(
        user_id=test_user.id,
        card_id=test_card.id,
        quantity=4,
        condition="NEAR_MINT",
        is_foil=False,
        acquisition_price=Decimal("5.00"),
        acquisition_date=datetime.now(timezone.utc),
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return {
        "id": item.id,
        "user_id": item.user_id,
        "card_id": item.card_id,
        "quantity": item.quantity,
        "condition": item.condition,
    }


# -----------------------------------------------------------------------------
# Want List Fixtures
# -----------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_want_list_item(db_session, test_user, test_card_2) -> dict:
    """Create a test want list item."""
    from app.models import WantListItem

    item = WantListItem(
        user_id=test_user.id,
        card_id=test_card_2.id,
        target_price=Decimal("3.00"),
        priority="high",
        alert_enabled=True,
        is_active=True,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return {
        "id": item.id,
        "user_id": item.user_id,
        "card_id": item.card_id,
    }

