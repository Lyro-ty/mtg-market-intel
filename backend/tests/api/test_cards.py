"""
Tests for card API endpoints.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card


@pytest.mark.asyncio
async def test_search_cards_empty(client: AsyncClient):
    """Test card search with no cards returns empty list."""
    response = await client.get("/api/cards/search?q=test")
    assert response.status_code == 200
    data = response.json()
    assert data["cards"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_search_cards_with_results(client: AsyncClient, db_session: AsyncSession):
    """Test card search returns matching cards."""
    # Create test card
    card = Card(
        scryfall_id="test-id-1",
        name="Lightning Bolt",
        set_code="M21",
        collector_number="1",
        rarity="common",
    )
    db_session.add(card)
    await db_session.commit()
    
    response = await client.get("/api/cards/search?q=Lightning")
    assert response.status_code == 200
    data = response.json()
    assert len(data["cards"]) == 1
    assert data["cards"][0]["name"] == "Lightning Bolt"


@pytest.mark.asyncio
async def test_get_card_not_found(client: AsyncClient):
    """Test getting non-existent card returns 404."""
    response = await client.get("/api/cards/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_card_detail(client: AsyncClient, db_session: AsyncSession):
    """Test getting card detail returns full info."""
    card = Card(
        scryfall_id="test-id-2",
        name="Black Lotus",
        set_code="LEA",
        collector_number="232",
        rarity="rare",
        mana_cost="{0}",
        type_line="Artifact",
    )
    db_session.add(card)
    await db_session.commit()
    await db_session.refresh(card)

    response = await client.get(f"/api/cards/{card.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["card"]["name"] == "Black Lotus"
    assert data["card"]["set_code"] == "LEA"


# ============================================================================
# Cursor-based pagination tests
# ============================================================================


@pytest.mark.asyncio
async def test_search_cards_cursor_empty(client: AsyncClient):
    """Test cursor search with no cards returns empty list."""
    response = await client.get("/api/cards/search/cursor?q=nonexistent")
    assert response.status_code == 200
    data = response.json()
    assert data["cards"] == []
    assert data["has_more"] is False
    assert data["next_cursor"] is None


@pytest.mark.asyncio
async def test_search_cards_cursor_with_results(client: AsyncClient, db_session: AsyncSession):
    """Test cursor search returns matching cards."""
    card = Card(
        scryfall_id="test-cursor-1",
        name="Lightning Bolt",
        set_code="M21",
        collector_number="150",
        rarity="common",
    )
    db_session.add(card)
    await db_session.commit()

    response = await client.get("/api/cards/search/cursor?q=Lightning")
    assert response.status_code == 200
    data = response.json()
    assert len(data["cards"]) == 1
    assert data["cards"][0]["name"] == "Lightning Bolt"
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_search_cards_cursor_pagination(client: AsyncClient, db_session: AsyncSession):
    """Test cursor pagination returns correct pages."""
    # Create multiple cards
    cards = [
        Card(
            scryfall_id=f"test-cursor-page-{i}",
            name=f"Bolt Card {i:02d}",
            set_code="TST",
            collector_number=str(i),
            rarity="common",
        )
        for i in range(5)
    ]
    for card in cards:
        db_session.add(card)
    await db_session.commit()

    # First page with limit of 2
    response = await client.get("/api/cards/search/cursor?q=Bolt&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["cards"]) == 2
    assert data["has_more"] is True
    assert data["next_cursor"] is not None
    first_page_names = [c["name"] for c in data["cards"]]

    # Second page using cursor
    cursor = data["next_cursor"]
    response = await client.get(f"/api/cards/search/cursor?q=Bolt&limit=2&cursor={cursor}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["cards"]) == 2
    assert data["has_more"] is True
    second_page_names = [c["name"] for c in data["cards"]]

    # Verify no overlap between pages
    assert set(first_page_names).isdisjoint(set(second_page_names))

    # Third page (last page)
    cursor = data["next_cursor"]
    response = await client.get(f"/api/cards/search/cursor?q=Bolt&limit=2&cursor={cursor}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["cards"]) == 1  # Only 1 remaining
    assert data["has_more"] is False
    assert data["next_cursor"] is None


@pytest.mark.asyncio
async def test_search_cards_cursor_with_count(client: AsyncClient, db_session: AsyncSession):
    """Test cursor search with include_count returns total count."""
    cards = [
        Card(
            scryfall_id=f"test-count-{i}",
            name=f"Countable Card {i}",
            set_code="CNT",
            collector_number=str(i),
            rarity="common",
        )
        for i in range(3)
    ]
    for card in cards:
        db_session.add(card)
    await db_session.commit()

    # Without count
    response = await client.get("/api/cards/search/cursor?q=Countable")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] is None

    # With count
    response = await client.get("/api/cards/search/cursor?q=Countable&include_count=true")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 3


@pytest.mark.asyncio
async def test_search_cards_cursor_with_set_filter(client: AsyncClient, db_session: AsyncSession):
    """Test cursor search with set code filter."""
    cards = [
        Card(
            scryfall_id="test-set-1",
            name="Test Card Alpha",
            set_code="AAA",
            collector_number="1",
            rarity="common",
        ),
        Card(
            scryfall_id="test-set-2",
            name="Test Card Beta",
            set_code="BBB",
            collector_number="1",
            rarity="common",
        ),
    ]
    for card in cards:
        db_session.add(card)
    await db_session.commit()

    # Filter by set code
    response = await client.get("/api/cards/search/cursor?q=Test&set_code=AAA")
    assert response.status_code == 200
    data = response.json()
    assert len(data["cards"]) == 1
    assert data["cards"][0]["set_code"] == "AAA"

