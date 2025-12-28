"""
Repository layer for data access.

Repositories provide a clean abstraction over the database,
hiding the details of SQL queries and ORM operations from
the use case layer.
"""
from app.repositories.base import BaseRepository
from app.repositories.price_repo import PriceRepository
from app.repositories.card_repo import CardRepository
from app.repositories.market_repo import MarketRepository
from app.repositories.cache_repo import CacheRepository
from app.repositories.signal_repo import SignalRepository
from app.repositories.inventory_repo import InventoryRepository
from app.repositories.recommendation_repo import RecommendationRepository
from app.repositories.settings_repo import SettingsRepository

__all__ = [
    "BaseRepository",
    "PriceRepository",
    "CardRepository",
    "MarketRepository",
    "CacheRepository",
    "SignalRepository",
    "InventoryRepository",
    "RecommendationRepository",
    "SettingsRepository",
]
