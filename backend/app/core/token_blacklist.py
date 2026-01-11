"""
Token blacklist for secure JWT invalidation.

Implements a Redis-based token blacklist. When Redis is unavailable,
operations fail secure - tokens are treated as potentially blacklisted.
"""
import structlog
from datetime import datetime, timezone
from typing import Optional

import redis

from app.core.config import settings

logger = structlog.get_logger()


class TokenBlacklist:
    """
    Token blacklist implementation using Redis.

    SECURITY: No in-memory fallback. When Redis is unavailable:
    - add() returns False (failed to blacklist)
    - is_blacklisted() returns True (fail secure - assume token invalid)
    """

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._initialized = False
        self._redis_available = False

    def _get_redis(self) -> Optional[redis.Redis]:
        """Get Redis connection, initializing if needed."""
        if self._initialized:
            return self._redis if self._redis_available else None

        try:
            self._redis = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            # Test connection
            self._redis.ping()
            self._redis_available = True
            logger.info("Token blacklist connected to Redis")
        except Exception as e:
            logger.error(
                "Token blacklist Redis connection failed - tokens will be treated as invalid",
                error=str(e)
            )
            self._redis = None
            self._redis_available = False

        self._initialized = True
        return self._redis if self._redis_available else None

    def add(self, jti: str, expires_at: datetime) -> bool:
        """
        Add a token JTI to the blacklist.

        Args:
            jti: JWT ID (unique token identifier)
            expires_at: Token expiration time

        Returns:
            True if successfully blacklisted, False if failed
        """
        # Calculate TTL
        now = datetime.now(timezone.utc)
        ttl_seconds = int((expires_at - now).total_seconds())

        if ttl_seconds <= 0:
            # Token already expired, no need to blacklist
            return True

        redis_client = self._get_redis()
        if not redis_client:
            logger.warning("Cannot blacklist token - Redis unavailable", jti=jti)
            return False

        try:
            key = f"token_blacklist:{jti}"
            redis_client.setex(key, ttl_seconds, "1")
            logger.debug("Token blacklisted in Redis", jti=jti, ttl=ttl_seconds)
            return True
        except Exception as e:
            logger.error("Failed to blacklist token in Redis", error=str(e), jti=jti)
            return False

    def is_blacklisted(self, jti: str) -> bool:
        """
        Check if a token JTI is blacklisted.

        SECURITY: Fails secure - if Redis unavailable, returns True
        (assumes token is blacklisted to prevent unauthorized access).

        Args:
            jti: JWT ID to check

        Returns:
            True if token is blacklisted OR if check failed (fail secure)
        """
        redis_client = self._get_redis()
        if not redis_client:
            # SECURITY: Fail secure - treat as blacklisted when we can't verify
            logger.warning(
                "Cannot verify token blacklist status - Redis unavailable, treating as blacklisted",
                jti=jti
            )
            return True

        try:
            key = f"token_blacklist:{jti}"
            return redis_client.exists(key) > 0
        except Exception as e:
            # SECURITY: Fail secure on error
            logger.warning(
                "Failed to check Redis blacklist - treating as blacklisted",
                error=str(e),
                jti=jti
            )
            return True


# Global blacklist instance
_token_blacklist = TokenBlacklist()


def get_token_blacklist() -> TokenBlacklist:
    """Get the token blacklist instance."""
    return _token_blacklist
