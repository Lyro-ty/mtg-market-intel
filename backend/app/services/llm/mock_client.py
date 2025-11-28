"""
Mock LLM client for testing and development.

Generates plausible responses without calling external APIs.
"""
import random
from app.services.llm.base import LLMClient, LLMResponse


class MockLLMClient(LLMClient):
    """
    Mock LLM client that generates reasonable placeholder responses.
    
    Useful for testing, development, and when no API keys are configured.
    """
    
    @property
    def provider_name(self) -> str:
        return "mock"
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        """Generate a mock response based on the prompt context."""
        # Analyze prompt to generate contextual response
        content = self._generate_contextual_response(prompt)
        
        return LLMResponse(
            content=content,
            model="mock-model",
            provider=self.provider_name,
            usage={
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": len(content.split()),
                "total_tokens": len(prompt.split()) + len(content.split()),
            },
        )
    
    def _generate_contextual_response(self, prompt: str) -> str:
        """Generate a contextual mock response based on prompt keywords."""
        prompt_lower = prompt.lower()
        
        # Recommendation rationale responses
        if "recommendation" in prompt_lower or "rationale" in prompt_lower:
            if "buy" in prompt_lower:
                return self._buy_rationale()
            elif "sell" in prompt_lower:
                return self._sell_rationale()
            else:
                return self._hold_rationale()
        
        # Market analysis responses
        if "analyze" in prompt_lower or "insight" in prompt_lower:
            return self._market_analysis()
        
        # Default response
        return "Based on current market data, this card shows moderate trading activity with stable pricing trends."
    
    def _buy_rationale(self) -> str:
        """Generate a mock BUY rationale."""
        rationales = [
            "Current price is significantly below the 30-day average, presenting a buying opportunity. Market spread indicates undervaluation on this marketplace. Consider accumulating while prices remain depressed.",
            "Strong upward momentum combined with increasing listing activity suggests growing demand. Price is still below recent highs, making this an attractive entry point.",
            "Cross-market analysis shows this card is priced 15-20% below comparable listings. Low volatility indicates stable pricing, reducing downside risk.",
        ]
        return random.choice(rationales)
    
    def _sell_rationale(self) -> str:
        """Generate a mock SELL rationale."""
        rationales = [
            "Price has reached recent highs and momentum is showing signs of slowing. Market spread suggests premium pricing on this marketplace. Consider taking profits before potential correction.",
            "Volatility has increased significantly, indicating unstable pricing. Current price is well above the 30-day average, presenting a good exit opportunity.",
            "Listing activity has surged while prices peaked, suggesting increased supply pressure. Recommend selling to lock in gains before market saturation.",
        ]
        return random.choice(rationales)
    
    def _hold_rationale(self) -> str:
        """Generate a mock HOLD rationale."""
        rationales = [
            "Price is trading within its normal range with no clear directional signal. Volatility is moderate and market spread is reasonable. Wait for clearer trend development.",
            "Recent price stability and consistent listing volumes suggest equilibrium. Neither buying nor selling pressure is dominant. Maintain current position.",
            "Mixed signals across timeframes. Short-term momentum is neutral while longer-term trend remains intact. No immediate action required.",
        ]
        return random.choice(rationales)
    
    def _market_analysis(self) -> str:
        """Generate a mock market analysis."""
        analyses = [
            "This card demonstrates healthy market dynamics with balanced supply and demand. Price movements have been orderly, suggesting institutional interest. Watch for breakout above recent resistance.",
            "Market activity shows typical pattern for cards of this rarity and playability. Seasonal factors may influence near-term pricing. Overall outlook is neutral to slightly positive.",
            "Strong fundamentals backed by tournament playability and collector demand. Price volatility remains within acceptable bounds. Long-term prospects appear favorable.",
        ]
        return random.choice(analyses)

