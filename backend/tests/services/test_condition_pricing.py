"""Tests for condition pricing service."""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.pricing.condition_pricing import ConditionPricer


class TestConditionPricer:
    """Test condition-based pricing from TCGPlayer or multipliers."""

    @pytest.fixture
    def pricer(self):
        return ConditionPricer(tcgplayer_api_key="test-key")

    @pytest.fixture
    def pricer_no_key(self):
        return ConditionPricer(tcgplayer_api_key=None)

    def test_should_use_tcgplayer_for_expensive_cards(self, pricer):
        """Cards over $5 should use TCGPlayer API."""
        assert pricer.should_use_tcgplayer(nm_price=10.00) is True
        assert pricer.should_use_tcgplayer(nm_price=5.01) is True

    def test_should_use_multiplier_for_cheap_cards(self, pricer):
        """Cards $5 or under should use multipliers."""
        assert pricer.should_use_tcgplayer(nm_price=5.00) is False
        assert pricer.should_use_tcgplayer(nm_price=1.00) is False

    def test_should_use_multiplier_when_no_api_key(self, pricer_no_key):
        """Without API key, always use multipliers."""
        assert pricer_no_key.should_use_tcgplayer(nm_price=100.00) is False

    def test_calculate_condition_prices_with_multipliers(self, pricer):
        """Should calculate all condition prices from NM base."""
        prices = pricer.calculate_condition_prices_from_multipliers(nm_price=10.00)

        assert prices["NEAR_MINT"] == 10.00
        assert prices["LIGHTLY_PLAYED"] == pytest.approx(8.70, rel=0.01)
        assert prices["MODERATELY_PLAYED"] == pytest.approx(7.20, rel=0.01)
        assert prices["HEAVILY_PLAYED"] == pytest.approx(5.50, rel=0.01)
        assert prices["DAMAGED"] == pytest.approx(3.50, rel=0.01)

    @pytest.mark.asyncio
    async def test_get_tcgplayer_prices_returns_condition_map(self, pricer):
        """Should fetch and parse TCGPlayer condition prices."""
        mock_response = {
            "results": [
                {"subTypeName": "Near Mint", "marketPrice": 12.50},
                {"subTypeName": "Lightly Played", "marketPrice": 10.80},
                {"subTypeName": "Moderately Played", "marketPrice": 9.00},
            ]
        }

        with patch.object(pricer, "_fetch_tcgplayer_prices", return_value=mock_response):
            prices = await pricer.get_tcgplayer_prices(tcgplayer_product_id=12345)

        assert prices["NEAR_MINT"] == 12.50
        assert prices["LIGHTLY_PLAYED"] == 10.80
        assert prices["MODERATELY_PLAYED"] == 9.00

    @pytest.mark.asyncio
    async def test_get_prices_for_card_uses_multipliers_for_cheap(self, pricer):
        """Cheap cards should use multipliers even with API key."""
        prices = await pricer.get_prices_for_card(nm_price=3.00)

        assert prices["NEAR_MINT"] == 3.00
        assert prices["LIGHTLY_PLAYED"] == pytest.approx(2.61, rel=0.01)

    @pytest.mark.asyncio
    async def test_get_prices_for_card_falls_back_on_api_error(self, pricer):
        """Should fallback to multipliers if TCGPlayer API fails."""
        with patch.object(pricer, "_fetch_tcgplayer_prices", side_effect=Exception("API Error")):
            prices = await pricer.get_prices_for_card(
                nm_price=20.00,
                tcgplayer_product_id=12345
            )

        # Should get multiplier-based prices instead of failing
        assert prices["NEAR_MINT"] == 20.00
        assert prices["LIGHTLY_PLAYED"] == pytest.approx(17.40, rel=0.01)
