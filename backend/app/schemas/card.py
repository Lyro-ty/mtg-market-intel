"""
Card-related Pydantic schemas.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

import json
from pydantic import BaseModel, Field, field_validator


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
    legalities: Optional[dict] = None

    @field_validator('legalities', mode='before')
    @classmethod
    def parse_legalities(cls, v):
        """Parse legalities from JSON string if needed."""
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    class Config:
        from_attributes = True


class CardSearchResponse(BaseModel):
    """Card search results schema (offset-based pagination)."""
    cards: list[CardResponse]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False


class CardCursorSearchResponse(BaseModel):
    """Card search results with cursor-based pagination.

    Cursor pagination is more efficient for large datasets:
    - O(1) performance vs O(n) for offset pagination
    - Use next_cursor to fetch the next page
    - Stable results even with concurrent inserts/deletes
    """
    cards: list[CardResponse]
    next_cursor: Optional[str] = Field(
        default=None,
        description="Cursor for the next page. Pass this as 'cursor' to get next results."
    )
    has_more: bool = Field(
        default=False,
        description="True if there are more results after this page"
    )
    total_count: Optional[int] = Field(
        default=None,
        description="Total matching count. Only included if include_count=true (adds query overhead)"
    )


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
    condition: Optional[str] = None  # Card condition (Near Mint, Lightly Played, etc.)
    price_foil: Optional[float] = None  # Foil price if available


class CardPriceResponse(BaseModel):
    """Current prices across marketplaces.

    Price fields default to 0.0 instead of null for frontend compatibility.
    Check `has_price_data` to determine if prices are real or defaults.
    """
    card_id: int
    card_name: str
    prices: list["MarketplacePriceDetail"]
    lowest_price: float = Field(default=0.0, description="Lowest price across marketplaces (0.0 if no data)")
    highest_price: float = Field(default=0.0, description="Highest price across marketplaces (0.0 if no data)")
    spread_pct: float = Field(default=0.0, description="Price spread percentage (0.0 if no data)")
    updated_at: datetime
    has_price_data: bool = Field(default=False, description="True if real price data is available")


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
    condition: Optional[str] = None  # Card condition (Near Mint, Lightly Played, etc.)


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
    """Card metrics response.

    Price/metric fields default to 0.0 instead of null for frontend compatibility.
    Check `has_metrics_data` to determine if metrics are real or defaults.
    """
    card_id: int
    date: Optional[str] = Field(default=None, description="Metrics date (None if no data)")
    avg_price: float = Field(default=0.0, description="Average price (0.0 if no data)")
    min_price: float = Field(default=0.0, description="Minimum price (0.0 if no data)")
    max_price: float = Field(default=0.0, description="Maximum price (0.0 if no data)")
    spread_pct: float = Field(default=0.0, description="Price spread percentage (0.0 if no data)")
    price_change_7d: float = Field(default=0.0, description="7-day price change percentage (0.0 if no data)")
    price_change_30d: float = Field(default=0.0, description="30-day price change percentage (0.0 if no data)")
    volatility_7d: float = Field(default=0.0, description="7-day volatility (0.0 if no data)")
    ma_7d: float = Field(default=0.0, description="7-day moving average (0.0 if no data)")
    ma_30d: float = Field(default=0.0, description="30-day moving average (0.0 if no data)")
    total_listings: int = Field(default=0, description="Total number of listings (0 if no data)")
    has_metrics_data: bool = Field(default=False, description="True if real metrics data is available")


class CardDetailResponse(BaseModel):
    """Detailed card response with all data.

    Use `has_price_data` to check if current_prices contains real data.
    When no price data exists, current_prices will be empty and has_price_data=False.
    """
    card: CardResponse
    metrics: Optional[CardMetricsResponse] = None
    current_prices: list[MarketplacePriceDetail] = []
    recent_signals: list["SignalSummary"] = []
    active_recommendations: list["RecommendationSummary"] = []
    refresh_requested: bool = False
    refresh_reason: Optional[str] = None
    has_price_data: bool = Field(default=False, description="True if current_prices contains real price data")


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


class CardPublicResponse(BaseModel):
    """Public card response - no internal ID exposed."""
    hashid: str
    name: str
    set_code: str
    set_name: Optional[str] = None
    collector_number: str
    rarity: Optional[str] = None
    mana_cost: Optional[str] = None
    cmc: Optional[float] = None
    type_line: Optional[str] = None
    oracle_text: Optional[str] = None
    colors: Optional[str] = None
    power: Optional[str] = None
    toughness: Optional[str] = None
    image_url: Optional[str] = None
    image_url_small: Optional[str] = None
    image_url_large: Optional[str] = None


class CardPublicPriceResponse(BaseModel):
    """Public price history response."""
    hashid: str
    card_name: str
    prices: list[PricePoint] = []
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    data_points: int = 0


# Update forward references
CardPriceResponse.model_rebuild()
CardDetailResponse.model_rebuild()

