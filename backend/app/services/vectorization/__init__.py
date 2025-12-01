"""
Feature vectorization service for ML training.

Converts raw card and listing data into normalized feature vectors
ready for machine learning models.
"""
import structlog
from functools import lru_cache

from app.services.vectorization.service import VectorizationService

logger = structlog.get_logger()

# Global cache for vectorization service
_VECTORIZATION_SERVICE: VectorizationService | None = None


@lru_cache()
def get_vectorization_service() -> VectorizationService:
    """
    Get a cached VectorizationService instance.
    
    The embedding model is expensive to load, so we cache the service
    to avoid reloading it for every card.
    
    Returns:
        Cached VectorizationService instance.
    """
    global _VECTORIZATION_SERVICE
    if _VECTORIZATION_SERVICE is None:
        logger.info("Creating cached VectorizationService instance")
        _VECTORIZATION_SERVICE = VectorizationService()
    return _VECTORIZATION_SERVICE


def clear_vectorization_service_cache() -> None:
    """Clear the cached vectorization service. Useful for testing."""
    global _VECTORIZATION_SERVICE
    _VECTORIZATION_SERVICE = None
    get_vectorization_service.cache_clear()


__all__ = ["VectorizationService", "get_vectorization_service", "clear_vectorization_service_cache"]
