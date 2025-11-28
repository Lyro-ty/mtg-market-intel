"""
Adapter registry for marketplace adapters.

Provides a centralized way to access and manage adapters.
"""
import structlog
from typing import Type

from app.services.ingestion.base import MarketplaceAdapter, AdapterConfig
from app.services.ingestion.scryfall import ScryfallAdapter
from app.services.ingestion.adapters.tcgplayer import TCGPlayerAdapter
from app.services.ingestion.adapters.cardmarket import CardMarketAdapter
from app.services.ingestion.adapters.cardkingdom import CardKingdomAdapter
from app.services.ingestion.adapters.mock import MockMarketplaceAdapter

logger = structlog.get_logger()

# Registry of available adapters
_ADAPTER_REGISTRY: dict[str, Type[MarketplaceAdapter]] = {
    "scryfall": ScryfallAdapter,
    "tcgplayer": TCGPlayerAdapter,
    "cardmarket": CardMarketAdapter,
    "cardkingdom": CardKingdomAdapter,
    "mock": MockMarketplaceAdapter,
}

# Cached adapter instances
_ADAPTER_INSTANCES: dict[str, MarketplaceAdapter] = {}


def register_adapter(slug: str, adapter_class: Type[MarketplaceAdapter]) -> None:
    """
    Register a new adapter type.
    
    Args:
        slug: Unique identifier for the adapter.
        adapter_class: The adapter class to register.
    """
    _ADAPTER_REGISTRY[slug] = adapter_class
    logger.info("Registered marketplace adapter", slug=slug, adapter=adapter_class.__name__)


def get_adapter(
    slug: str,
    config: AdapterConfig | None = None,
    cached: bool = True,
) -> MarketplaceAdapter:
    """
    Get an adapter instance by slug.
    
    Args:
        slug: Adapter identifier.
        config: Optional custom configuration.
        cached: Whether to use/store cached instance.
        
    Returns:
        Adapter instance.
        
    Raises:
        ValueError: If slug is not registered.
    """
    slug = slug.lower()
    
    if slug not in _ADAPTER_REGISTRY:
        raise ValueError(f"Unknown adapter: {slug}. Available: {list(_ADAPTER_REGISTRY.keys())}")
    
    # Return cached instance if available
    if cached and slug in _ADAPTER_INSTANCES and config is None:
        return _ADAPTER_INSTANCES[slug]
    
    # Create new instance
    adapter_class = _ADAPTER_REGISTRY[slug]
    if config:
        instance = adapter_class(config)
    else:
        instance = adapter_class()
    
    # Cache if requested
    if cached and config is None:
        _ADAPTER_INSTANCES[slug] = instance
    
    return instance


def get_all_adapters(
    exclude_scryfall: bool = True,
    enabled_only: list[str] | None = None,
) -> list[MarketplaceAdapter]:
    """
    Get all registered adapter instances.
    
    Args:
        exclude_scryfall: Whether to exclude Scryfall (it's not a marketplace).
        enabled_only: If provided, only return adapters with these slugs.
        
    Returns:
        List of adapter instances.
    """
    adapters = []
    
    for slug in _ADAPTER_REGISTRY:
        if exclude_scryfall and slug == "scryfall":
            continue
        
        if enabled_only is not None and slug not in enabled_only:
            continue
        
        adapters.append(get_adapter(slug))
    
    return adapters


def get_available_adapters() -> list[str]:
    """Get list of available adapter slugs."""
    return list(_ADAPTER_REGISTRY.keys())


async def close_all_adapters() -> None:
    """Close all cached adapter instances."""
    for slug, adapter in _ADAPTER_INSTANCES.items():
        if hasattr(adapter, 'close'):
            await adapter.close()
    _ADAPTER_INSTANCES.clear()

