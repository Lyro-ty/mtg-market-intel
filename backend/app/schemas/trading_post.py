"""
Trading Post (LGS) related Pydantic schemas.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    """Types of trading post events."""
    TOURNAMENT = "tournament"
    SALE = "sale"
    RELEASE = "release"
    MEETUP = "meetup"


class SubmissionStatus(str, Enum):
    """Status of a quote submission."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    COUNTERED = "countered"
    DECLINED = "declined"
    USER_ACCEPTED = "user_accepted"
    USER_DECLINED = "user_declined"


class QuoteStatus(str, Enum):
    """Status of a trade quote."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    EXPIRED = "expired"


# ============ Trading Post Schemas ============

class TradingPostCreate(BaseModel):
    """Schema for creating a new trading post."""
    store_name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)
    country: str = Field("US", max_length=50)
    postal_code: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=20)
    website: Optional[str] = Field(None, max_length=500)
    hours: Optional[dict] = None  # {"monday": "10:00-20:00", ...}
    services: Optional[list[str]] = None  # ["singles", "tournaments", "buylist"]
    buylist_margin: Decimal = Field(
        default=Decimal("0.50"),
        ge=Decimal("0.01"),
        le=Decimal("0.99"),
        description="Percentage of market price paid for cards (0.50 = 50%)"
    )

    @field_validator("website")
    @classmethod
    def validate_website(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.startswith(("http://", "https://")):
            return f"https://{v}"
        return v


class TradingPostUpdate(BaseModel):
    """Schema for updating a trading post."""
    store_name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)
    country: Optional[str] = Field(None, max_length=50)
    postal_code: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=20)
    website: Optional[str] = Field(None, max_length=500)
    hours: Optional[dict] = None
    services: Optional[list[str]] = None
    logo_url: Optional[str] = Field(None, max_length=500)
    buylist_margin: Optional[Decimal] = Field(
        None,
        ge=Decimal("0.01"),
        le=Decimal("0.99")
    )


class TradingPostResponse(BaseModel):
    """Schema for trading post response."""
    id: int
    user_id: int
    store_name: str
    description: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    hours: Optional[dict] = None
    services: Optional[list[str]] = None
    logo_url: Optional[str] = None
    buylist_margin: Decimal
    email_verified_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Computed fields
    is_verified: bool = False
    is_email_verified: bool = False

    class Config:
        from_attributes = True


class TradingPostPublic(BaseModel):
    """Public-facing trading post info (no sensitive data)."""
    id: int
    store_name: str
    description: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str
    website: Optional[str] = None
    hours: Optional[dict] = None
    services: Optional[list[str]] = None
    logo_url: Optional[str] = None
    is_verified: bool = False

    class Config:
        from_attributes = True


class TradingPostListResponse(BaseModel):
    """Paginated list of trading posts."""
    items: list[TradingPostPublic]
    total: int
    page: int
    page_size: int


# ============ Event Schemas ============

class EventCreate(BaseModel):
    """Schema for creating a trading post event."""
    title: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    event_type: EventType
    format: Optional[str] = Field(None, max_length=50)  # modern, standard, commander
    start_time: datetime
    end_time: Optional[datetime] = None
    entry_fee: Optional[Decimal] = Field(None, ge=0)
    max_players: Optional[int] = Field(None, ge=1)


class EventUpdate(BaseModel):
    """Schema for updating an event."""
    title: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    event_type: Optional[EventType] = None
    format: Optional[str] = Field(None, max_length=50)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    entry_fee: Optional[Decimal] = Field(None, ge=0)
    max_players: Optional[int] = Field(None, ge=1)


class EventResponse(BaseModel):
    """Schema for event response."""
    id: int
    trading_post_id: int
    title: str
    description: Optional[str] = None
    event_type: str
    format: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    entry_fee: Optional[Decimal] = None
    max_players: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    # Include store info for discovery
    trading_post: Optional[TradingPostPublic] = None

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    """Paginated list of events."""
    items: list[EventResponse]
    total: int


# ============ Quote Offer Preview ============

class StoreOffer(BaseModel):
    """Preview of what a store would pay for a quote."""
    trading_post_id: int
    store_name: str
    city: Optional[str] = None
    state: Optional[str] = None
    is_verified: bool = False
    buylist_margin: Decimal
    offer_amount: Decimal  # total_market_value * margin


class QuoteOffersPreview(BaseModel):
    """Preview of offers from nearby stores."""
    quote_id: int
    total_market_value: Decimal
    offers: list[StoreOffer]
