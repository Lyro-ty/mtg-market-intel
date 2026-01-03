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
from app.services.ingestion.cache import SnapshotCache
from app.services.ingestion.bulk_ops import (
    get_recent_snapshot_times,
    batch_upsert_snapshots,
    batch_upsert_snapshots_safe,
    bulk_copy_snapshots,
    prepare_copy_record,
)

__all__ = [
    # Base classes
    "MarketplaceAdapter",
    "CardListing",
    "CardPrice",
    "PriceData",
    "AdapterConfig",
    # Adapters
    "ScryfallAdapter",
    # Registry
    "get_adapter",
    "get_all_adapters",
    "get_available_adapters",
    "register_adapter",
    "enable_adapter_caching",
    # Cache
    "SnapshotCache",
    # Bulk operations
    "get_recent_snapshot_times",
    "batch_upsert_snapshots",
    "batch_upsert_snapshots_safe",
    "bulk_copy_snapshots",
    "prepare_copy_record",
]

