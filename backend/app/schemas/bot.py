"""Pydantic schemas for Discord bot API endpoints."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


# =============================================================================
# User Lookup Schemas
# =============================================================================

class BotUserResponse(BaseModel):
    """User data returned to the bot for linked Discord accounts."""

    user_id: int = Field(..., description="Internal user ID")
    username: str = Field(..., description="Username on the platform")
    display_name: Optional[str] = Field(None, description="Display name if set")
    discord_alerts_enabled: bool = Field(..., description="Whether Discord alerts are enabled")

    class Config:
        from_attributes = True


# =============================================================================
# Portfolio Schemas
# =============================================================================

class PortfolioSummary(BaseModel):
    """Summary of a user's portfolio for bot display."""

    total_value: Decimal = Field(..., description="Total portfolio value in USD")
    total_cards: int = Field(..., description="Total number of cards")
    unique_cards: int = Field(..., description="Number of unique cards")
    change_24h: Optional[Decimal] = Field(None, description="24h value change")
    change_24h_pct: Optional[float] = Field(None, description="24h change percentage")
    top_cards: list["PortfolioCard"] = Field(default_factory=list, description="Top 5 cards by value")


class PortfolioCard(BaseModel):
    """Card in portfolio summary."""

    card_id: int
    name: str
    set_code: str
    quantity: int
    current_price: Decimal
    total_value: Decimal
    change_24h_pct: Optional[float] = None


# =============================================================================
# Want List Schemas
# =============================================================================

class WantListSummary(BaseModel):
    """Summary of a user's want list for bot display."""

    total_items: int = Field(..., description="Total items on want list")
    items_with_alerts: int = Field(..., description="Items with price alerts set")
    alerts_triggered: int = Field(..., description="Alerts triggered (target hit)")
    items: list["WantListItemBrief"] = Field(default_factory=list, description="Want list items")


class WantListItemBrief(BaseModel):
    """Brief want list item for bot display."""

    card_id: int
    name: str
    set_code: str
    target_price: Optional[Decimal] = None
    current_price: Optional[Decimal] = None
    alert_triggered: bool = False


# =============================================================================
# Trade Schemas
# =============================================================================

class TradeItem(BaseModel):
    """Item available for trade."""

    card_id: int
    name: str
    set_code: str
    quantity: int
    condition: str
    is_foil: bool
    current_price: Optional[Decimal] = None


class UserTradeList(BaseModel):
    """User's trade list for bot display."""

    user_id: int
    username: str
    discord_username: Optional[str] = None
    total_for_trade: int
    items: list[TradeItem] = Field(default_factory=list)


# =============================================================================
# Alert Schemas
# =============================================================================

class PendingAlert(BaseModel):
    """Alert pending delivery to Discord."""

    alert_id: int
    user_id: int
    discord_id: str
    alert_type: str = Field(..., description="Type: price_alert, price_spike, etc.")
    title: str
    message: str
    card_id: Optional[int] = None
    card_name: Optional[str] = None
    current_price: Optional[Decimal] = None
    target_price: Optional[Decimal] = None
    created_at: datetime


class AlertDeliveryConfirm(BaseModel):
    """Confirmation of alert delivery."""

    alert_ids: list[int] = Field(
        ...,
        max_length=500,
        description="IDs of alerts successfully delivered (max 500)"
    )


# =============================================================================
# Discovery Schemas
# =============================================================================

class TraderMatch(BaseModel):
    """A potential trade match between users."""

    user_id: int
    username: str
    discord_id: Optional[str] = None
    discord_username: Optional[str] = None
    has_cards: list[str] = Field(default_factory=list, description="Cards they have that you want")
    wants_cards: list[str] = Field(default_factory=list, description="Cards they want that you have")
    match_score: int = Field(..., description="Number of matching cards")


# Update forward references
PortfolioSummary.model_rebuild()
WantListSummary.model_rebuild()
