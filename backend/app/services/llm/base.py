"""
Base LLM client interface.

Defines the abstract interface that all LLM providers must implement.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    model: str
    provider: str
    usage: dict[str, int] | None = None
    raw_response: Any = None


class LLMClient(ABC):
    """
    Abstract base class for LLM clients.
    
    All LLM provider implementations must inherit from this class
    and implement the required methods.
    """
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of the LLM provider."""
        pass
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        """
        Generate text based on a prompt.
        
        Args:
            prompt: The user prompt to send to the LLM.
            system_prompt: Optional system prompt to set context.
            temperature: Sampling temperature (0-1).
            max_tokens: Maximum tokens to generate.
            
        Returns:
            LLMResponse containing the generated text and metadata.
        """
        pass
    
    async def generate_explanation(
        self,
        context: dict[str, Any],
        prompt_template: str | None = None,
    ) -> str:
        """
        Generate a human-readable explanation of market data.
        
        Args:
            context: Dictionary containing market metrics and data.
            prompt_template: Optional custom prompt template.
            
        Returns:
            Human-readable explanation string.
        """
        if prompt_template is None:
            prompt_template = self._default_explanation_prompt()
        
        prompt = prompt_template.format(**context)
        response = await self.generate(
            prompt=prompt,
            system_prompt="You are an MTG market analyst. Provide concise, actionable insights.",
            temperature=0.5,
            max_tokens=500,
        )
        return response.content
    
    async def generate_recommendation_rationale(
        self,
        card_name: str,
        action: str,
        metrics: dict[str, Any],
    ) -> str:
        """
        Generate a rationale for a trading recommendation.
        
        Args:
            card_name: Name of the MTG card.
            action: Recommended action (BUY/SELL/HOLD).
            metrics: Dictionary of relevant metrics.
            
        Returns:
            Human-readable rationale string.
        """
        prompt = f"""
        Generate a concise rationale for the following MTG card trading recommendation:
        
        Card: {card_name}
        Recommended Action: {action}
        
        Metrics:
        - Current Price: ${metrics.get('current_price', 'N/A')}
        - 7-Day Change: {metrics.get('price_change_pct_7d', 'N/A')}%
        - 30-Day Change: {metrics.get('price_change_pct_30d', 'N/A')}%
        - Market Spread: {metrics.get('spread_pct', 'N/A')}%
        - Volatility (7d): {metrics.get('volatility_7d', 'N/A')}
        - Momentum: {metrics.get('momentum', 'N/A')}
        - Number of Listings: {metrics.get('total_listings', 'N/A')}
        
        Provide a clear, actionable rationale in 2-3 sentences. Focus on the key factors
        driving this recommendation and any risks to consider.
        """
        
        response = await self.generate(
            prompt=prompt,
            system_prompt="You are an MTG market analyst. Be concise and data-driven.",
            temperature=0.5,
            max_tokens=200,
        )
        return response.content
    
    def _default_explanation_prompt(self) -> str:
        """Return the default explanation prompt template."""
        return """
        Analyze the following MTG card market data and provide a brief insight:
        
        Card: {card_name}
        Current Price: ${avg_price}
        Price Trend (7d): {price_change_pct_7d}%
        Price Trend (30d): {price_change_pct_30d}%
        Market Spread: {spread_pct}%
        Volatility: {volatility_7d}
        
        Provide a 2-3 sentence summary of the market situation and outlook.
        """

