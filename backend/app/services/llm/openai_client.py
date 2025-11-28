"""
OpenAI LLM client implementation.
"""
import structlog
from openai import AsyncOpenAI

from app.core.config import settings
from app.services.llm.base import LLMClient, LLMResponse

logger = structlog.get_logger()


class OpenAIClient(LLMClient):
    """OpenAI API client implementation."""
    
    def __init__(self, api_key: str | None = None, model: str | None = None):
        """
        Initialize the OpenAI client.
        
        Args:
            api_key: OpenAI API key. Defaults to settings.
            model: Model to use. Defaults to settings.
        """
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
    
    @property
    def provider_name(self) -> str:
        return "openai"
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        """Generate text using OpenAI's API."""
        if not self.client:
            logger.warning("OpenAI API key not configured, returning placeholder response")
            return LLMResponse(
                content="[LLM response placeholder - API key not configured]",
                model=self.model,
                provider=self.provider_name,
            )
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=self.model,
                provider=self.provider_name,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                raw_response=response,
            )
        except Exception as e:
            logger.error("OpenAI API error", error=str(e))
            raise

