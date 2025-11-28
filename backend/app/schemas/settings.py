"""
Settings-related Pydantic schemas.
"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class SettingItem(BaseModel):
    """Single setting item."""
    key: str
    value: Any
    description: Optional[str] = None
    value_type: str = "string"


class SettingsResponse(BaseModel):
    """All settings response."""
    settings: dict[str, Any]
    
    # Typed convenience fields
    enabled_marketplaces: list[str] = []
    min_roi_threshold: float = 0.10
    min_confidence_threshold: float = 0.60
    recommendation_horizon_days: int = 7
    price_history_days: int = 90
    scraping_enabled: bool = True
    analytics_enabled: bool = True


class SettingsUpdate(BaseModel):
    """Settings update request."""
    enabled_marketplaces: Optional[list[str]] = None
    min_roi_threshold: Optional[float] = Field(None, ge=0, le=1)
    min_confidence_threshold: Optional[float] = Field(None, ge=0, le=1)
    recommendation_horizon_days: Optional[int] = Field(None, ge=1, le=90)
    price_history_days: Optional[int] = Field(None, ge=7, le=365)
    scraping_enabled: Optional[bool] = None
    analytics_enabled: Optional[bool] = None

