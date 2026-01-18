"""
User directory and profile card Pydantic schemas.

These schemas support the trading card-style user profiles and
the social trading directory features.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProfileCardResponse(BaseModel):
    """The trading card-style profile displayed in the directory."""
    id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    tagline: Optional[str] = None
    card_type: Optional[str] = None  # collector, trader, brewer, investor

    # Stats
    trade_count: int = 0
    reputation_score: Optional[float] = None
    reputation_count: int = 0
    success_rate: Optional[float] = None
    response_time_hours: Optional[float] = None

    # Frame and tier
    frame_tier: str = "bronze"

    # Location
    city: Optional[str] = None
    country: Optional[str] = None
    shipping_preference: Optional[str] = None

    # Status
    is_online: bool = False
    last_active_at: Optional[datetime] = None
    open_to_trades: bool = False

    # Verification
    email_verified: bool = False
    discord_linked: bool = False
    id_verified: bool = False

    # Badges (top achievements)
    badges: list[dict] = Field(
        default_factory=list,
        description='Top badges, e.g. [{"key": "trade_master", "icon": "...", "name": "..."}]'
    )

    # Formats
    formats: list[str] = Field(
        default_factory=list,
        description="MTG formats the user plays (modern, standard, commander, etc.)"
    )

    # Signature card
    signature_card: Optional[dict] = Field(
        default=None,
        description='Favorite card, e.g. {"id": 1, "name": "...", "image_url": "..."}'
    )

    # Member info
    member_since: datetime

    class Config:
        from_attributes = True


class ProfileCardBackResponse(BaseModel):
    """Extended info for card flip (back of the trading card)."""
    id: int
    total_trades: int = 0
    completed_trades: int = 0
    portfolio_tier: Optional[str] = None
    endorsement_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Counts by endorsement type (trustworthy, responsive, etc.)"
    )
    recent_trades: list[dict] = Field(
        default_factory=list,
        description="Recent trade summaries"
    )
    recent_reviews: list[dict] = Field(
        default_factory=list,
        description="Recent reviews received"
    )
    mutual_connections: list[dict] = Field(
        default_factory=list,
        description="Mutual connections with viewer"
    )
    achievements: list[dict] = Field(
        default_factory=list,
        description="Achievement badges"
    )


class QuickTradePreviewResponse(BaseModel):
    """Hover preview for trade potential between users."""
    user_id: int
    cards_they_have_you_want: int = 0
    cards_they_have_you_want_value: float = 0.0
    cards_you_have_they_want: int = 0
    cards_you_have_they_want_value: float = 0.0
    is_mutual_match: bool = False


class DirectoryFilters(BaseModel):
    """Filters for the user directory search."""
    q: Optional[str] = Field(None, description="Search query for username/display name")
    sort: str = Field("discovery_score", description="Sort field")
    reputation_tier: Optional[list[str]] = Field(
        None, description="Filter by reputation tier (bronze, silver, gold, platinum)"
    )
    frame_tier: Optional[list[str]] = Field(
        None, description="Filter by frame tier (bronze, silver, gold, platinum)"
    )
    card_type: Optional[list[str]] = Field(
        None, description="Filter by card type (collector, trader, brewer, investor)"
    )
    format: Optional[list[str]] = Field(
        None, description="Filter by MTG formats (modern, standard, commander, etc.)"
    )
    shipping: Optional[list[str]] = Field(
        None, description="Filter by shipping preference (local, domestic, international)"
    )
    country: Optional[str] = Field(None, description="Filter by country code")
    online_only: bool = Field(False, description="Only show online users")
    has_my_wants: bool = Field(False, description="Only users with cards I want")
    wants_my_cards: bool = Field(False, description="Only users who want my cards")
    user_type: Optional[str] = Field(None, description="Filter by user type (individual, store)")
    verified_only: bool = Field(False, description="Only show verified users")


class DirectoryResponse(BaseModel):
    """Paginated directory listing response."""
    users: list[ProfileCardResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class SuggestedUserResponse(BaseModel):
    """A suggested user with matching context."""
    user: ProfileCardResponse
    reason: str = Field(description="Why this user is suggested")
    mutual_connection_count: int = 0
    matching_formats: list[str] = Field(default_factory=list)
    matching_cards: int = 0
