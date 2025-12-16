"""
Token blacklist for secure JWT invalidation.

Implements a Redis-based token blacklist with in-memory fallback.
Tokens are stored with TTL matching their expiration to auto-cleanup.
"""
import time
from datetime import datetime, timezone
from typing import Optional

import structlog
import redis

from app.core.config import settings

logger = structlog.get_logger()


class TokenBlacklist:
    """
    Token blacklist implementation using Redis with in-memory fallback.

    Uses JTI (JWT ID) as the key and stores until token expiration.
    """

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._local_cache: dict[str, float] = {}  # jti -> expiry timestamp
        self._initialized = False

    def _get_redis(self) -> Optional[redis.Redis]:
        """Get Redis connection, initializing if needed."""
        if self._initialized:
            return self._redis

        try:
            self._redis = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            # Test connection
            self._redis.ping()
            logger.info("Token blacklist connected to Redis")
        except Exception as e:
            logger.warning(
                "Token blacklist Redis connection failed, using in-memory fallback",
                error=str(e)
            )
            self._redis = None

        self._initialized = True
        return self._redis

    def add(self, jti: str, expires_at: datetime) -> bool:
        """
        Add a token JTI to the blacklist.

        Args:
            jti: JWT ID (unique token identifier)
            expires_at: Token expiration time

        Returns:
            True if successfully blacklisted
        """
        # Calculate TTL
        now = datetime.now(timezone.utc)
        ttl_seconds = int((expires_at - now).total_seconds())

        if ttl_seconds <= 0:
            # Token already expired, no need to blacklist
            return True

        redis_client = self._get_redis()
        if redis_client:
            try:
                # Use Redis SET with EX (expiry)
                key = f"token_blacklist:{jti}"
                redis_client.setex(key, ttl_seconds, "1")
                logger.debug("Token blacklisted in Redis", jti=jti, ttl=ttl_seconds)
                return True
            except Exception as e:
                logger.warning("Failed to blacklist token in Redis", error=str(e))

        # Fallback to in-memory cache
        self._local_cache[jti] = time.time() + ttl_seconds
        self._cleanup_local_cache()
        logger.debug("Token blacklisted in memory", jti=jti, ttl=ttl_seconds)
        return True

    def is_blacklisted(self, jti: str) -> bool:
        """
        Check if a token JTI is blacklisted.

        Args:
            jti: JWT ID to check

        Returns:
            True if token is blacklisted
        """
        redis_client = self._get_redis()
        if redis_client:
            try:
                key = f"token_blacklist:{jti}"
                return redis_client.exists(key) > 0
            except Exception as e:
                logger.warning("Failed to check Redis blacklist", error=str(e))

        # Check in-memory cache
        if jti in self._local_cache:
            if time.time() < self._local_cache[jti]:
                return True
            else:
                # Expired, clean up
                del self._local_cache[jti]

        return False

    def _cleanup_local_cache(self) -> None:
        """Remove expired entries from local cache."""
        now = time.time()
        expired = [jti for jti, expiry in self._local_cache.items() if now >= expiry]
        for jti in expired:
            del self._local_cache[jti]


# Global blacklist instance
_token_blacklist = TokenBlacklist()


def get_token_blacklist() -> TokenBlacklist:
    """Get the token blacklist instance."""
    return _token_blacklist
