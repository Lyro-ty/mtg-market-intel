"""
Base classes for marketplace adapters.

Defines the interface that all marketplace adapters must implement,
including standardized data classes for price data ingestion.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.constants import (
    CardCondition,
    CardLanguage,
    normalize_condition,
    normalize_language,
    get_currency_for_marketplace,
)


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
    timeout_seconds: float = float(settings.external_api_timeout)  # From centralized config
    user_agent: str = "MTGMarketIntel/1.0"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PriceData:
    """
    Standardized price data for ingestion into TimescaleDB.

    This dataclass represents the normalized format used to insert
    price snapshots into the database. All adapters should convert
    their raw data to this format.

    Attributes:
        card_id: Database ID of the card
        marketplace_id: Database ID of the marketplace
        time: Timestamp of the price snapshot
        price: Current/representative price
        currency: Currency code (USD, EUR)
        condition: Normalized card condition
        is_foil: Whether this is a foil variant
        language: Normalized card language
        price_low: Low price tier
        price_mid: Mid price tier
        price_high: High price tier
        price_market: Market price (if available)
        num_listings: Number of active listings
        total_quantity: Total quantity available
    """
    # Required fields
    card_id: int
    marketplace_id: int
    price: float
    currency: str

    # Optional fields with defaults
    time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    condition: CardCondition = CardCondition.NEAR_MINT
    is_foil: bool = False
    language: CardLanguage = CardLanguage.ENGLISH
    price_low: float | None = None
    price_mid: float | None = None
    price_high: float | None = None
    price_market: float | None = None
    num_listings: int | None = None
    total_quantity: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return {
            "card_id": self.card_id,
            "marketplace_id": self.marketplace_id,
            "time": self.time.isoformat() if isinstance(self.time, datetime) else self.time,
            "price": self.price,
            "currency": self.currency,
            "condition": self.condition.value,
            "is_foil": self.is_foil,
            "language": self.language.value,
            "price_low": self.price_low,
            "price_mid": self.price_mid,
            "price_high": self.price_high,
            "price_market": self.price_market,
            "num_listings": self.num_listings,
            "total_quantity": self.total_quantity,
        }

    @classmethod
    def from_card_price(
        cls,
        card_price: "CardPrice",
        card_id: int,
        marketplace_id: int,
        condition: CardCondition = CardCondition.NEAR_MINT,
        is_foil: bool = False,
        language: CardLanguage = CardLanguage.ENGLISH,
    ) -> "PriceData":
        """Create PriceData from a CardPrice object."""
        return cls(
            card_id=card_id,
            marketplace_id=marketplace_id,
            price=card_price.price,
            currency=card_price.currency,
            time=card_price.snapshot_time,
            condition=condition,
            is_foil=is_foil,
            language=language,
            price_low=card_price.price_low,
            price_mid=card_price.price_mid,
            price_high=card_price.price_high,
            price_market=card_price.price_market,
            num_listings=card_price.num_listings,
            total_quantity=card_price.total_quantity,
        )


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
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
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
    snapshot_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


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
    
    def normalize_condition(self, condition: str | None) -> CardCondition:
        """
        Normalize condition strings to CardCondition enum.

        Uses the centralized normalization from app.core.constants.

        Args:
            condition: Raw condition string from marketplace.

        Returns:
            CardCondition enum value.
        """
        return normalize_condition(condition)

    def normalize_language(self, language: str | None) -> CardLanguage:
        """
        Normalize language strings to CardLanguage enum.

        Uses the centralized normalization from app.core.constants.

        Args:
            language: Raw language string.

        Returns:
            CardLanguage enum value.
        """
        return normalize_language(language)

    def get_default_currency(self) -> str:
        """
        Get the default currency for this marketplace.

        Returns:
            Currency code (USD, EUR, etc.)
        """
        return get_currency_for_marketplace(self.marketplace_slug)

    def to_price_data(
        self,
        card_price: CardPrice,
        card_id: int,
        marketplace_id: int,
        condition: str | None = None,
        is_foil: bool = False,
        language: str | None = None,
    ) -> PriceData:
        """
        Convert a CardPrice to PriceData with proper normalization.

        Args:
            card_price: Raw price data from adapter
            card_id: Database card ID
            marketplace_id: Database marketplace ID
            condition: Raw condition string (will be normalized)
            is_foil: Foil status
            language: Raw language string (will be normalized)

        Returns:
            PriceData ready for database insertion
        """
        return PriceData.from_card_price(
            card_price=card_price,
            card_id=card_id,
            marketplace_id=marketplace_id,
            condition=self.normalize_condition(condition),
            is_foil=is_foil,
            language=self.normalize_language(language),
        )

