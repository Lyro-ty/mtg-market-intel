"""
Buylist price schemas.
"""
from datetime import datetime
from pydantic import BaseModel


class BuylistPriceItem(BaseModel):
    """Single buylist price from a vendor."""
    vendor: str
    condition: str
    is_foil: bool
    price: float
    credit_price: float | None = None
    quantity: int | None = None
    time: datetime

    class Config:
        from_attributes = True


class CardBuylistResponse(BaseModel):
    """Buylist prices for a card."""
    card_id: int
    card_name: str
    prices: list[BuylistPriceItem]
    best_cash_price: float | None = None
    best_credit_price: float | None = None
    spread_vs_retail: float | None = None
    spread_pct: float | None = None
    last_updated: datetime | None = None


class BuylistRefreshResponse(BaseModel):
    """Response for on-demand buylist collection."""
    card_id: int
    card_name: str
    prices_found: int
    task_id: str | None = None
    status: str = "completed"
