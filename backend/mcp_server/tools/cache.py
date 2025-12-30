"""
Redis cache tools for MCP server.

Provides tools to inspect and manage the Redis cache.
"""
from typing import Any
import os
import redis.asyncio as redis

from mcp_server.utils import log_write_operation, require_dev_mode


def get_redis_client():
    """Get Redis client from environment."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return redis.from_url(redis_url)


async def list_cache_keys(pattern: str = "*", limit: int = 100) -> dict[str, Any]:
    """
    List Redis keys matching a pattern.

    Args:
        pattern: Key pattern (default "*" for all)
        limit: Maximum keys to return (default 100)

    Returns:
        List of matching key names
    """
    try:
        client = get_redis_client()
        keys = []
        async for key in client.scan_iter(match=pattern, count=limit):
            keys.append(key.decode() if isinstance(key, bytes) else key)
            if len(keys) >= limit:
                break
        await client.aclose()

        return {
            "pattern": pattern,
            "count": len(keys),
            "keys": keys,
            "truncated": len(keys) >= limit,
        }
    except Exception as e:
        return {"error": str(e)}


async def get_cache_value(key: str) -> dict[str, Any]:
    """
    Get value for a specific cache key.

    Args:
        key: Redis key name

    Returns:
        Cached value and metadata
    """
    try:
        client = get_redis_client()

        # Get type first
        key_type = await client.type(key)
        key_type = key_type.decode() if isinstance(key_type, bytes) else key_type

        # Get TTL
        ttl = await client.ttl(key)

        # Get value based on type
        if key_type == "string":
            value = await client.get(key)
            value = value.decode() if isinstance(value, bytes) else value
        elif key_type == "hash":
            value = await client.hgetall(key)
            value = {k.decode(): v.decode() for k, v in value.items()}
        elif key_type == "list":
            value = await client.lrange(key, 0, 100)
            value = [v.decode() if isinstance(v, bytes) else v for v in value]
        elif key_type == "set":
            value = await client.smembers(key)
            value = [v.decode() if isinstance(v, bytes) else v for v in value]
        elif key_type == "none":
            await client.aclose()
            return {"error": f"Key '{key}' not found"}
        else:
            value = f"<{key_type} type not supported>"

        await client.aclose()

        return {
            "key": key,
            "type": key_type,
            "ttl": ttl if ttl > 0 else "no expiry" if ttl == -1 else "expired",
            "value": value,
        }
    except Exception as e:
        return {"error": str(e)}


async def get_cache_stats() -> dict[str, Any]:
    """
    Get Redis cache statistics.

    Returns:
        Memory usage, hit/miss stats, etc.
    """
    try:
        client = get_redis_client()

        info = await client.info()
        memory = await client.info("memory")
        stats = await client.info("stats")

        await client.aclose()

        return {
            "redis_version": info.get("redis_version"),
            "uptime_seconds": info.get("uptime_in_seconds"),
            "connected_clients": info.get("connected_clients"),
            "used_memory_human": memory.get("used_memory_human"),
            "used_memory_peak_human": memory.get("used_memory_peak_human"),
            "total_connections_received": stats.get("total_connections_received"),
            "total_commands_processed": stats.get("total_commands_processed"),
            "keyspace_hits": stats.get("keyspace_hits"),
            "keyspace_misses": stats.get("keyspace_misses"),
        }
    except Exception as e:
        return {"error": str(e)}


async def write_clear_cache(pattern: str = "*", confirm: bool = False) -> dict[str, Any]:
    """
    Clear Redis cache keys matching a pattern.

    WARNING: This deletes cached data.

    Args:
        pattern: Key pattern to delete (default "*" for all)
        confirm: Must be True to actually delete

    Returns:
        Number of keys deleted
    """
    require_dev_mode("write_clear_cache")

    if not confirm:
        # Show what would be deleted
        keys_result = await list_cache_keys(pattern, limit=20)
        return {
            "warning": "This will delete cache keys matching the pattern",
            "pattern": pattern,
            "sample_keys": keys_result.get("keys", []),
            "usage": "Set confirm=True to actually delete",
        }

    log_write_operation("write_clear_cache", {"pattern": pattern})

    try:
        client = get_redis_client()
        deleted = 0

        async for key in client.scan_iter(match=pattern):
            await client.delete(key)
            deleted += 1

        await client.aclose()

        return {
            "success": True,
            "pattern": pattern,
            "deleted_count": deleted,
        }
    except Exception as e:
        return {"error": str(e)}


async def write_invalidate_cache_key(key: str) -> dict[str, Any]:
    """
    Delete a specific cache key.

    Args:
        key: Redis key to delete

    Returns:
        Deletion result
    """
    require_dev_mode("write_invalidate_cache_key")
    log_write_operation("write_invalidate_cache_key", {"key": key})

    try:
        client = get_redis_client()
        deleted = await client.delete(key)
        await client.aclose()

        return {
            "success": True,
            "key": key,
            "deleted": deleted > 0,
        }
    except Exception as e:
        return {"error": str(e)}
