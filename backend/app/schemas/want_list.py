"""
Want List Pydantic schemas for API request/response validation.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class WantListPriority(str, Enum):
    """Priority levels for want list items."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CardSummary(BaseModel):
    """Summary of card info for embedding in responses."""
    id: int
    name: str
    set_code: str
    current_price: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)


class WantListItemBase(BaseModel):
    """Base schema with shared fields for want list items."""
    card_id: int
    target_price: Decimal = Field(..., gt=0, description="Target price to buy at")
    priority: WantListPriority = Field(
        default=WantListPriority.MEDIUM,
        description="Priority level for this want"
    )
    alert_enabled: bool = Field(
        default=True,
        description="Whether to send alerts when price drops below target"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Optional notes about this want list item"
    )
    # Enhanced alert options
    alert_on_spike: bool = Field(
        default=False,
        description="Alert when price spikes by threshold percentage"
    )
    alert_threshold_pct: Optional[Decimal] = Field(
        default=None,
        ge=0,
        le=100,
        description="Price change threshold % to trigger spike alert (e.g., 15.00 = 15%)"
    )
    alert_on_supply_low: bool = Field(
        default=False,
        description="Alert when supply drops to low levels"
    )
    alert_on_price_drop: bool = Field(
        default=True,
        description="Alert when price drops below target price"
    )


class WantListItemCreate(WantListItemBase):
    """Schema for creating a want list item."""
    pass


class WantListItemUpdate(BaseModel):
    """Schema for updating a want list item. All fields optional."""
    target_price: Optional[Decimal] = Field(
        default=None,
        gt=0,
        description="Target price to buy at"
    )
    priority: Optional[WantListPriority] = Field(
        default=None,
        description="Priority level for this want"
    )
    alert_enabled: Optional[bool] = Field(
        default=None,
        description="Whether to send alerts when price drops below target"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Optional notes about this want list item"
    )
    # Enhanced alert options
    alert_on_spike: Optional[bool] = Field(
        default=None,
        description="Alert when price spikes by threshold percentage"
    )
    alert_threshold_pct: Optional[Decimal] = Field(
        default=None,
        ge=0,
        le=100,
        description="Price change threshold % to trigger spike alert"
    )
    alert_on_supply_low: Optional[bool] = Field(
        default=None,
        description="Alert when supply drops to low levels"
    )
    alert_on_price_drop: Optional[bool] = Field(
        default=None,
        description="Alert when price drops below target price"
    )


class WantListItemResponse(WantListItemBase):
    """Full want list item response with card details."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    card: CardSummary

    model_config = ConfigDict(from_attributes=True)


class WantListListResponse(BaseModel):
    """Paginated want list response."""
    items: list[WantListItemResponse]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False
