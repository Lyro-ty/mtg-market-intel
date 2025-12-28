"""Tests for inventory valuation service."""
import pytest

from app.services.pricing.valuation import InventoryValuator, ConditionMultiplier


class TestConditionMultiplier:
    """Test condition-based price adjustments."""

    def test_near_mint_is_100_percent(self):
        assert ConditionMultiplier.get("NEAR_MINT") == 1.0

    def test_lightly_played_is_87_percent(self):
        assert ConditionMultiplier.get("LIGHTLY_PLAYED") == 0.87

    def test_moderately_played_is_72_percent(self):
        assert ConditionMultiplier.get("MODERATELY_PLAYED") == 0.72

    def test_heavily_played_is_55_percent(self):
        assert ConditionMultiplier.get("HEAVILY_PLAYED") == 0.55

    def test_damaged_is_35_percent(self):
        assert ConditionMultiplier.get("DAMAGED") == 0.35

    def test_unknown_condition_defaults_to_100_percent(self):
        assert ConditionMultiplier.get("UNKNOWN") == 1.0


class TestInventoryValuator:
    """Test inventory valuation calculations."""

    @pytest.fixture
    def valuator(self):
        return InventoryValuator()

    def test_calculate_item_value_applies_condition_multiplier(self, valuator):
        """LP card at $10 NM should value at $8.70."""
        result = valuator.calculate_item_value(
            base_price=10.00,
            condition="LIGHTLY_PLAYED",
            quantity=1,
            is_foil=False
        )
        assert result == pytest.approx(8.70, rel=0.01)

    def test_calculate_item_value_multiplies_by_quantity(self, valuator):
        """4 copies of $10 NM card = $40."""
        result = valuator.calculate_item_value(
            base_price=10.00,
            condition="NEAR_MINT",
            quantity=4,
            is_foil=False
        )
        assert result == pytest.approx(40.00, rel=0.01)

    def test_calculate_profit_loss(self, valuator):
        """Bought at $5, now worth $8 = $3 profit."""
        result = valuator.calculate_profit_loss(
            current_value=8.00,
            acquisition_price=5.00,
            quantity=1
        )
        assert result["profit_loss"] == pytest.approx(3.00, rel=0.01)
        assert result["profit_loss_pct"] == pytest.approx(60.0, rel=0.01)

    def test_calculate_profit_loss_handles_loss(self, valuator):
        """Bought at $10, now worth $6 = -$4 loss."""
        result = valuator.calculate_profit_loss(
            current_value=6.00,
            acquisition_price=10.00,
            quantity=1
        )
        assert result["profit_loss"] == pytest.approx(-4.00, rel=0.01)
        assert result["profit_loss_pct"] == pytest.approx(-40.0, rel=0.01)

    def test_calculate_portfolio_index(self, valuator):
        """Index = (current_value / acquisition_cost) * 100."""
        result = valuator.calculate_portfolio_index(
            total_current_value=650.00,
            total_acquisition_cost=500.00
        )
        assert result == pytest.approx(130.0, rel=0.01)

    def test_calculate_portfolio_index_handles_zero_cost(self, valuator):
        """Zero acquisition cost should return 100 (neutral)."""
        result = valuator.calculate_portfolio_index(
            total_current_value=100.00,
            total_acquisition_cost=0.00
        )
        assert result == 100.0
