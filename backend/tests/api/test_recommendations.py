"""
Tests for recommendation API endpoints.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, Recommendation


@pytest.mark.asyncio
async def test_get_recommendations_empty(client: AsyncClient):
    """Test getting recommendations when none exist."""
    response = await client.get("/recommendations")
    assert response.status_code == 200
    data = response.json()
    assert data["recommendations"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_recommendations_with_filter(client: AsyncClient, db_session: AsyncSession):
    """Test filtering recommendations by action."""
    # Create test card
    card = Card(
        scryfall_id="test-rec-1",
        name="Test Card",
        set_code="TST",
        collector_number="1",
    )
    db_session.add(card)
    await db_session.flush()
    
    # Create recommendations
    rec_buy = Recommendation(
        card_id=card.id,
        action="BUY",
        confidence=0.8,
        rationale="Test buy rationale",
    )
    rec_sell = Recommendation(
        card_id=card.id,
        action="SELL",
        confidence=0.7,
        rationale="Test sell rationale",
    )
    db_session.add_all([rec_buy, rec_sell])
    await db_session.commit()
    
    # Test filter by BUY
    response = await client.get("/recommendations?action=BUY")
    assert response.status_code == 200
    data = response.json()
    assert len(data["recommendations"]) == 1
    assert data["recommendations"][0]["action"] == "BUY"


@pytest.mark.asyncio
async def test_get_recommendation_not_found(client: AsyncClient):
    """Test getting non-existent recommendation returns 404."""
    response = await client.get("/recommendations/999")
    assert response.status_code == 404

