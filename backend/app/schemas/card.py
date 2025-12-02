"""
Card-related Pydantic schemas.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CardBase(BaseModel):
    """Base card schema with common fields."""
    name: str
    set_code: str
    collector_number: str
    rarity: Optional[str] = None
    mana_cost: Optional[str] = None
    type_line: Optional[str] = None
    
    class Config:
        from_attributes = True


class CardCreate(CardBase):
    """Schema for creating a card."""
    scryfall_id: str
    oracle_id: Optional[str] = None
    set_name: Optional[str] = None
    cmc: Optional[float] = None
    oracle_text: Optional[str] = None
    colors: Optional[str] = None
    color_identity: Optional[str] = None
    power: Optional[str] = None
    toughness: Optional[str] = None
    legalities: Optional[str] = None
    image_url: Optional[str] = None
    image_url_small: Optional[str] = None
    image_url_large: Optional[str] = None


class CardResponse(CardBase):
    """Card response schema."""
    id: int
    scryfall_id: str
    oracle_id: Optional[str] = None
    set_name: Optional[str] = None
    cmc: Optional[float] = None
    oracle_text: Optional[str] = None
    power: Optional[str] = None
    toughness: Optional[str] = None
    image_url: Optional[str] = None
    image_url_small: Optional[str] = None
    
    class Config:
        from_attributes = True


class CardSearchResponse(BaseModel):
    """Card search results schema."""
    cards: list[CardResponse]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False


class PricePoint(BaseModel):
    """Single price data point."""
    date: datetime
    price: float
    marketplace: str
    currency: str = "USD"
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    num_listings: Optional[int] = None
    snapshot_time: Optional[datetime] = None  # When this price was collected
    data_age_minutes: Optional[int] = None  # Minutes since collection


class CardPriceResponse(BaseModel):
    """Current prices across marketplaces."""
    card_id: int
    card_name: str
    prices: list["MarketplacePriceDetail"]
    lowest_price: Optional[float] = None
    highest_price: Optional[float] = None
    spread_pct: Optional[float] = None
    updated_at: datetime


class MarketplacePriceDetail(BaseModel):
    """Price details for a single marketplace."""
    marketplace_id: int
    marketplace_name: str
    marketplace_slug: str
    price: float
    currency: str = "USD"
    price_foil: Optional[float] = None
    num_listings: Optional[int] = None
    last_updated: datetime


class CardHistoryResponse(BaseModel):
    """Price history response."""
    card_id: int
    card_name: str
    history: list[PricePoint]
    from_date: datetime
    to_date: datetime
    data_points: int
    latest_snapshot_time: Optional[datetime] = None  # Most recent data point timestamp
    data_freshness_minutes: Optional[int] = None  # Minutes since latest snapshot


class CardMetricsResponse(BaseModel):
    """Card metrics response."""
    card_id: int
    date: str
    avg_price: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    spread_pct: Optional[float] = None
    price_change_7d: Optional[float] = None
    price_change_30d: Optional[float] = None
    volatility_7d: Optional[float] = None
    ma_7d: Optional[float] = None
    ma_30d: Optional[float] = None
    total_listings: Optional[int] = None


class CardDetailResponse(BaseModel):
    """Detailed card response with all data."""
    card: CardResponse
    metrics: Optional[CardMetricsResponse] = None
    current_prices: list[MarketplacePriceDetail] = []
    recent_signals: list["SignalSummary"] = []
    active_recommendations: list["RecommendationSummary"] = []
    refresh_requested: bool = False
    refresh_reason: Optional[str] = None


class SignalSummary(BaseModel):
    """Brief signal info for card detail."""
    signal_type: str
    value: Optional[float] = None
    confidence: Optional[float] = None
    date: str
    llm_insight: Optional[str] = None


class RecommendationSummary(BaseModel):
    """Brief recommendation info for card detail."""
    action: str
    confidence: float
    rationale: str
    marketplace: Optional[str] = None
    potential_profit_pct: Optional[float] = None


# Update forward references
CardPriceResponse.model_rebuild()
CardDetailResponse.model_rebuild()

