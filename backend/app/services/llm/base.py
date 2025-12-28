"""
Base LLM client interface.

Defines the abstract interface that all LLM providers must implement.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import structlog

from app.services.llm.cache import get_cached_response, cache_response
from app.services.llm.enhanced_prompts import (
    get_enhanced_explanation_prompt,
    get_enhanced_recommendation_prompt,
    format_signals_context,
    format_historical_context,
)

logger = structlog.get_logger()


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
        use_cache: bool = True,
        use_enhanced: bool = True,
    ) -> str:
        """
        Generate a human-readable explanation of market data.
        
        Args:
            context: Dictionary containing market metrics and data.
            prompt_template: Optional custom prompt template.
            use_cache: Whether to use cached responses (default: True).
            use_enhanced: Whether to use enhanced prompts with more context (default: True).
            
        Returns:
            Human-readable explanation string.
        """
        if prompt_template is None:
            if use_enhanced:
                prompt_template = get_enhanced_explanation_prompt()
            else:
                prompt_template = self._default_explanation_prompt()
        
        # Add signals context if available
        signals = context.get("signals", [])
        if signals:
            context["signals_context"] = format_signals_context(signals)
        else:
            context["signals_context"] = ""
        
        # Add total_listings if not present
        if "total_listings" not in context:
            context["total_listings"] = context.get("num_listings", 0)
        
        # Ensure all required keys are present with defaults
        # Enhanced prompts expect numeric values, but we may have strings from analytics
        required_keys = {
            "card_name": "Unknown Card",
            "avg_price": "N/A",
            "price_change_pct_7d": "N/A",
            "price_change_pct_30d": "N/A",
            "spread_pct": "N/A",
            "volatility_7d": "N/A",
            "total_listings": 0,
            "signals_context": "",
        }
        for key, default_value in required_keys.items():
            if key not in context:
                context[key] = default_value
        
        try:
            prompt = prompt_template.format(**context)
        except (KeyError, ValueError) as e:
            logger.error("Error formatting prompt", error=str(e), available_keys=list(context.keys()))
            # Fallback to default prompt if enhanced prompt fails
            prompt_template = self._default_explanation_prompt()
            prompt = prompt_template.format(**context)
        system_prompt = "You are an expert MTG market analyst. Provide concise, actionable insights based on data."
        
        # Check cache first
        if use_cache:
            cached = get_cached_response(prompt, system_prompt, temperature=0.5)
            if cached:
                return cached
        
        response = await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.5,
            max_tokens=500,
        )
        
        # Cache the response
        if use_cache:
            cache_response(prompt, response.content, system_prompt, temperature=0.5, ttl=3600)
        
        return response.content
    
    async def generate_recommendation_rationale(
        self,
        card_name: str,
        action: str,
        metrics: dict[str, Any],
        confidence: float | None = None,
        signals: list[dict[str, Any]] | None = None,
        use_cache: bool = True,
        use_enhanced: bool = True,
    ) -> str:
        """
        Generate a rationale for a trading recommendation.
        
        Args:
            card_name: Name of the MTG card.
            action: Recommended action (BUY/SELL/HOLD).
            metrics: Dictionary of relevant metrics.
            confidence: Confidence score for the recommendation.
            signals: List of signals that triggered this recommendation.
            use_cache: Whether to use cached responses (default: True).
            use_enhanced: Whether to use enhanced prompts (default: True).
            
        Returns:
            Human-readable rationale string.
        """
        if use_enhanced:
            # Build enhanced prompt context with proper type conversion
            def safe_float(value, default=0.0):
                """Safely convert value to float."""
                if value is None:
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default
            
            prompt_context = {
                "card_name": card_name,
                "action": action,
                "confidence": safe_float(confidence or metrics.get("confidence"), 0.7),
                "current_price": safe_float(metrics.get("current_price"), 0.0),
                "price_change_pct_7d": safe_float(metrics.get("price_change_pct_7d"), 0.0),
                "price_change_pct_30d": safe_float(metrics.get("price_change_pct_30d"), 0.0),
                "spread_pct": safe_float(metrics.get("spread_pct"), 0.0),
                "volatility_7d": safe_float(metrics.get("volatility_7d"), 0.0),
                "momentum": str(metrics.get("momentum", "neutral")),
                "total_listings": int(safe_float(metrics.get("total_listings") or metrics.get("num_listings"), 0)),
            }
            
            # Add signals summary
            if signals:
                prompt_context["signals_summary"] = format_signals_context(signals)
            else:
                prompt_context["signals_summary"] = ""
            
            # Add historical context if available
            prompt_context["historical_context"] = format_historical_context(
                price_history=metrics.get("price_history"),
                recent_recommendations=metrics.get("recent_recommendations"),
            )
            
            prompt_template = get_enhanced_recommendation_prompt()
            try:
                prompt = prompt_template.format(**prompt_context)
            except (KeyError, ValueError) as e:
                logger.error("Error formatting enhanced prompt", error=str(e), context_keys=list(prompt_context.keys()))
                # Fallback to simple prompt
                use_enhanced = False
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
        else:
            # Fallback to simple prompt
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
        
        system_prompt = "You are an expert MTG market analyst. Be concise and data-driven."
        
        # Check cache first
        if use_cache:
            cached = get_cached_response(prompt, system_prompt, temperature=0.5)
            if cached:
                return cached
        
        response = await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.5,
            max_tokens=200,
        )
        
        # Cache the response
        if use_cache:
            cache_response(prompt, response.content, system_prompt, temperature=0.5, ttl=3600)
        
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

