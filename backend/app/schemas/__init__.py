"""
Pydantic schemas for API request/response validation.

Also exports TypedDict schemas for internal type hints.
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
from app.schemas.inventory import (
    InventoryCondition,
    InventoryUrgency,
    InventoryImportRequest,
    InventoryImportResponse,
    ImportedItem,
    InventoryItemBase,
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse,
    InventoryListResponse,
    InventoryAnalytics,
    InventoryRecommendationResponse,
    InventoryRecommendationListResponse,
)
from app.schemas.sets import (
    MTGSetResponse,
    MTGSetList,
    SetSearchQuery,
)
from app.schemas.want_list import (
    WantListPriority,
    CardSummary,
    WantListItemBase,
    WantListItemCreate,
    WantListItemUpdate,
    WantListItemResponse,
    WantListListResponse,
)
from app.schemas.notification import (
    NotificationResponse,
    NotificationUpdate,
    NotificationList,
    UnreadCountResponse,
)
from app.schemas.collection import (
    CollectionStatsResponse,
    SetCompletion,
    SetCompletionList,
    MilestoneResponse,
    MilestoneList,
)
from app.schemas.typed_dicts import (
    # Market types
    MarketIndexPoint,
    MarketIndexResponse,
    MarketOverviewResponse,
    TopMoverItem,
    TopMoversResponse,
    VolumeDataPoint,
    FormatVolumeData,
    VolumeByFormatResponse,
    ColorDistributionResponse,
    MarketDiagnosticsResponse,
    # Price snapshot types
    PriceSnapshotKey,
    PriceSnapshotData,
    PriceSnapshotQueryResult,
    # Card types
    CardBasicInfo,
    MarketplacePriceInfo,
    CardPricesResponse,
    PriceHistoryPoint,
    CardHistoryDict,
    # Dashboard types
    DashboardTopCard,
    DashboardSpread,
    DashboardSummaryResponse,
    # WebSocket types
    WebSocketMessageBase,
    MarketUpdateMessage,
    CardUpdateMessage,
    DashboardUpdateMessage,
    InventoryUpdateMessage,
    RecommendationsUpdateMessage,
    # Inventory types
    InventoryItemInfo,
    InventoryListDict,
    InventoryAnalyticsResponse,
    # Task result types
    PriceCollectionResult,
    InventoryPriceCollectionResult,
    MTGJSONImportResult,
    VectorizationResult,
)

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
    # Inventory schemas
    "InventoryCondition",
    "InventoryUrgency",
    "InventoryImportRequest",
    "InventoryImportResponse",
    "ImportedItem",
    "InventoryItemBase",
    "InventoryItemCreate",
    "InventoryItemUpdate",
    "InventoryItemResponse",
    "InventoryListResponse",
    "InventoryAnalytics",
    "InventoryRecommendationResponse",
    "InventoryRecommendationListResponse",
    # Sets schemas
    "MTGSetResponse",
    "MTGSetList",
    "SetSearchQuery",
    # Want List schemas
    "WantListPriority",
    "CardSummary",
    "WantListItemBase",
    "WantListItemCreate",
    "WantListItemUpdate",
    "WantListItemResponse",
    "WantListListResponse",
    # Notification schemas
    "NotificationResponse",
    "NotificationUpdate",
    "NotificationList",
    "UnreadCountResponse",
    # Collection schemas
    "CollectionStatsResponse",
    "SetCompletion",
    "SetCompletionList",
    "MilestoneResponse",
    "MilestoneList",
    # TypedDict schemas - Market
    "MarketIndexPoint",
    "MarketIndexResponse",
    "MarketOverviewResponse",
    "TopMoverItem",
    "TopMoversResponse",
    "VolumeDataPoint",
    "FormatVolumeData",
    "VolumeByFormatResponse",
    "ColorDistributionResponse",
    "MarketDiagnosticsResponse",
    # TypedDict schemas - Price Snapshot
    "PriceSnapshotKey",
    "PriceSnapshotData",
    "PriceSnapshotQueryResult",
    # TypedDict schemas - Card
    "CardBasicInfo",
    "MarketplacePriceInfo",
    "CardPricesResponse",
    "PriceHistoryPoint",
    "CardHistoryDict",
    # TypedDict schemas - Dashboard
    "DashboardTopCard",
    "DashboardSpread",
    "DashboardSummaryResponse",
    # TypedDict schemas - WebSocket
    "WebSocketMessageBase",
    "MarketUpdateMessage",
    "CardUpdateMessage",
    "DashboardUpdateMessage",
    "InventoryUpdateMessage",
    "RecommendationsUpdateMessage",
    # TypedDict schemas - Inventory
    "InventoryItemInfo",
    "InventoryListDict",
    "InventoryAnalyticsResponse",
    # TypedDict schemas - Task Results
    "PriceCollectionResult",
    "InventoryPriceCollectionResult",
    "MTGJSONImportResult",
    "VectorizationResult",
]

