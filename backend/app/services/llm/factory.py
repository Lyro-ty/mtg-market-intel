"""
LLM client factory.

Creates the appropriate LLM client based on configuration.
"""
import structlog
from functools import lru_cache

from app.core.config import settings
from app.services.llm.base import LLMClient
from app.services.llm.openai_client import OpenAIClient
from app.services.llm.anthropic_client import AnthropicClient
from app.services.llm.mock_client import MockLLMClient

logger = structlog.get_logger()


@lru_cache()
def get_llm_client(provider: str | None = None) -> LLMClient:
    """
    Get an LLM client instance based on provider configuration.
    
    Args:
        provider: Override the provider from settings. Options: openai, anthropic, mock
        
    Returns:
        Configured LLM client instance.
    """
    provider = provider or settings.llm_provider.lower()
    
    logger.info("Creating LLM client", provider=provider)
    
    if provider == "openai":
        if not settings.openai_api_key:
            logger.warning("OpenAI API key not set, falling back to mock client")
            return MockLLMClient()
        return OpenAIClient()
    
    elif provider == "anthropic":
        if not settings.anthropic_api_key:
            logger.warning("Anthropic API key not set, falling back to mock client")
            return MockLLMClient()
        return AnthropicClient()
    
    elif provider == "mock":
        return MockLLMClient()
    
    else:
        logger.warning("Unknown LLM provider, using mock client", provider=provider)
        return MockLLMClient()


def clear_llm_client_cache() -> None:
    """Clear the cached LLM client. Useful for testing."""
    get_llm_client.cache_clear()

