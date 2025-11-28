"""
Dashboard-related Pydantic schemas.
"""
from typing import Optional

from pydantic import BaseModel


class TopCard(BaseModel):
    """Card with price change info for dashboard."""
    card_id: int
    card_name: str
    set_code: str
    image_url: Optional[str] = None
    current_price: Optional[float] = None
    price_change_pct: float
    price_change_period: str = "7d"  # 7d, 30d, etc.


class MarketSpread(BaseModel):
    """Card with high market spread."""
    card_id: int
    card_name: str
    set_code: str
    image_url: Optional[str] = None
    lowest_price: float
    lowest_marketplace: str
    highest_price: float
    highest_marketplace: str
    spread_pct: float


class DashboardSummary(BaseModel):
    """Dashboard summary data."""
    # Card statistics
    total_cards: int
    total_with_prices: int
    total_marketplaces: int
    
    # Top movers
    top_gainers: list[TopCard]
    top_losers: list[TopCard]
    
    # Arbitrage opportunities
    highest_spreads: list[MarketSpread]
    
    # Recommendation summary
    total_recommendations: int
    buy_recommendations: int
    sell_recommendations: int
    hold_recommendations: int
    
    # Recent activity
    last_scrape_time: Optional[str] = None
    last_analytics_time: Optional[str] = None
    
    # Price stats
    avg_price_change_7d: Optional[float] = None
    avg_spread_pct: Optional[float] = None


class ChartDataPoint(BaseModel):
    """Data point for charts."""
    x: str  # Date or label
    y: float  # Value
    label: Optional[str] = None


class PriceChartData(BaseModel):
    """Price chart data for a card."""
    card_id: int
    card_name: str
    series: list["ChartSeries"]


class ChartSeries(BaseModel):
    """Single series in a chart."""
    name: str  # e.g., marketplace name
    data: list[ChartDataPoint]
    color: Optional[str] = None


# Update forward references
PriceChartData.model_rebuild()

