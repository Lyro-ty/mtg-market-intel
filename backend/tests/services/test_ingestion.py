"""
Tests for ingestion service.
"""
import pytest

from app.services.ingestion import get_adapter, get_available_adapters
from app.services.ingestion.scryfall import ScryfallAdapter


def test_get_available_adapters():
    """Test getting list of available adapters."""
    adapters = get_available_adapters()

    # These adapters should be available in the current registry
    assert "scryfall" in adapters
    assert "tcgplayer" in adapters
    assert "cardtrader" in adapters
    assert "mtgjson" in adapters
    assert "manapool" in adapters
    assert len(adapters) == 5


def test_get_scryfall_adapter():
    """Test getting Scryfall adapter."""
    adapter = get_adapter("scryfall")

    assert isinstance(adapter, ScryfallAdapter)
    assert adapter.marketplace_slug == "scryfall"


def test_get_unknown_adapter():
    """Test that getting unknown adapter raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        get_adapter("nonexistent")

    assert "Unknown adapter: nonexistent" in str(exc_info.value)

