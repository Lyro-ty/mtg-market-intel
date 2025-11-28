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
    response = await client.get("/cards/search?q=test")
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
    
    response = await client.get("/cards/search?q=Lightning")
    assert response.status_code == 200
    data = response.json()
    assert len(data["cards"]) == 1
    assert data["cards"][0]["name"] == "Lightning Bolt"


@pytest.mark.asyncio
async def test_get_card_not_found(client: AsyncClient):
    """Test getting non-existent card returns 404."""
    response = await client.get("/cards/999")
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
    
    response = await client.get(f"/cards/{card.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["card"]["name"] == "Black Lotus"
    assert data["card"]["set_code"] == "LEA"

