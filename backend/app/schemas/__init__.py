"""
Pydantic schemas for API request/response validation.
"""
from app.schemas.card import (
    CardBase,
    CardCreate,
    CardResponse,
    CardSearchResponse,
    CardDetailResponse,
    CardPriceResponse,
    CardHistoryResponse,
    PricePoint,
)
from app.schemas.recommendation import (
    RecommendationBase,
    RecommendationResponse,
    RecommendationListResponse,
    RecommendationFilters,
)
from app.schemas.signal import SignalResponse, SignalListResponse
from app.schemas.marketplace import MarketplaceResponse, MarketplacePriceResponse
from app.schemas.dashboard import DashboardSummary, TopCard, MarketSpread
from app.schemas.settings import SettingsResponse, SettingsUpdate

__all__ = [
    # Card schemas
    "CardBase",
    "CardCreate",
    "CardResponse",
    "CardSearchResponse",
    "CardDetailResponse",
    "CardPriceResponse",
    "CardHistoryResponse",
    "PricePoint",
    # Recommendation schemas
    "RecommendationBase",
    "RecommendationResponse",
    "RecommendationListResponse",
    "RecommendationFilters",
    # Signal schemas
    "SignalResponse",
    "SignalListResponse",
    # Marketplace schemas
    "MarketplaceResponse",
    "MarketplacePriceResponse",
    # Dashboard schemas
    "DashboardSummary",
    "TopCard",
    "MarketSpread",
    # Settings schemas
    "SettingsResponse",
    "SettingsUpdate",
]

