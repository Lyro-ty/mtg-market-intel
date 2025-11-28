"""
Base classes for marketplace adapters.

Defines the interface that all marketplace adapters must implement.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AdapterConfig:
    """Configuration for a marketplace adapter."""
    base_url: str
    api_url: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    rate_limit_seconds: float = 1.0
    max_retries: int = 3
    backoff_factor: float = 2.0
    timeout_seconds: float = 30.0
    user_agent: str = "MTGMarketIntel/1.0"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CardListing:
    """Represents a card listing from a marketplace."""
    # Required fields (no defaults) - must come first
    card_name: str
    set_code: str
    collector_number: str
    price: float
    
    # Optional fields (with defaults)
    scryfall_id: str | None = None
    currency: str = "USD"
    quantity: int = 1
    condition: str | None = None
    language: str = "English"
    is_foil: bool = False
    
    # Seller info
    seller_name: str | None = None
    seller_rating: float | None = None
    
    # External reference
    external_id: str | None = None
    listing_url: str | None = None
    
    # Timestamps
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    
    # Raw data for debugging
    raw_data: dict[str, Any] | None = None


@dataclass
class CardPrice:
    """Aggregated price data for a card."""
    # Required fields first (no defaults)
    card_name: str
    set_code: str
    collector_number: str
    price: float  # Representative/market price
    
    # Optional fields (with defaults)
    scryfall_id: str | None = None
    currency: str = "USD"
    
    # Price variants
    price_low: float | None = None
    price_mid: float | None = None
    price_high: float | None = None
    price_market: float | None = None
    price_foil: float | None = None
    
    # Market data
    num_listings: int | None = None
    total_quantity: int | None = None
    
    # Timestamp
    snapshot_time: datetime = field(default_factory=datetime.utcnow)


class MarketplaceAdapter(ABC):
    """
    Abstract base class for marketplace adapters.
    
    Each marketplace should implement this interface to standardize
    data collection across different sources.
    """
    
    def __init__(self, config: AdapterConfig):
        """
        Initialize the adapter with configuration.
        
        Args:
            config: Adapter configuration including URLs and credentials.
        """
        self.config = config
        self._last_request_time: datetime | None = None
    
    @property
    @abstractmethod
    def marketplace_name(self) -> str:
        """Return the marketplace name."""
        pass
    
    @property
    @abstractmethod
    def marketplace_slug(self) -> str:
        """Return the marketplace slug (lowercase, no spaces)."""
        pass
    
    @property
    def supports_api(self) -> bool:
        """Return whether this adapter uses an official API."""
        return self.config.api_url is not None
    
    @abstractmethod
    async def fetch_listings(
        self,
        card_name: str | None = None,
        set_code: str | None = None,
        scryfall_id: str | None = None,
        limit: int = 100,
    ) -> list[CardListing]:
        """
        Fetch current listings from the marketplace.
        
        Args:
            card_name: Filter by card name.
            set_code: Filter by set code.
            scryfall_id: Filter by Scryfall ID.
            limit: Maximum number of listings to return.
            
        Returns:
            List of CardListing objects.
        """
        pass
    
    @abstractmethod
    async def fetch_price(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
    ) -> CardPrice | None:
        """
        Fetch aggregated price data for a specific card.
        
        Args:
            card_name: Card name.
            set_code: Set code.
            collector_number: Collector number within the set.
            scryfall_id: Scryfall ID for exact matching.
            
        Returns:
            CardPrice object or None if not found.
        """
        pass
    
    async def fetch_price_history(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
        days: int = 30,
    ) -> list[CardPrice]:
        """
        Fetch price history for a card (if available).
        
        Not all marketplaces support historical data.
        Default implementation returns empty list.
        
        Args:
            card_name: Card name.
            set_code: Set code.
            collector_number: Collector number.
            scryfall_id: Scryfall ID.
            days: Number of days of history.
            
        Returns:
            List of CardPrice objects ordered by time.
        """
        return []
    
    @abstractmethod
    async def search_cards(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Search for cards by name/query.
        
        Args:
            query: Search query string.
            limit: Maximum results to return.
            
        Returns:
            List of card info dictionaries.
        """
        pass
    
    async def health_check(self) -> bool:
        """
        Check if the marketplace is reachable.
        
        Returns:
            True if healthy, False otherwise.
        """
        return True
    
    def normalize_condition(self, condition: str) -> str:
        """
        Normalize condition strings to a standard format.
        
        Args:
            condition: Raw condition string from marketplace.
            
        Returns:
            Normalized condition string.
        """
        condition_map = {
            # Near Mint variations
            "nm": "NM", "near mint": "NM", "nm-m": "NM", "mint": "NM",
            # Lightly Played
            "lp": "LP", "light play": "LP", "lightly played": "LP", "sp": "LP",
            # Moderately Played
            "mp": "MP", "moderately played": "MP", "played": "MP",
            # Heavily Played
            "hp": "HP", "heavily played": "HP", "heavy play": "HP",
            # Damaged
            "dmg": "DMG", "damaged": "DMG", "poor": "DMG",
        }
        normalized = condition_map.get(condition.lower().strip(), condition.upper())
        return normalized
    
    def normalize_language(self, language: str) -> str:
        """
        Normalize language strings to a standard format.
        
        Args:
            language: Raw language string.
            
        Returns:
            Normalized language string.
        """
        language_map = {
            "en": "English", "eng": "English", "english": "English",
            "jp": "Japanese", "ja": "Japanese", "japanese": "Japanese",
            "de": "German", "ger": "German", "german": "German",
            "fr": "French", "fre": "French", "french": "French",
            "it": "Italian", "ita": "Italian", "italian": "Italian",
            "es": "Spanish", "spa": "Spanish", "spanish": "Spanish",
            "pt": "Portuguese", "por": "Portuguese", "portuguese": "Portuguese",
            "kr": "Korean", "ko": "Korean", "korean": "Korean",
            "cn": "Chinese Simplified", "zhs": "Chinese Simplified",
            "tw": "Chinese Traditional", "zht": "Chinese Traditional",
            "ru": "Russian", "rus": "Russian", "russian": "Russian",
        }
        return language_map.get(language.lower().strip(), language.title())

