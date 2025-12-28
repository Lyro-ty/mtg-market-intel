"""
Tests for inventory top movers endpoint.

Tests the GET /api/v1/inventory/top-movers endpoint which uses direct
price_snapshot comparison to calculate gainers and losers.
"""
import pytest
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card
from app.models.inventory import InventoryItem
from app.models.user import User
from app.models.marketplace import Marketplace
from app.models.price_snapshot import PriceSnapshot


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4GQJfIK1R1MBfG.",  # 'password'
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_marketplace(db_session: AsyncSession) -> Marketplace:
    """Create a test marketplace."""
    marketplace = Marketplace(
        slug="tcgplayer",
        name="TCGPlayer",
        base_url="https://tcgplayer.com",
        is_enabled=True,
    )
    db_session.add(marketplace)
    await db_session.commit()
    await db_session.refresh(marketplace)
    return marketplace


@pytest.fixture
async def auth_headers(test_user: User, client: AsyncClient) -> dict:
    """Create auth headers with a mock current user."""
    from app.api.deps import get_current_user
    from app.main import app

    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield {}  # Use yield instead of return
    app.dependency_overrides.pop(get_current_user, None)  # Cleanup


@pytest.mark.asyncio
class TestTopMovers:
    """Test GET /api/v1/inventory/top-movers endpoint."""

    async def test_returns_empty_for_empty_inventory(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """Should return empty lists when user has no inventory."""
        response = await client.get(
            "/api/v1/inventory/top-movers?window=24h",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["gainers"] == []
        assert data["losers"] == []
        assert data["data_freshness_hours"] == 0

    async def test_returns_gainers_and_losers(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        auth_headers: dict,
        test_user: User,
        test_marketplace: Marketplace,
    ):
        """Should return cards with biggest price changes."""
        # Create test cards
        gainer_card = Card(
            scryfall_id="gainer-123",
            name="Gainer Card",
            set_code="TST",
            collector_number="1",
        )
        loser_card = Card(
            scryfall_id="loser-456",
            name="Loser Card",
            set_code="TST",
            collector_number="2",
        )
        db_session.add_all([gainer_card, loser_card])
        await db_session.flush()

        # Add to inventory
        inv1 = InventoryItem(
            user_id=test_user.id,
            card_id=gainer_card.id,
            quantity=1,
            condition="NEAR_MINT",
            is_foil=False,
        )
        inv2 = InventoryItem(
            user_id=test_user.id,
            card_id=loser_card.id,
            quantity=1,
            condition="NEAR_MINT",
            is_foil=False,
        )
        db_session.add_all([inv1, inv2])

        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)

        # Card 1: $10 -> $15 (50% gain)
        db_session.add(PriceSnapshot(
            card_id=gainer_card.id,
            marketplace_id=test_marketplace.id,
            time=yesterday,
            price=10.00,
            currency="USD",
            condition="NEAR_MINT",
            is_foil=False,
            language="English",
            source="bulk",
        ))
        db_session.add(PriceSnapshot(
            card_id=gainer_card.id,
            marketplace_id=test_marketplace.id,
            time=now,
            price=15.00,
            currency="USD",
            condition="NEAR_MINT",
            is_foil=False,
            language="English",
            source="bulk",
        ))

        # Card 2: $20 -> $12 (40% loss)
        db_session.add(PriceSnapshot(
            card_id=loser_card.id,
            marketplace_id=test_marketplace.id,
            time=yesterday,
            price=20.00,
            currency="USD",
            condition="NEAR_MINT",
            is_foil=False,
            language="English",
            source="bulk",
        ))
        db_session.add(PriceSnapshot(
            card_id=loser_card.id,
            marketplace_id=test_marketplace.id,
            time=now,
            price=12.00,
            currency="USD",
            condition="NEAR_MINT",
            is_foil=False,
            language="English",
            source="bulk",
        ))

        await db_session.commit()

        response = await client.get(
            "/api/v1/inventory/top-movers?window=24h",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["gainers"]) >= 1
        assert len(data["losers"]) >= 1
        assert data["gainers"][0]["card_name"] == "Gainer Card"
        assert data["losers"][0]["card_name"] == "Loser Card"
        assert data["gainers"][0]["change_pct"] == pytest.approx(50.0, rel=0.1)
        assert data["losers"][0]["change_pct"] == pytest.approx(-40.0, rel=0.1)
        assert "data_freshness_hours" in data

    async def test_respects_7d_window_parameter(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        auth_headers: dict,
        test_user: User,
        test_marketplace: Marketplace,
    ):
        """Should use 7-day window when specified."""
        # Create test card
        card = Card(
            scryfall_id="week-old-123",
            name="Week Old Card",
            set_code="TST",
            collector_number="3",
        )
        db_session.add(card)
        await db_session.flush()

        # Add to inventory
        inv = InventoryItem(
            user_id=test_user.id,
            card_id=card.id,
            quantity=1,
            condition="NEAR_MINT",
            is_foil=False,
        )
        db_session.add(inv)

        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)

        # Card: $10 -> $20 (100% gain over 7 days)
        db_session.add(PriceSnapshot(
            card_id=card.id,
            marketplace_id=test_marketplace.id,
            time=week_ago,
            price=10.00,
            currency="USD",
            condition="NEAR_MINT",
            is_foil=False,
            language="English",
            source="bulk",
        ))
        db_session.add(PriceSnapshot(
            card_id=card.id,
            marketplace_id=test_marketplace.id,
            time=now,
            price=20.00,
            currency="USD",
            condition="NEAR_MINT",
            is_foil=False,
            language="English",
            source="bulk",
        ))

        await db_session.commit()

        response = await client.get(
            "/api/v1/inventory/top-movers?window=7d",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["window"] == "7d"
        assert len(data["gainers"]) >= 1
        assert data["gainers"][0]["change_pct"] == pytest.approx(100.0, rel=0.1)

    async def test_returns_correct_response_format(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        auth_headers: dict,
        test_user: User,
        test_marketplace: Marketplace,
    ):
        """Should return the expected response format with all fields."""
        # Create test card
        card = Card(
            scryfall_id="format-test-123",
            name="Format Test Card",
            set_code="FMT",
            collector_number="99",
            image_url_small="https://example.com/image.jpg",
        )
        db_session.add(card)
        await db_session.flush()

        inv = InventoryItem(
            user_id=test_user.id,
            card_id=card.id,
            quantity=1,
            condition="NEAR_MINT",
            is_foil=False,
        )
        db_session.add(inv)

        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)

        db_session.add(PriceSnapshot(
            card_id=card.id,
            marketplace_id=test_marketplace.id,
            time=yesterday,
            price=5.00,
            currency="USD",
            condition="NEAR_MINT",
            is_foil=False,
            language="English",
            source="bulk",
        ))
        db_session.add(PriceSnapshot(
            card_id=card.id,
            marketplace_id=test_marketplace.id,
            time=now,
            price=7.50,
            currency="USD",
            condition="NEAR_MINT",
            is_foil=False,
            language="English",
            source="bulk",
        ))

        await db_session.commit()

        response = await client.get(
            "/api/v1/inventory/top-movers?window=24h",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "gainers" in data
        assert "losers" in data
        assert "data_freshness_hours" in data
        assert "window" in data

        # Check gainer structure
        gainer = data["gainers"][0]
        assert "card_id" in gainer
        assert "card_name" in gainer
        assert "set_code" in gainer
        assert "image_url" in gainer
        assert "old_price" in gainer
        assert "new_price" in gainer
        assert "change_pct" in gainer

        assert gainer["card_name"] == "Format Test Card"
        assert gainer["set_code"] == "FMT"
        assert gainer["old_price"] == 5.00
        assert gainer["new_price"] == 7.50
        assert gainer["change_pct"] == pytest.approx(50.0, rel=0.1)

    async def test_limits_to_top_5_each(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        auth_headers: dict,
        test_user: User,
        test_marketplace: Marketplace,
    ):
        """Should limit results to 5 gainers and 5 losers."""
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)

        # Create 10 gaining cards
        for i in range(10):
            card = Card(
                scryfall_id=f"gainer-{i}",
                name=f"Gainer {i}",
                set_code="TST",
                collector_number=str(i),
            )
            db_session.add(card)
            await db_session.flush()

            inv = InventoryItem(
                user_id=test_user.id,
                card_id=card.id,
                quantity=1,
                condition="NEAR_MINT",
                is_foil=False,
            )
            db_session.add(inv)

            # Each gains (i+1)*10%
            base_price = 10.0
            new_price = base_price * (1 + (i + 1) * 0.1)

            db_session.add(PriceSnapshot(
                card_id=card.id,
                marketplace_id=test_marketplace.id,
                time=yesterday,
                price=base_price,
                currency="USD",
                condition="NEAR_MINT",
                is_foil=False,
                language="English",
                source="bulk",
            ))
            db_session.add(PriceSnapshot(
                card_id=card.id,
                marketplace_id=test_marketplace.id,
                time=now,
                price=new_price,
                currency="USD",
                condition="NEAR_MINT",
                is_foil=False,
                language="English",
                source="bulk",
            ))

        await db_session.commit()

        response = await client.get(
            "/api/v1/inventory/top-movers?window=24h",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["gainers"]) == 5
        assert len(data["losers"]) == 0  # No losers in this test

    async def test_only_includes_users_inventory(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        auth_headers: dict,
        test_user: User,
        test_marketplace: Marketplace,
    ):
        """Should only include cards from the authenticated user's inventory."""
        # Create another user
        other_user = User(
            email="other@example.com",
            username="otheruser",
            hashed_password="$2b$12$hash",
            is_active=True,
        )
        db_session.add(other_user)
        await db_session.flush()

        # Create cards
        my_card = Card(
            scryfall_id="my-card-123",
            name="My Card",
            set_code="TST",
            collector_number="1",
        )
        other_card = Card(
            scryfall_id="other-card-456",
            name="Other Card",
            set_code="TST",
            collector_number="2",
        )
        db_session.add_all([my_card, other_card])
        await db_session.flush()

        # Add my_card to test_user's inventory
        inv1 = InventoryItem(
            user_id=test_user.id,
            card_id=my_card.id,
            quantity=1,
            condition="NEAR_MINT",
            is_foil=False,
        )
        # Add other_card to other_user's inventory
        inv2 = InventoryItem(
            user_id=other_user.id,
            card_id=other_card.id,
            quantity=1,
            condition="NEAR_MINT",
            is_foil=False,
        )
        db_session.add_all([inv1, inv2])

        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)

        # Both cards have price changes
        for card in [my_card, other_card]:
            db_session.add(PriceSnapshot(
                card_id=card.id,
                marketplace_id=test_marketplace.id,
                time=yesterday,
                price=10.00,
                currency="USD",
                condition="NEAR_MINT",
                is_foil=False,
                language="English",
                source="bulk",
            ))
            db_session.add(PriceSnapshot(
                card_id=card.id,
                marketplace_id=test_marketplace.id,
                time=now,
                price=15.00,
                currency="USD",
                condition="NEAR_MINT",
                is_foil=False,
                language="English",
                source="bulk",
            ))

        await db_session.commit()

        response = await client.get(
            "/api/v1/inventory/top-movers?window=24h",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Should only see our card
        assert len(data["gainers"]) == 1
        assert data["gainers"][0]["card_name"] == "My Card"
