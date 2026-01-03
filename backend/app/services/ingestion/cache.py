"""
Snapshot cache for ingestion optimization.

Provides a Redis cache-aside layer to track recently updated cards,
reducing database queries during price collection.
"""
from datetime import datetime, timezone
from typing import Optional

from redis.asyncio import Redis
from redis.exceptions import RedisError

import structlog

logger = structlog.get_logger()


class SnapshotCache:
    """
    Cache-aside for recent snapshot timestamps.

    Tracks when cards were last updated per marketplace to avoid
    unnecessary database queries and API calls during ingestion.

    Usage:
        cache = SnapshotCache(redis_client)

        # Check which cards were recently updated (skip these)
        recently_updated = await cache.get_recently_updated(card_ids, marketplace_id)
        cards_to_fetch = [cid for cid in card_ids if cid not in recently_updated]

        # After writing snapshots, mark cards as updated
        await cache.mark_updated(cards_to_fetch, marketplace_id)
    """

    PREFIX = "snapshot:last:"
    DEFAULT_TTL = 7200  # 2 hours (matches our update window)

    def __init__(self, redis: Redis):
        """
        Initialize the snapshot cache.

        Args:
            redis: Async Redis client instance
        """
        self.redis = redis

    def _key(self, marketplace_id: int, card_id: int) -> str:
        """Build a cache key for a card/marketplace pair."""
        return f"{self.PREFIX}{marketplace_id}:{card_id}"

    async def get_recently_updated(
        self,
        card_ids: list[int],
        marketplace_id: int,
    ) -> set[int]:
        """
        Returns card_ids that were updated within TTL window.

        Uses Redis MGET for efficient batch lookup.

        Args:
            card_ids: List of card IDs to check
            marketplace_id: ID of the marketplace

        Returns:
            Set of card_ids that were recently updated (should be skipped)
        """
        if not card_ids:
            return set()

        try:
            keys = [self._key(marketplace_id, cid) for cid in card_ids]
            values = await self.redis.mget(keys)

            return {
                card_ids[i]
                for i, v in enumerate(values)
                if v is not None
            }
        except RedisError as e:
            logger.warning(
                "Redis cache lookup failed, falling back to DB",
                marketplace_id=marketplace_id,
                card_count=len(card_ids),
                error=str(e),
            )
            return set()

    async def mark_updated(
        self,
        card_ids: list[int],
        marketplace_id: int,
        ttl: int = DEFAULT_TTL,
    ) -> bool:
        """
        Mark cards as recently updated.

        Uses Redis pipeline for efficient batch writes.

        Args:
            card_ids: List of card IDs that were updated
            marketplace_id: ID of the marketplace
            ttl: Time-to-live in seconds (default 2 hours)

        Returns:
            True if successful, False if Redis failed
        """
        if not card_ids:
            return True

        try:
            now = datetime.now(timezone.utc).isoformat()
            pipe = self.redis.pipeline()

            for cid in card_ids:
                key = self._key(marketplace_id, cid)
                pipe.setex(key, ttl, now)

            await pipe.execute()
            return True

        except RedisError as e:
            logger.warning(
                "Redis cache update failed",
                marketplace_id=marketplace_id,
                card_count=len(card_ids),
                error=str(e),
            )
            return False

    async def get_last_update(
        self,
        card_id: int,
        marketplace_id: int,
    ) -> Optional[datetime]:
        """
        Get the last update timestamp for a specific card.

        Args:
            card_id: Card ID to check
            marketplace_id: ID of the marketplace

        Returns:
            Datetime of last update, or None if not in cache
        """
        try:
            key = self._key(marketplace_id, card_id)
            value = await self.redis.get(key)

            if value:
                return datetime.fromisoformat(value)
            return None

        except (RedisError, ValueError) as e:
            logger.debug(
                "Cache get failed",
                card_id=card_id,
                marketplace_id=marketplace_id,
                error=str(e),
            )
            return None

    async def invalidate(
        self,
        card_ids: list[int],
        marketplace_id: int,
    ) -> int:
        """
        Invalidate cache entries for specific cards.

        Useful when forcing a refresh of price data.

        Args:
            card_ids: List of card IDs to invalidate
            marketplace_id: ID of the marketplace

        Returns:
            Number of keys deleted
        """
        if not card_ids:
            return 0

        try:
            keys = [self._key(marketplace_id, cid) for cid in card_ids]
            return await self.redis.delete(*keys)

        except RedisError as e:
            logger.warning(
                "Cache invalidation failed",
                marketplace_id=marketplace_id,
                card_count=len(card_ids),
                error=str(e),
            )
            return 0

    async def invalidate_marketplace(self, marketplace_id: int) -> int:
        """
        Invalidate all cache entries for a marketplace.

        Args:
            marketplace_id: ID of the marketplace to clear

        Returns:
            Number of keys deleted
        """
        try:
            pattern = f"{self.PREFIX}{marketplace_id}:*"
            keys = []
            async for key in self.redis.scan_iter(match=pattern, count=1000):
                keys.append(key)

            if keys:
                return await self.redis.delete(*keys)
            return 0

        except RedisError as e:
            logger.warning(
                "Marketplace cache invalidation failed",
                marketplace_id=marketplace_id,
                error=str(e),
            )
            return 0
