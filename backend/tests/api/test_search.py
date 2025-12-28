"""Tests for search API endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card


class TestSearchAPI:
    """Test search API endpoints."""

    @pytest.mark.asyncio
    async def test_search_endpoint(self, client: AsyncClient):
        """Test main search endpoint."""
        response = await client.get("/api/search?q=lightning")

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data
        assert "query" in data
        assert data["query"] == "lightning"

    @pytest.mark.asyncio
    async def test_search_endpoint_requires_query(self, client: AsyncClient):
        """Test search endpoint requires query parameter."""
        response = await client.get("/api/search")

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_search_with_mode_text(self, client: AsyncClient, db_session: AsyncSession):
        """Test text mode search returns matching cards."""
        # Create test card
        card = Card(
            scryfall_id="test-search-1",
            name="Lightning Bolt",
            set_code="M21",
            collector_number="1",
            rarity="common",
            type_line="Instant",
            oracle_text="Lightning Bolt deals 3 damage to any target.",
        )
        db_session.add(card)
        await db_session.commit()

        response = await client.get("/api/search?q=Lightning&mode=text")
        assert response.status_code == 200
        data = response.json()
        assert data["search_type"] == "text"
        assert len(data["results"]) == 1
        assert data["results"][0]["name"] == "Lightning Bolt"

    @pytest.mark.asyncio
    async def test_search_pagination(self, client: AsyncClient, db_session: AsyncSession):
        """Test search pagination parameters."""
        # Create multiple test cards
        for i in range(5):
            card = Card(
                scryfall_id=f"test-page-{i}",
                name=f"Test Card {i}",
                set_code="TST",
                collector_number=str(i),
            )
            db_session.add(card)
        await db_session.commit()

        response = await client.get("/api/search?q=Test&mode=text&page=1&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["results"]) == 2
        assert data["has_more"] is True


class TestAutocompleteAPI:
    """Test autocomplete API endpoints."""

    @pytest.mark.asyncio
    async def test_autocomplete_endpoint(self, client: AsyncClient):
        """Test autocomplete endpoint."""
        response = await client.get("/api/search/autocomplete?q=light")

        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert "query" in data
        assert data["query"] == "light"

    @pytest.mark.asyncio
    async def test_autocomplete_requires_query(self, client: AsyncClient):
        """Test autocomplete requires query parameter."""
        response = await client.get("/api/search/autocomplete")

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_autocomplete_returns_suggestions(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test autocomplete returns matching suggestions."""
        # Create test cards
        card1 = Card(
            scryfall_id="auto-1",
            name="Lightning Bolt",
            set_code="M21",
            collector_number="1",
        )
        card2 = Card(
            scryfall_id="auto-2",
            name="Lightning Strike",
            set_code="M21",
            collector_number="2",
        )
        card3 = Card(
            scryfall_id="auto-3",
            name="Counterspell",
            set_code="M21",
            collector_number="3",
        )
        db_session.add_all([card1, card2, card3])
        await db_session.commit()

        response = await client.get("/api/search/autocomplete?q=Light")
        assert response.status_code == 200
        data = response.json()
        assert len(data["suggestions"]) == 2
        names = [s["name"] for s in data["suggestions"]]
        assert "Lightning Bolt" in names
        assert "Lightning Strike" in names
        assert "Counterspell" not in names

    @pytest.mark.asyncio
    async def test_autocomplete_limit(self, client: AsyncClient, db_session: AsyncSession):
        """Test autocomplete respects limit parameter."""
        # Create many test cards
        for i in range(10):
            card = Card(
                scryfall_id=f"limit-{i}",
                name=f"Test Card {i}",
                set_code="TST",
                collector_number=str(i),
            )
            db_session.add(card)
        await db_session.commit()

        response = await client.get("/api/search/autocomplete?q=Test&limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data["suggestions"]) == 3


class TestSimilarCardsAPI:
    """Test similar cards API endpoints."""

    @pytest.mark.asyncio
    async def test_similar_cards_not_found(self, client: AsyncClient):
        """Test similar cards returns 404 for non-existent card."""
        response = await client.get("/api/search/similar/99999")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_similar_cards_endpoint(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test similar cards endpoint returns expected structure."""
        # Create a test card
        card = Card(
            scryfall_id="similar-1",
            name="Lightning Bolt",
            set_code="M21",
            collector_number="1",
            type_line="Instant",
            oracle_text="Lightning Bolt deals 3 damage to any target.",
        )
        db_session.add(card)
        await db_session.commit()
        await db_session.refresh(card)

        response = await client.get(f"/api/search/similar/{card.id}")

        assert response.status_code == 200
        data = response.json()
        assert "card_id" in data
        assert "card_name" in data
        assert "similar_cards" in data
        assert data["card_id"] == card.id
        assert data["card_name"] == "Lightning Bolt"
