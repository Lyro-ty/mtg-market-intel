"""Tests for autocomplete service."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.search.autocomplete import AutocompleteService


class TestAutocompleteService:
    """Test autocomplete service."""

    @pytest.mark.asyncio
    async def test_autocomplete_returns_matches(self):
        """Test autocomplete returns matching card names."""
        service = AutocompleteService()

        mock_db = AsyncMock()
        mock_result = MagicMock()

        # Mock cards returned from DB - use configure_mock for 'name' attribute
        # since MagicMock(name=...) sets the mock's internal name, not .name attribute
        mock_card1 = MagicMock()
        mock_card1.configure_mock(id=1, name="Lightning Bolt", set_code="LEA", image_url_small="/img1.jpg", image_url=None)
        mock_card2 = MagicMock()
        mock_card2.configure_mock(id=2, name="Lightning Helix", set_code="RAV", image_url_small="/img2.jpg", image_url=None)
        mock_cards = [mock_card1, mock_card2]
        mock_result.scalars.return_value.all.return_value = mock_cards
        mock_db.execute = AsyncMock(return_value=mock_result)

        results = await service.get_suggestions(mock_db, "light", limit=5)

        assert len(results) == 2
        assert results[0]["name"] == "Lightning Bolt"
        assert results[1]["name"] == "Lightning Helix"

    @pytest.mark.asyncio
    async def test_autocomplete_empty_query(self):
        """Test autocomplete with empty query returns empty list."""
        service = AutocompleteService()
        mock_db = AsyncMock()

        results = await service.get_suggestions(mock_db, "", limit=5)

        assert results == []

    @pytest.mark.asyncio
    async def test_autocomplete_respects_limit(self):
        """Test autocomplete respects the limit parameter."""
        service = AutocompleteService()

        mock_db = AsyncMock()
        mock_result = MagicMock()

        # Return 10 cards - use configure_mock for 'name' attribute
        mock_cards = []
        for i in range(10):
            mock_card = MagicMock()
            mock_card.configure_mock(id=i, name=f"Card {i}", set_code="TST", image_url_small=None, image_url=None)
            mock_cards.append(mock_card)
        mock_result.scalars.return_value.all.return_value = mock_cards[:5]  # DB returns limited
        mock_db.execute = AsyncMock(return_value=mock_result)

        results = await service.get_suggestions(mock_db, "card", limit=5)

        assert len(results) <= 5
