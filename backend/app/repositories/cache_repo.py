"""
Cache repository for Redis operations.

This repository provides a clean interface for caching data in Redis,
with support for TTL, pattern-based invalidation, and the get-or-compute
pattern commonly used in web applications.
"""
import json
from datetime import timedelta
from typing import Any, Callable, TypeVar, Awaitable

from redis.asyncio import Redis
from redis.exceptions import RedisError

import structlog

logger = structlog.get_logger()

T = TypeVar("T")


class CacheRepository:
    """
    Repository for Redis caching operations.

    Provides:
    - Get/set with automatic JSON serialization
    - TTL management
    - Pattern-based invalidation
    - Resilient get-or-compute pattern
    """

    def __init__(self, redis: Redis, default_ttl: timedelta = timedelta(minutes=5)):
        """
        Initialize the cache repository.

        Args:
            redis: Redis client instance
            default_ttl: Default TTL for cached values
        """
        self.redis = redis
        self.default_ttl = default_ttl

    def _key(self, *parts: str) -> str:
        """Build a cache key from parts."""
        return "cache:" + ":".join(str(p) for p in parts)

    async def get(self, *key_parts: str) -> Any | None:
        """
        Get a cached value.

        Args:
            *key_parts: Parts of the cache key

        Returns:
            Cached value or None if not found
        """
        try:
            key = self._key(*key_parts)
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except RedisError as e:
            logger.warning("Cache get failed", key=key_parts, error=str(e))
            return None
        except json.JSONDecodeError as e:
            logger.warning("Cache decode failed", key=key_parts, error=str(e))
            return None

    async def set(
        self,
        *key_parts: str,
        value: Any,
        ttl: timedelta | None = None,
    ) -> bool:
        """
        Set a cached value.

        Args:
            *key_parts: Parts of the cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live (uses default if not specified)

        Returns:
            True if successful, False otherwise
        """
        try:
            key = self._key(*key_parts)
            ttl_seconds = int((ttl or self.default_ttl).total_seconds())
            serialized = json.dumps(value, default=str)
            await self.redis.setex(key, ttl_seconds, serialized)
            return True
        except RedisError as e:
            logger.warning("Cache set failed", key=key_parts, error=str(e))
            return False
        except (TypeError, ValueError) as e:
            logger.warning("Cache serialize failed", key=key_parts, error=str(e))
            return False

    async def delete(self, *key_parts: str) -> bool:
        """
        Delete a cached value.

        Args:
            *key_parts: Parts of the cache key

        Returns:
            True if the key was deleted, False otherwise
        """
        try:
            key = self._key(*key_parts)
            result = await self.redis.delete(key)
            return result > 0
        except RedisError as e:
            logger.warning("Cache delete failed", key=key_parts, error=str(e))
            return False

    async def get_or_compute(
        self,
        key_parts: tuple[str, ...],
        compute_fn: Callable[[], Awaitable[T]],
        ttl: timedelta | None = None,
    ) -> T:
        """
        Get cached value or compute and cache it.

        This is the primary caching pattern. It:
        1. Tries to get from cache
        2. If cache miss, calls compute_fn to get the value
        3. Caches the result
        4. Returns the value

        If Redis is unavailable, it falls back to computing without caching.

        Args:
            key_parts: Tuple of cache key parts
            compute_fn: Async function to compute the value if not cached
            ttl: Optional TTL override

        Returns:
            The cached or computed value
        """
        # Try to get from cache
        cached = await self.get(*key_parts)
        if cached is not None:
            return cached

        # Compute the value
        result = await compute_fn()

        # Try to cache it (don't fail if caching fails)
        await self.set(*key_parts, value=result, ttl=ttl)

        return result

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.

        Args:
            pattern: Glob pattern to match (e.g., "market:*")

        Returns:
            Number of keys deleted
        """
        try:
            full_pattern = f"cache:{pattern}"
            keys = []
            async for key in self.redis.scan_iter(match=full_pattern):
                keys.append(key)

            if keys:
                return await self.redis.delete(*keys)
            return 0
        except RedisError as e:
            logger.warning("Cache invalidate pattern failed", pattern=pattern, error=str(e))
            return 0

    async def invalidate_card(self, card_id: int) -> int:
        """
        Invalidate all cached data for a specific card.

        Args:
            card_id: ID of the card

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern(f"card:{card_id}:*")

    async def invalidate_market(self) -> int:
        """
        Invalidate all market-related cached data.

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern("market:*")

    async def invalidate_dashboard(self, currency: str | None = None) -> int:
        """
        Invalidate dashboard cached data.

        Args:
            currency: Optional currency to narrow invalidation

        Returns:
            Number of keys deleted
        """
        if currency:
            return await self.invalidate_pattern(f"dashboard:*:{currency}")
        return await self.invalidate_pattern("dashboard:*")

    async def invalidate_recommendations(self) -> int:
        """
        Invalidate recommendations cached data.

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern("recommendations:*")

    async def invalidate_all(self) -> int:
        """
        Invalidate all cached data.

        Use with caution - this clears the entire cache.

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_pattern("*")

    async def get_ttl(self, *key_parts: str) -> int | None:
        """
        Get the remaining TTL for a cached value.

        Args:
            *key_parts: Parts of the cache key

        Returns:
            Remaining TTL in seconds, or None if key doesn't exist
        """
        try:
            key = self._key(*key_parts)
            ttl = await self.redis.ttl(key)
            return ttl if ttl >= 0 else None
        except RedisError:
            return None

    async def exists(self, *key_parts: str) -> bool:
        """
        Check if a key exists in cache.

        Args:
            *key_parts: Parts of the cache key

        Returns:
            True if key exists
        """
        try:
            key = self._key(*key_parts)
            return await self.redis.exists(key) > 0
        except RedisError:
            return False
