"""
TypedDict schemas for API responses.

These provide type hints for dict responses that don't use Pydantic models,
particularly for internal functions and raw database query results.
"""
from typing import TypedDict, Optional, NotRequired
from datetime import datetime


# =============================================================================
# Market API Response Types
# =============================================================================

class MarketIndexPoint(TypedDict):
    """Single point in market index time series."""
    timestamp: str
    indexValue: float


class MarketIndexResponse(TypedDict):
    """Response from /api/market/index endpoint."""
    range: str
    currency: str
    points: list[MarketIndexPoint]
    isMockData: bool
    data_freshness_minutes: NotRequired[Optional[int]]
    latest_snapshot_time: NotRequired[Optional[str]]
    diagnostic: NotRequired[dict]


class MarketOverviewResponse(TypedDict):
    """Response from /api/market/overview endpoint."""
    totalCardsTracked: int
    totalSnapshots: int
    volume24hUsd: float
    avgPriceChange24hPct: Optional[float]
    activeFormatsTracked: int


class TopMoverItem(TypedDict):
    """Single item in top movers list."""
    cardName: str
    setCode: str
    format: str
    currentPriceUsd: float
    changePct: float
    volume: int


class TopMoversResponse(TypedDict):
    """Response from /api/market/top-movers endpoint."""
    window: str
    gainers: list[TopMoverItem]
    losers: list[TopMoverItem]
    isMockData: bool


class VolumeDataPoint(TypedDict):
    """Single volume data point."""
    timestamp: str
    volume: float


class FormatVolumeData(TypedDict):
    """Volume data for a single format."""
    format: str
    data: list[VolumeDataPoint]


class VolumeByFormatResponse(TypedDict):
    """Response from /api/market/volume-by-format endpoint."""
    days: int
    formats: list[FormatVolumeData]
    isMockData: bool


class ColorDistributionResponse(TypedDict):
    """Response from /api/market/color-distribution endpoint."""
    window: str
    colors: list[str]
    distribution: dict[str, float]
    isMockData: bool


class MarketDiagnosticsResponse(TypedDict):
    """Response from /api/market/diagnostics endpoint."""
    total_snapshots: int
    recent_7d: int
    recent_30d: int
    usd_snapshots: int
    eur_snapshots: int
    usd_recent_7d: int
    cards_with_snapshots: int
    total_cards: int
    test_query_rows: int
    sample_snapshot: Optional[dict]
    oldest_snapshot: Optional[dict]
    current_time: str
    seed_status: str
    chart_issue: str


# =============================================================================
# Price Snapshot Types (for composite key operations)
# =============================================================================

class PriceSnapshotKey(TypedDict):
    """Composite primary key for price_snapshots table."""
    time: datetime
    card_id: int
    marketplace_id: int
    condition: str
    is_foil: bool
    language: str


class PriceSnapshotData(TypedDict):
    """Full price snapshot data for insert/update operations."""
    time: datetime
    card_id: int
    marketplace_id: int
    condition: str
    is_foil: bool
    language: str
    price: float
    currency: str
    price_low: NotRequired[Optional[float]]
    price_mid: NotRequired[Optional[float]]
    price_high: NotRequired[Optional[float]]
    price_market: NotRequired[Optional[float]]
    num_listings: NotRequired[Optional[int]]
    total_quantity: NotRequired[Optional[int]]


class PriceSnapshotQueryResult(TypedDict):
    """Result from price snapshot queries."""
    time: datetime
    card_id: int
    marketplace_id: int
    condition: str
    is_foil: bool
    language: str
    price: float
    currency: str
    price_low: Optional[float]
    price_mid: Optional[float]
    price_high: Optional[float]
    price_market: Optional[float]
    num_listings: Optional[int]
    total_quantity: Optional[int]


# =============================================================================
# Card API Response Types
# =============================================================================

class CardBasicInfo(TypedDict):
    """Basic card information."""
    id: int
    scryfall_id: str
    name: str
    set_code: str
    collector_number: str
    rarity: NotRequired[Optional[str]]
    mana_cost: NotRequired[Optional[str]]
    type_line: NotRequired[Optional[str]]
    image_url: NotRequired[Optional[str]]


class MarketplacePriceInfo(TypedDict):
    """Price information for a single marketplace."""
    marketplace_id: int
    marketplace_name: str
    marketplace_slug: str
    price: float
    currency: str
    price_foil: NotRequired[Optional[float]]
    num_listings: NotRequired[Optional[int]]
    last_updated: str
    condition: NotRequired[Optional[str]]


class CardPricesResponse(TypedDict):
    """Response for card prices across marketplaces."""
    card_id: int
    card_name: str
    prices: list[MarketplacePriceInfo]
    lowest_price: Optional[float]
    highest_price: Optional[float]
    spread_pct: Optional[float]
    updated_at: str


class PriceHistoryPoint(TypedDict):
    """Single point in price history."""
    date: str
    price: float
    marketplace: str
    currency: str
    min_price: NotRequired[Optional[float]]
    max_price: NotRequired[Optional[float]]
    num_listings: NotRequired[Optional[int]]
    snapshot_time: NotRequired[Optional[str]]
    data_age_minutes: NotRequired[Optional[int]]
    condition: NotRequired[Optional[str]]
    price_foil: NotRequired[Optional[float]]


class CardHistoryDict(TypedDict):
    """
    TypedDict for card price history responses.

    Note: Named CardHistoryDict to avoid conflict with Pydantic CardHistoryResponse.
    """
    card_id: int
    card_name: str
    history: list[PriceHistoryPoint]
    from_date: str
    to_date: str
    data_points: int
    latest_snapshot_time: NotRequired[Optional[str]]
    data_freshness_minutes: NotRequired[Optional[int]]


# =============================================================================
# Dashboard API Response Types
# =============================================================================

class DashboardTopCard(TypedDict):
    """Top card in dashboard gainers/losers."""
    card_id: int
    card_name: str
    set_code: str
    image_url: Optional[str]
    current_price: Optional[float]
    price_change_pct: float
    price_change_period: str


class DashboardSpread(TypedDict):
    """Spread opportunity in dashboard."""
    card_id: int
    card_name: str
    set_code: str
    image_url: Optional[str]
    lowest_price: float
    lowest_marketplace: str
    highest_price: float
    highest_marketplace: str
    spread_pct: float


class DashboardSummaryResponse(TypedDict):
    """Response from dashboard summary endpoint."""
    total_cards: int
    total_with_prices: int
    total_marketplaces: int
    top_gainers: list[DashboardTopCard]
    top_losers: list[DashboardTopCard]
    highest_spreads: list[DashboardSpread]
    total_recommendations: int
    buy_recommendations: int
    sell_recommendations: int
    hold_recommendations: int
    last_scrape_time: Optional[str]
    last_analytics_time: Optional[str]
    avg_price_change_7d: Optional[float]
    avg_spread_pct: Optional[float]


# =============================================================================
# WebSocket Message Types
# =============================================================================

class WebSocketMessageBase(TypedDict):
    """Base WebSocket message structure."""
    type: str
    channel: NotRequired[str]
    timestamp: NotRequired[str]


class MarketUpdateMessage(WebSocketMessageBase):
    """Market index update via WebSocket."""
    index_value: NotRequired[float]
    change_24h: NotRequired[float]
    volume_24h: NotRequired[float]
    currency: NotRequired[str]


class CardUpdateMessage(WebSocketMessageBase):
    """Card price update via WebSocket."""
    card_id: int
    price: NotRequired[float]
    price_change: NotRequired[float]
    marketplace_id: NotRequired[int]


class DashboardUpdateMessage(WebSocketMessageBase):
    """Dashboard section update via WebSocket."""
    section: str
    data: NotRequired[dict]


class InventoryUpdateMessage(WebSocketMessageBase):
    """Inventory update via WebSocket."""
    item_id: NotRequired[int]
    action: NotRequired[str]  # 'created' | 'updated' | 'deleted'
    value_change: NotRequired[float]


class RecommendationsUpdateMessage(WebSocketMessageBase):
    """Recommendations update via WebSocket."""
    count: NotRequired[int]
    new_recommendations: NotRequired[int]


# =============================================================================
# Inventory API Response Types
# =============================================================================

class InventoryItemInfo(TypedDict):
    """Single inventory item."""
    id: int
    card_id: int
    card_name: str
    card_set: str
    card_image_url: Optional[str]
    quantity: int
    condition: str
    is_foil: bool
    language: str
    acquisition_price: Optional[float]
    acquisition_currency: str
    acquisition_date: Optional[str]
    acquisition_source: Optional[str]
    current_value: Optional[float]
    value_change_pct: Optional[float]
    last_valued_at: Optional[str]
    profit_loss: Optional[float]
    profit_loss_pct: Optional[float]
    notes: Optional[str]
    created_at: str
    updated_at: str


class InventoryListDict(TypedDict):
    """
    TypedDict for inventory list responses.

    Note: Named InventoryListDict to avoid conflict with Pydantic InventoryListResponse.
    """
    items: list[InventoryItemInfo]
    total: int
    page: int
    page_size: int
    has_more: bool
    total_items: int
    total_quantity: int
    total_value: float
    total_acquisition_cost: float
    total_profit_loss: float
    total_profit_loss_pct: Optional[float]


class InventoryAnalyticsResponse(TypedDict):
    """Response for inventory analytics."""
    total_unique_cards: int
    total_quantity: int
    total_acquisition_cost: float
    total_current_value: float
    total_profit_loss: float
    profit_loss_pct: Optional[float]
    condition_breakdown: dict[str, int]
    top_gainers: list[InventoryItemInfo]
    top_losers: list[InventoryItemInfo]
    value_distribution: dict[str, float]
    sell_recommendations: int
    hold_recommendations: int
    critical_alerts: int


# =============================================================================
# Task/Celery Response Types
# =============================================================================

class PriceCollectionResult(TypedDict):
    """Result from price collection task."""
    started_at: str
    completed_at: NotRequired[str]
    scryfall_snapshots: int
    cardtrader_snapshots: int
    manapool_snapshots: int
    tcgplayer_snapshots: int
    mtgjson_snapshots: int
    total_snapshots: int
    backfilled_snapshots: int
    cards_processed: int
    errors: list[str]


class InventoryPriceCollectionResult(TypedDict):
    """Result from inventory price collection task."""
    started_at: str
    completed_at: NotRequired[str]
    inventory_cards: int
    snapshots_created: int
    snapshots_updated: int
    backfilled_snapshots: int
    errors: list[str]


class MTGJSONImportResult(TypedDict):
    """Result from MTGJSON historical price import."""
    started_at: str
    completed_at: NotRequired[str]
    cards_processed: int
    snapshots_created: int
    snapshots_skipped: int
    errors: list[str]


class VectorizationResult(TypedDict):
    """Result from bulk vectorization task."""
    started_at: str
    completed_at: NotRequired[str]
    total_cards: int
    vectors_created: int
    vectors_updated: int
    vectors_skipped: int
    errors: list[dict]
