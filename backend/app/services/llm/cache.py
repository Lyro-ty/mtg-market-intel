"""
LLM response caching to reduce API calls and improve efficiency.

Caches LLM responses based on prompt hash to avoid redundant API calls
when the same analysis is requested multiple times.
"""
import hashlib
import json
from typing import Any, Optional
from datetime import datetime, timedelta

import structlog

from app.core.cache import SimpleCache

logger = structlog.get_logger()

# Global cache for LLM responses
_llm_cache = SimpleCache(max_size=500, default_ttl=3600)  # 1 hour TTL


def _hash_prompt(prompt: str, system_prompt: str | None = None, temperature: float = 0.7) -> str:
    """
    Generate a hash key for a prompt combination.
    
    Args:
        prompt: User prompt.
        system_prompt: System prompt.
        temperature: Temperature setting.
        
    Returns:
        Hash string for caching.
    """
    # Normalize temperature to avoid cache misses from float precision
    temp_normalized = round(temperature, 2)
    
    key_data = {
        "prompt": prompt,
        "system_prompt": system_prompt or "",
        "temperature": temp_normalized,
    }
    key_str = json.dumps(key_data, sort_keys=True)
    return hashlib.sha256(key_str.encode()).hexdigest()


def get_cached_response(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float = 0.7,
) -> Optional[str]:
    """
    Get a cached LLM response if available.
    
    Args:
        prompt: User prompt.
        system_prompt: System prompt.
        temperature: Temperature setting.
        
    Returns:
        Cached response content or None.
    """
    cache_key = f"llm:{_hash_prompt(prompt, system_prompt, temperature)}"
    cached = _llm_cache.get(cache_key)
    
    if cached:
        logger.debug("LLM cache hit", cache_key=cache_key[:16])
        return cached
    
    return None


def cache_response(
    prompt: str,
    response_content: str,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    ttl: Optional[int] = None,
) -> None:
    """
    Cache an LLM response.
    
    Args:
        prompt: User prompt.
        response_content: Response content to cache.
        system_prompt: System prompt.
        temperature: Temperature setting.
        ttl: Time-to-live in seconds. Uses default if None.
    """
    cache_key = f"llm:{_hash_prompt(prompt, system_prompt, temperature)}"
    _llm_cache.set(cache_key, response_content, ttl=ttl)
    logger.debug("LLM response cached", cache_key=cache_key[:16])


def clear_llm_cache() -> None:
    """Clear all cached LLM responses."""
    _llm_cache.clear()
    logger.info("LLM cache cleared")


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics."""
    return {
        "size": len(_llm_cache._cache),
        "max_size": _llm_cache.max_size,
        "default_ttl": _llm_cache.default_ttl,
    }

