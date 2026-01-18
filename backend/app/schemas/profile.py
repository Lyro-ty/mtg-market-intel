"""
Profile-related Pydantic schemas.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# Valid card types for social trading
CardType = Literal["collector", "trader", "brewer", "investor"]

# Valid shipping preferences
ShippingPreference = Literal["local", "domestic", "international"]


class SignatureCardResponse(BaseModel):
    """Nested card info for signature card."""
    id: int
    name: str
    image_url: Optional[str] = None

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    """Schema for updating user profile."""
    # Basic profile fields
    display_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = Field(None, max_length=500)

    # Social trading fields
    tagline: Optional[str] = Field(None, max_length=50)
    card_type: Optional[CardType] = None
    signature_card_id: Optional[int] = None

    # Extended location fields
    city: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    shipping_preference: Optional[ShippingPreference] = None

    # Privacy settings
    show_in_directory: Optional[bool] = None
    show_in_search: Optional[bool] = None
    show_online_status: Optional[bool] = None
    show_portfolio_tier: Optional[bool] = None


class ProfileResponse(BaseModel):
    """Profile response schema for authenticated user."""
    id: int
    email: str
    username: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    avatar_url: Optional[str] = None
    discord_id: Optional[str] = None
    created_at: datetime
    last_active_at: Optional[datetime] = None

    # Social trading fields
    tagline: Optional[str] = None
    card_type: Optional[str] = None
    signature_card_id: Optional[int] = None
    signature_card: Optional[SignatureCardResponse] = None

    # Extended location fields
    city: Optional[str] = None
    country: Optional[str] = None
    shipping_preference: Optional[str] = None

    # Frame and discovery
    active_frame_tier: str = "bronze"
    discovery_score: int = 100

    # Privacy settings
    show_in_directory: bool = True
    show_in_search: bool = True
    show_online_status: bool = True
    show_portfolio_tier: bool = True

    # Onboarding
    onboarding_completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PublicProfileResponse(BaseModel):
    """Public profile response - limited fields for other users."""
    username: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    hashid: Optional[str] = None
    cards_for_trade: int = 0

    # Social trading fields (public)
    tagline: Optional[str] = None
    card_type: Optional[str] = None
    signature_card: Optional[SignatureCardResponse] = None
    active_frame_tier: str = "bronze"
    shipping_preference: Optional[str] = None

    # Extended location (only if show_in_directory is true)
    city: Optional[str] = None
    country: Optional[str] = None

    class Config:
        from_attributes = True
