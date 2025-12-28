"""
Inventory-related Pydantic schemas.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class InventoryCondition(str, Enum):
    """Card condition grades."""
    MINT = "MINT"
    NEAR_MINT = "NEAR_MINT"
    LIGHTLY_PLAYED = "LIGHTLY_PLAYED"
    MODERATELY_PLAYED = "MODERATELY_PLAYED"
    HEAVILY_PLAYED = "HEAVILY_PLAYED"
    DAMAGED = "DAMAGED"


class InventoryUrgency(str, Enum):
    """Recommendation urgency levels."""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ActionType(str, Enum):
    """Recommendation action types."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


# Import schemas
class InventoryImportLine(BaseModel):
    """Single line of inventory import data."""
    card_name: str
    set_code: Optional[str] = None
    quantity: int = 1
    condition: InventoryCondition = InventoryCondition.NEAR_MINT
    is_foil: bool = False
    language: str = "English"
    acquisition_price: Optional[float] = None
    acquisition_date: Optional[datetime] = None
    acquisition_source: Optional[str] = None
    notes: Optional[str] = None


class InventoryImportRequest(BaseModel):
    """Request to import inventory from CSV or plaintext."""
    content: str = Field(..., description="CSV or plaintext content to import")
    format: str = Field("auto", description="Format: 'csv', 'plaintext', or 'auto' for detection")
    has_header: bool = Field(True, description="Whether CSV has a header row")
    default_condition: InventoryCondition = InventoryCondition.NEAR_MINT
    default_acquisition_source: Optional[str] = None


class ImportedItem(BaseModel):
    """Result of importing a single item."""
    line_number: int
    raw_line: str
    success: bool
    inventory_item_id: Optional[int] = None
    card_id: Optional[int] = None
    card_name: Optional[str] = None
    error: Optional[str] = None


class InventoryImportResponse(BaseModel):
    """Response from inventory import operation."""
    batch_id: str
    total_lines: int
    successful_imports: int
    failed_imports: int
    items: list[ImportedItem]


# CRUD schemas
class InventoryItemBase(BaseModel):
    """Base inventory item schema."""
    quantity: int = 1
    condition: InventoryCondition = InventoryCondition.NEAR_MINT
    is_foil: bool = False
    language: str = "English"
    acquisition_price: Optional[float] = None
    acquisition_currency: str = "USD"
    acquisition_date: Optional[datetime] = None
    acquisition_source: Optional[str] = None
    notes: Optional[str] = None
    
    class Config:
        from_attributes = True


class InventoryItemCreate(InventoryItemBase):
    """Schema for creating an inventory item."""
    card_id: int


class InventoryItemUpdate(BaseModel):
    """Schema for updating an inventory item."""
    quantity: Optional[int] = None
    condition: Optional[InventoryCondition] = None
    is_foil: Optional[bool] = None
    language: Optional[str] = None
    acquisition_price: Optional[float] = None
    acquisition_currency: Optional[str] = None
    acquisition_date: Optional[datetime] = None
    acquisition_source: Optional[str] = None
    notes: Optional[str] = None


class InventoryItemResponse(InventoryItemBase):
    """Full inventory item response."""
    id: int
    card_id: int
    card_name: str
    card_set: str
    card_image_url: Optional[str] = None
    current_value: Optional[float] = None
    value_change_pct: Optional[float] = None
    last_valued_at: Optional[datetime] = None
    profit_loss: Optional[float] = None
    profit_loss_pct: Optional[float] = None
    import_batch_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class InventoryListResponse(BaseModel):
    """Paginated inventory list."""
    items: list[InventoryItemResponse]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False
    
    # Summary stats
    total_items: int = 0
    total_quantity: int = 0
    total_value: float = 0.0
    total_acquisition_cost: float = 0.0
    total_profit_loss: float = 0.0
    total_profit_loss_pct: Optional[float] = None


# Analytics schemas
class InventoryAnalytics(BaseModel):
    """Comprehensive inventory analytics."""
    total_unique_cards: int
    total_quantity: int
    total_acquisition_cost: float
    total_current_value: float
    total_profit_loss: float
    profit_loss_pct: Optional[float] = None
    
    # Breakdown by condition
    condition_breakdown: dict[str, int]
    
    # Top performers
    top_gainers: list[InventoryItemResponse]
    top_losers: list[InventoryItemResponse]
    
    # Price distribution
    value_distribution: dict[str, int]  # price ranges
    
    # Recommendations summary
    sell_recommendations: int = 0
    hold_recommendations: int = 0
    critical_alerts: int = 0


# Recommendation schemas
class InventoryRecommendationResponse(BaseModel):
    """Inventory-specific recommendation response."""
    id: int
    inventory_item_id: int
    card_id: int
    card_name: str
    card_set: str
    card_image_url: Optional[str] = None
    
    action: ActionType
    urgency: InventoryUrgency
    confidence: float = Field(..., ge=0, le=1)
    horizon_days: int
    
    # Prices
    current_price: Optional[float] = None
    target_price: Optional[float] = None
    potential_profit_pct: Optional[float] = None
    
    # Acquisition context
    acquisition_price: Optional[float] = None
    roi_from_acquisition: Optional[float] = None
    
    # Guidance
    rationale: str
    suggested_marketplace: Optional[str] = None
    suggested_listing_price: Optional[float] = None
    
    valid_until: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime
    
    class Config:
        from_attributes = True


class InventoryRecommendationListResponse(BaseModel):
    """Paginated inventory recommendation list."""
    recommendations: list[InventoryRecommendationResponse]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False

    # Summary stats by urgency
    critical_count: int = 0
    high_count: int = 0
    normal_count: int = 0
    low_count: int = 0

    # Summary stats by action
    sell_count: int = 0
    hold_count: int = 0


# Top Movers schemas
class TopMoverCard(BaseModel):
    """A card with significant price movement."""
    card_id: int
    card_name: str
    set_code: str
    image_url: Optional[str] = None
    old_price: float
    new_price: float
    change_pct: float


class InventoryTopMoversResponse(BaseModel):
    """Response for inventory top movers endpoint."""
    window: str
    gainers: list[TopMoverCard]
    losers: list[TopMoverCard]
    data_freshness_hours: float
