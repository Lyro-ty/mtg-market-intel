"""
SQLAlchemy models for the MTG Market Intel application.

Price data is stored in PriceSnapshot, which stores price data with full variant
tracking (condition, language, foil status) as part of a TimescaleDB hypertable.
"""

from app.models.card import Card
from app.models.marketplace import Marketplace
from app.models.price_snapshot import PriceSnapshot
from app.models.metrics import MetricsCardsDaily
from app.models.signal import Signal
from app.models.recommendation import Recommendation, ActionType
from app.models.settings import AppSettings
from app.models.inventory import InventoryItem, InventoryRecommendation, InventoryCondition
from app.models.user import User
from app.models.feature_vector import CardFeatureVector
from app.models.tournament import (
    Tournament,
    TournamentStanding,
    Decklist,
    DecklistCard,
    CardMetaStats,
)
from app.models.news import NewsArticle, CardNewsMention
from app.models.buylist_snapshot import BuylistSnapshot
from app.models.legality import LegalityChange
from app.models.session import UserSession
from app.models.want_list import WantListItem
from app.models.notification import Notification, NotificationType, NotificationPriority
from app.models.mtg_set import MTGSet
from app.models.collection_stats import CollectionStats
from app.models.user_milestone import UserMilestone, MilestoneType
from app.models.import_job import ImportJob, ImportPlatform, ImportStatus
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.saved_search import SavedSearch, SearchAlertFrequency
from app.models.connection import (
    ConnectionRequest,
    Message,
    UserEndorsement,
    BlockedUser,
    UserReport,
)
from app.models.discord_alert import DiscordAlertQueue
from app.models.trading_post import (
    TradingPost,
    TradeQuote,
    TradeQuoteItem,
    TradeQuoteSubmission,
    TradingPostEvent,
    QuoteStatus,
    SubmissionStatus,
    EventType,
)
from app.models.reputation import (
    UserReputation,
    ReputationReview,
    ReputationTier,
)
from app.models.trade import (
    TradeProposal,
    TradeProposalItem,
    TradeStatus,
    TradeSide,
)


__all__ = [
    # Active models
    "Card",
    "Marketplace",
    "PriceSnapshot",
    "MetricsCardsDaily",
    "Signal",
    "Recommendation",
    "ActionType",
    "AppSettings",
    "InventoryItem",
    "InventoryRecommendation",
    "InventoryCondition",
    "User",
    "CardFeatureVector",
    "Tournament",
    "TournamentStanding",
    "Decklist",
    "DecklistCard",
    "CardMetaStats",
    "UserSession",
    "WantListItem",
    "Notification",
    "NotificationType",
    "NotificationPriority",
    "MTGSet",
    "CollectionStats",
    "UserMilestone",
    "MilestoneType",
    "ImportJob",
    "ImportPlatform",
    "ImportStatus",
    "PortfolioSnapshot",
    "SavedSearch",
    "SearchAlertFrequency",
    "NewsArticle",
    "CardNewsMention",
    "BuylistSnapshot",
    "LegalityChange",
    # Connection models
    "ConnectionRequest",
    "Message",
    "UserEndorsement",
    "BlockedUser",
    "UserReport",
    # Discord integration
    "DiscordAlertQueue",
    # Trading Posts (LGS)
    "TradingPost",
    "TradeQuote",
    "TradeQuoteItem",
    "TradeQuoteSubmission",
    "TradingPostEvent",
    "QuoteStatus",
    "SubmissionStatus",
    "EventType",
    # Reputation system
    "UserReputation",
    "ReputationReview",
    "ReputationTier",
    # Trade proposals
    "TradeProposal",
    "TradeProposalItem",
    "TradeStatus",
    "TradeSide",
]

