"""
Tests for ingestion service.
"""
import pytest

from app.services.ingestion.adapters.mock import MockMarketplaceAdapter
from app.services.ingestion import get_adapter, get_available_adapters


def test_get_available_adapters():
    """Test getting list of available adapters."""
    adapters = get_available_adapters()
    
    assert "scryfall" in adapters
    assert "tcgplayer" in adapters
    assert "cardmarket" in adapters
    assert "mock" in adapters


def test_get_mock_adapter():
    """Test getting mock adapter."""
    adapter = get_adapter("mock")
    
    assert isinstance(adapter, MockMarketplaceAdapter)
    assert adapter.marketplace_slug == "mock_market"


@pytest.mark.asyncio
async def test_mock_adapter_fetch_price():
    """Test mock adapter fetches price data."""
    adapter = MockMarketplaceAdapter()
    
    price = await adapter.fetch_price(
        card_name="Lightning Bolt",
        set_code="M21",
    )
    
    assert price is not None
    assert price.price > 0
    assert price.card_name == "Lightning Bolt"


@pytest.mark.asyncio
async def test_mock_adapter_fetch_listings():
    """Test mock adapter fetches listings."""
    adapter = MockMarketplaceAdapter()
    
    listings = await adapter.fetch_listings(
        card_name="Lightning Bolt",
        set_code="M21",
    )
    
    assert len(listings) > 0
    assert all(l.price > 0 for l in listings)
    assert all(l.card_name == "Lightning Bolt" for l in listings)


@pytest.mark.asyncio
async def test_mock_adapter_price_history():
    """Test mock adapter generates price history."""
    adapter = MockMarketplaceAdapter()
    
    history = await adapter.fetch_price_history(
        card_name="Lightning Bolt",
        set_code="M21",
        days=7,
    )
    
    assert len(history) == 7
    assert all(h.price > 0 for h in history)


@pytest.mark.asyncio
async def test_mock_adapter_search():
    """Test mock adapter search."""
    adapter = MockMarketplaceAdapter()
    
    results = await adapter.search_cards("Dragon", limit=5)
    
    assert len(results) <= 5
    assert all("Dragon" in r["name"] for r in results)

