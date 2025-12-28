"""
Ingestion service for marketplace data collection.

Provides adapter interfaces and implementations for various MTG marketplaces.
"""
from app.services.ingestion.base import (
    MarketplaceAdapter,
    CardListing,
    CardPrice,
    PriceData,
    AdapterConfig,
)
from app.services.ingestion.scryfall import ScryfallAdapter
from app.services.ingestion.registry import (
    get_adapter,
    get_all_adapters,
    get_available_adapters,
    register_adapter,
    enable_adapter_caching,
)

__all__ = [
    "MarketplaceAdapter",
    "CardListing",
    "CardPrice",
    "PriceData",
    "AdapterConfig",
    "ScryfallAdapter",
    "get_adapter",
    "get_all_adapters",
    "get_available_adapters",
    "register_adapter",
    "enable_adapter_caching",
]

