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


# ============ Trade Quote Schemas ============

class QuoteItemCreate(BaseModel):
    """Schema for adding a card to a quote."""
    card_id: int
    quantity: int = Field(1, ge=1, le=100)
    condition: str = Field("NM", max_length=20)  # NM, LP, MP, HP, DMG


class QuoteItemUpdate(BaseModel):
    """Schema for updating a quote item."""
    quantity: Optional[int] = Field(None, ge=1, le=100)
    condition: Optional[str] = Field(None, max_length=20)


class QuoteItemResponse(BaseModel):
    """Schema for quote item response."""
    id: int
    card_id: int
    card_name: str
    set_code: Optional[str] = None
    quantity: int
    condition: str
    market_price: Optional[Decimal] = None
    line_total: Optional[Decimal] = None  # market_price * quantity

    class Config:
        from_attributes = True


class QuoteCreate(BaseModel):
    """Schema for creating a new trade quote."""
    name: Optional[str] = Field(None, max_length=100, description="Optional name for the quote")


class QuoteUpdate(BaseModel):
    """Schema for updating a quote."""
    name: Optional[str] = Field(None, max_length=100)
    status: Optional[QuoteStatus] = None


class QuoteResponse(BaseModel):
    """Schema for quote response."""
    id: int
    user_id: int
    name: Optional[str] = None
    status: str
    total_market_value: Optional[Decimal] = None
    item_count: int = 0
    items: list[QuoteItemResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class QuoteListResponse(BaseModel):
    """Paginated list of quotes."""
    items: list[QuoteResponse]
    total: int
    page: int
    page_size: int


class QuoteBulkImportItem(BaseModel):
    """Single item in a bulk import."""
    card_name: str
    set_code: Optional[str] = None
    quantity: int = Field(1, ge=1)
    condition: str = Field("NM")


class QuoteBulkImport(BaseModel):
    """Schema for bulk importing cards to a quote."""
    items: list[QuoteBulkImportItem]


class QuoteBulkImportResult(BaseModel):
    """Result of bulk import operation."""
    imported: int
    failed: int
    errors: list[str] = []


# ============ Quote Submission Schemas ============

class QuoteSubmit(BaseModel):
    """Schema for submitting a quote to stores."""
    trading_post_ids: list[int] = Field(..., min_length=1, max_length=5)
    message: Optional[str] = Field(None, max_length=500)


class SubmissionCounter(BaseModel):
    """Schema for store counter-offer."""
    counter_amount: Decimal = Field(..., gt=0)
    message: Optional[str] = Field(None, max_length=500)


class SubmissionResponse(BaseModel):
    """Schema for quote submission response."""
    id: int
    quote_id: int
    trading_post_id: int
    status: str
    offer_amount: Decimal
    counter_amount: Optional[Decimal] = None
    store_message: Optional[str] = None
    user_message: Optional[str] = None
    submitted_at: datetime
    responded_at: Optional[datetime] = None

    # Include store info
    trading_post: Optional[TradingPostPublic] = None

    # Include quote summary (for store view)
    quote_name: Optional[str] = None
    quote_item_count: Optional[int] = None
    quote_total_value: Optional[Decimal] = None

    class Config:
        from_attributes = True


class SubmissionListResponse(BaseModel):
    """List of quote submissions."""
    items: list[SubmissionResponse]
    total: int
