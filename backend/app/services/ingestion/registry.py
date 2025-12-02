"""
Adapter registry for marketplace adapters.

Provides a centralized way to access and manage adapters.

NOTE: Adapter caching is disabled by default because HTTP clients (httpx/aiohttp)
are bound to the event loop they were created in. In Celery workers, each task
runs in a new event loop, so reusing cached adapters causes "Event loop is closed" errors.
"""
import structlog
from typing import Type

from app.services.ingestion.base import MarketplaceAdapter, AdapterConfig
from app.services.ingestion.scryfall import ScryfallAdapter
from app.services.ingestion.adapters.tcgplayer import TCGPlayerAdapter
from app.services.ingestion.adapters.cardmarket import CardMarketAdapter
from app.services.ingestion.adapters.cardkingdom import CardKingdomAdapter
from app.services.ingestion.adapters.mtgjson import MTGJSONAdapter
from app.services.ingestion.adapters.mock import MockMarketplaceAdapter

logger = structlog.get_logger()

# Registry of available adapters
_ADAPTER_REGISTRY: dict[str, Type[MarketplaceAdapter]] = {
    "scryfall": ScryfallAdapter,
    "tcgplayer": TCGPlayerAdapter,
    "cardmarket": CardMarketAdapter,
    "cardkingdom": CardKingdomAdapter,
    "mtgjson": MTGJSONAdapter,
    "mock": MockMarketplaceAdapter,
}

# Cached adapter instances - DISABLED by default due to event loop issues
# Only use caching in long-running processes with a single event loop (e.g., FastAPI)
_ADAPTER_INSTANCES: dict[str, MarketplaceAdapter] = {}
_CACHING_ENABLED: bool = False  # Set to True only in FastAPI startup


def register_adapter(slug: str, adapter_class: Type[MarketplaceAdapter]) -> None:
    """
    Register a new adapter type.
    
    Args:
        slug: Unique identifier for the adapter.
        adapter_class: The adapter class to register.
    """
    _ADAPTER_REGISTRY[slug] = adapter_class
    logger.info("Registered marketplace adapter", slug=slug, adapter=adapter_class.__name__)


def enable_adapter_caching(enabled: bool = True) -> None:
    """
    Enable or disable adapter caching.
    
    Should only be enabled in long-running processes with a single event loop
    (e.g., FastAPI). Must be disabled in Celery workers where each task
    runs in a new event loop.
    
    Args:
        enabled: Whether to enable caching.
    """
    global _CACHING_ENABLED
    _CACHING_ENABLED = enabled
    if not enabled:
        _ADAPTER_INSTANCES.clear()
    logger.info("Adapter caching", enabled=enabled)


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
        cached: Whether to use/store cached instance (only works if caching is enabled globally).
        
    Returns:
        Adapter instance.
        
    Raises:
        ValueError: If slug is not registered.
    """
    slug = slug.lower()
    
    if slug not in _ADAPTER_REGISTRY:
        raise ValueError(f"Unknown adapter: {slug}. Available: {list(_ADAPTER_REGISTRY.keys())}")
    
    # Only use cache if both global caching is enabled AND caller requests it
    use_cache = _CACHING_ENABLED and cached and config is None
    
    # Return cached instance if available
    if use_cache and slug in _ADAPTER_INSTANCES:
        return _ADAPTER_INSTANCES[slug]
    
    # Create new instance
    adapter_class = _ADAPTER_REGISTRY[slug]
    if config:
        instance = adapter_class(config)
    else:
        instance = adapter_class()
    
    # Cache if requested and caching is enabled
    if use_cache:
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

