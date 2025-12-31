"""
SQLAlchemy models for the MTG Market Intel application.

Note: The Listing model is DEPRECATED and should not be used for new code.
Use PriceSnapshot instead, which stores price data with full variant tracking
(condition, language, foil status) as part of a TimescaleDB hypertable.

The Listing model is kept for backward compatibility during migration.
"""
import warnings

# Import Listing first since Card has a relationship to it
from app.models.listing import Listing as _Listing
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
from app.models.session import UserSession
from app.models.want_list import WantListItem
from app.models.notification import Notification, NotificationType, NotificationPriority
from app.models.mtg_set import MTGSet
from app.models.collection_stats import CollectionStats
from app.models.user_milestone import UserMilestone, MilestoneType
from app.models.import_job import ImportJob, ImportPlatform, ImportStatus
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.saved_search import SavedSearch, SearchAlertFrequency


# DEPRECATED: Listing model - use PriceSnapshot instead
# Kept for backward compatibility during migration period
def _get_listing():
    """Get the deprecated Listing model with a deprecation warning."""
    warnings.warn(
        "Listing model is deprecated. Use PriceSnapshot instead, which supports "
        "condition, language, and foil tracking with TimescaleDB hypertable.",
        DeprecationWarning,
        stacklevel=3
    )
    from app.models.listing import Listing
    return Listing




# Lazy imports for deprecated models
# These emit warnings when accessed
class _DeprecatedListing:
    """Proxy for deprecated Listing model."""
    _model = None

    def __getattr__(self, name):
        if self._model is None:
            self._model = _get_listing()
        return getattr(self._model, name)

    def __call__(self, *args, **kwargs):
        if self._model is None:
            self._model = _get_listing()
        return self._model(*args, **kwargs)


# Expose deprecated models via proxies (emit warnings on use)
Listing = _DeprecatedListing()


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
    # Deprecated models (emit warnings when used)
    "Listing",  # DEPRECATED: Use PriceSnapshot
]

