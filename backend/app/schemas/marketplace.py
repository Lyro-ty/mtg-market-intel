"""
Marketplace-related Pydantic schemas.
"""
from typing import Optional

from pydantic import BaseModel


class MarketplaceResponse(BaseModel):
    """Marketplace response schema."""
    id: int
    name: str
    slug: str
    base_url: str
    is_enabled: bool = True
    supports_api: bool = False
    default_currency: str = "USD"
    
    class Config:
        from_attributes = True


class MarketplacePriceResponse(BaseModel):
    """Price data from a marketplace."""
    marketplace: MarketplaceResponse
    price: float
    currency: str = "USD"
    price_foil: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    num_listings: Optional[int] = None
    total_quantity: Optional[int] = None
    last_updated: Optional[str] = None


class MarketplaceListResponse(BaseModel):
    """List of marketplaces."""
    marketplaces: list[MarketplaceResponse]
    total: int

