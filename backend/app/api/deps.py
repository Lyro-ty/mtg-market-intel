"""
API dependencies for authentication and authorization.
"""
import asyncio
from datetime import timedelta
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from redis.asyncio import ConnectionPool, Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.repositories.cache_repo import CacheRepository
from app.services.auth import decode_access_token, get_user_by_id

# Security scheme for JWT bearer tokens
security = HTTPBearer(auto_error=False)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
) -> User:
    """
    Get the current authenticated user from the JWT token.
    
    Raises HTTPException 401 if token is invalid or user not found.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user_id = int(payload.sub)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_user_optional(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
) -> Optional[User]:
    """
    Get the current user if authenticated, otherwise return None.
    
    Useful for endpoints that have different behavior for logged in vs anonymous users.
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(db, credentials)
    except HTTPException:
        return None


async def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Get the current user and verify they are an admin.
    
    Raises HTTPException 403 if user is not an admin.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


# Type aliases for cleaner dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[Optional[User], Depends(get_current_user_optional)]
AdminUser = Annotated[User, Depends(get_current_admin_user)]

# Alias for backwards compatibility
get_optional_current_user = get_current_user_optional


# Redis and cache dependencies
_redis_client: Redis | None = None
_redis_lock = asyncio.Lock()


def _reset_redis_client() -> None:
    """Reset Redis client for testing. Do not use in production."""
    global _redis_client
    _redis_client = None


async def _create_redis_client() -> Redis:
    """Create and configure Redis client."""
    pool = ConnectionPool.from_url(
        settings.redis_url,
        max_connections=20,
        decode_responses=True,
    )
    return Redis(connection_pool=pool)


async def get_redis() -> Redis:
    """
    Get Redis client singleton.

    Thread-safe initialization using asyncio.Lock.
    All concurrent callers wait for the same initialization.

    Returns:
        Configured Redis client
    """
    global _redis_client

    # Fast path: already initialized
    if _redis_client is not None:
        return _redis_client

    # Slow path: need to initialize
    async with _redis_lock:
        # Check again after acquiring lock (another task may have initialized)
        if _redis_client is not None:
            return _redis_client

        # We're the first - create the client
        _redis_client = await _create_redis_client()
        return _redis_client


async def close_redis() -> None:
    """Close Redis connection pool. Call on application shutdown."""
    global _redis_client

    async with _redis_lock:
        if _redis_client is not None:
            await _redis_client.close()
            _redis_client = None


async def get_cache(
    redis: Annotated[Redis, Depends(get_redis)],
) -> CacheRepository:
    """
    Get the cache repository with Redis backend.

    Default TTL is 5 minutes for dashboard/API caching.
    """
    return CacheRepository(redis, default_ttl=timedelta(minutes=5))


# Type alias for cleaner dependency injection
Cache = Annotated[CacheRepository, Depends(get_cache)]


# =============================================================================
# Bot Service Authentication
# =============================================================================

from fastapi import Header
import secrets


async def verify_bot_token(
    x_bot_token: str = Header(..., alias="X-Bot-Token"),
) -> bool:
    """
    Verify the bot service token for internal bot-to-backend API calls.

    The bot authenticates using a shared secret (DISCORD_BOT_API_KEY).
    This is used for bot-specific endpoints like user lookup by Discord ID.

    Raises HTTPException 401 if token is missing or invalid.
    """
    if not settings.DISCORD_BOT_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot authentication not configured",
        )

    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(x_bot_token, settings.DISCORD_BOT_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bot token",
        )

    return True


# Type alias for bot authentication dependency
BotAuth = Annotated[bool, Depends(verify_bot_token)]




