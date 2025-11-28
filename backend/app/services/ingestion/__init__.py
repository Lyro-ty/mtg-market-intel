"""
Ingestion service for marketplace data collection.

Provides adapter interfaces and implementations for various MTG marketplaces.
"""
from app.services.ingestion.base import (
    MarketplaceAdapter,
    CardListing,
    CardPrice,
    AdapterConfig,
)
from app.services.ingestion.scryfall import ScryfallAdapter
from app.services.ingestion.registry import get_adapter, get_all_adapters, register_adapter

__all__ = [
    "MarketplaceAdapter",
    "CardListing",
    "CardPrice",
    "AdapterConfig",
    "ScryfallAdapter",
    "get_adapter",
    "get_all_adapters",
    "register_adapter",
]

