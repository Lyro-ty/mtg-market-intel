"""
Recommendation-related Pydantic schemas.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """Recommendation action types."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class RecommendationBase(BaseModel):
    """Base recommendation schema."""
    action: ActionType
    confidence: float = Field(..., ge=0, le=1)
    rationale: str
    horizon_days: int = 7
    
    class Config:
        from_attributes = True


class RecommendationResponse(RecommendationBase):
    """Full recommendation response."""
    id: int
    card_id: int
    card_name: str
    card_set: str
    card_image_url: Optional[str] = None
    marketplace_id: Optional[int] = None
    marketplace_name: Optional[str] = None
    target_price: Optional[float] = None
    current_price: Optional[float] = None
    potential_profit_pct: Optional[float] = None
    source_signals: Optional[list[str]] = None
    valid_until: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime
    
    class Config:
        from_attributes = True


class RecommendationFilters(BaseModel):
    """Filters for recommendation queries."""
    action: Optional[ActionType] = None
    min_confidence: Optional[float] = Field(None, ge=0, le=1)
    marketplace_id: Optional[int] = None
    set_code: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    is_active: bool = True


class RecommendationListResponse(BaseModel):
    """Paginated recommendation list."""
    recommendations: list[RecommendationResponse]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False
    
    # Summary stats
    buy_count: int = 0
    sell_count: int = 0
    hold_count: int = 0

