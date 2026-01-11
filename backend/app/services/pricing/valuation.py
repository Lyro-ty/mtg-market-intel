"""Inventory valuation service."""


class ConditionMultiplier:
    """TCGPlayer-standard condition price multipliers."""

    MULTIPLIERS = {
        "MINT": 1.0,
        "NEAR_MINT": 1.0,
        "LIGHTLY_PLAYED": 0.87,
        "MODERATELY_PLAYED": 0.72,
        "HEAVILY_PLAYED": 0.55,
        "DAMAGED": 0.35,
    }

    @classmethod
    def get(cls, condition: str) -> float:
        """Get multiplier for condition, defaulting to 1.0."""
        return cls.MULTIPLIERS.get(condition.upper(), 1.0)


class InventoryValuator:
    """Calculate inventory item and portfolio valuations."""

    def calculate_item_value(
        self,
        base_price: float,
        condition: str,
        quantity: int,
        is_foil: bool = False,
    ) -> float:
        """
        Calculate the current value of an inventory item.

        Args:
            base_price: NM price (foil or non-foil as appropriate)
            condition: Card condition (NEAR_MINT, LIGHTLY_PLAYED, etc.)
            quantity: Number of copies
            is_foil: Whether this is a foil (base_price should already be foil price)

        Returns:
            Total current value for this item
        """
        multiplier = ConditionMultiplier.get(condition)
        per_card_value = base_price * multiplier
        return per_card_value * quantity

    def calculate_profit_loss(
        self,
        current_value: float,
        acquisition_price: float,
        quantity: int,
    ) -> dict:
        """
        Calculate profit/loss for an inventory item.

        Returns:
            Dict with profit_loss (absolute) and profit_loss_pct
        """
        if acquisition_price <= 0:
            return {"profit_loss": 0.0, "profit_loss_pct": 0.0}

        total_acquisition = acquisition_price * quantity
        profit_loss = current_value - total_acquisition
        profit_loss_pct = (profit_loss / total_acquisition) * 100

        return {
            "profit_loss": profit_loss,
            "profit_loss_pct": profit_loss_pct,
        }

    @classmethod
    def calculate_portfolio_index(
        cls,
        total_current_value: float,
        total_acquisition_cost: float,
    ) -> float:
        """
        Calculate portfolio value index.

        Index = (current_value / acquisition_cost) * 100

        Returns:
            Index value where 100 = break even, >100 = profit, <100 = loss
        """
        if total_acquisition_cost <= 0:
            return 100.0

        return (total_current_value / total_acquisition_cost) * 100
