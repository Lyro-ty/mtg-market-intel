"""
Anthropic (Claude) LLM client implementation.
"""
import structlog
from anthropic import AsyncAnthropic

from app.core.config import settings
from app.services.llm.base import LLMClient, LLMResponse

logger = structlog.get_logger()


class AnthropicClient(LLMClient):
    """Anthropic Claude API client implementation."""
    
    def __init__(self, api_key: str | None = None, model: str | None = None):
        """
        Initialize the Anthropic client.
        
        Args:
            api_key: Anthropic API key. Defaults to settings.
            model: Model to use. Defaults to settings.
        """
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model or settings.anthropic_model
        self.client = AsyncAnthropic(api_key=self.api_key) if self.api_key else None
    
    @property
    def provider_name(self) -> str:
        return "anthropic"
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        """Generate text using Anthropic's API."""
        if not self.client:
            logger.warning("Anthropic API key not configured, returning placeholder response")
            return LLMResponse(
                content="[LLM response placeholder - API key not configured]",
                model=self.model,
                provider=self.provider_name,
            )
        
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt or "You are a helpful assistant.",
                messages=[{"role": "user", "content": prompt}],
            )
            
            content = ""
            if response.content and len(response.content) > 0:
                content = response.content[0].text
            
            return LLMResponse(
                content=content,
                model=self.model,
                provider=self.provider_name,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                },
                raw_response=response,
            )
        except Exception as e:
            logger.error("Anthropic API error", error=str(e))
            raise

