"""
Simple in-memory cache for dashboard and frequently accessed data.
"""
import time
from typing import Any, Optional
from collections import OrderedDict

import structlog

logger = structlog.get_logger()


class SimpleCache:
    """
    Simple in-memory cache with TTL (time-to-live).
    
    Uses LRU eviction when cache size limit is reached.
    """
    
    def __init__(self, max_size: int = 100, default_ttl: int = 300):
        """
        Initialize cache.
        
        Args:
            max_size: Maximum number of items to cache.
            default_ttl: Default time-to-live in seconds.
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key.
            
        Returns:
            Cached value or None if not found/expired.
        """
        if key not in self._cache:
            return None
        
        value, expiry = self._cache[key]
        
        # Check if expired
        if time.time() > expiry:
            del self._cache[key]
            return None
        
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key.
            value: Value to cache.
            ttl: Time-to-live in seconds. Uses default if None.
        """
        if ttl is None:
            ttl = self.default_ttl
        
        expiry = time.time() + ttl
        
        # Remove if exists
        if key in self._cache:
            del self._cache[key]
        
        # Evict oldest if at capacity
        if len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)  # Remove oldest
        
        self._cache[key] = (value, expiry)
    
    def clear(self) -> None:
        """Clear all cached items."""
        self._cache.clear()
    
    def delete(self, key: str) -> None:
        """Delete a specific key from cache."""
        if key in self._cache:
            del self._cache[key]


# Global cache instance
_dashboard_cache = SimpleCache(max_size=50, default_ttl=300)  # 5 minute TTL


def get_dashboard_cache() -> SimpleCache:
    """Get the dashboard cache instance."""
    return _dashboard_cache

