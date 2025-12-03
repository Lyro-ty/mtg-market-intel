"""
Enhanced prompt templates with better context and few-shot examples.

These prompts provide more context to the LLM for better accuracy and consistency.
"""
from typing import Any


def get_enhanced_explanation_prompt() -> str:
    """
    Enhanced prompt for market analysis with more context.
    
    Includes few-shot examples and better structure.
    """
    return """You are an expert MTG (Magic: The Gathering) market analyst with deep knowledge of card pricing, market trends, and trading strategies.

Analyze the following market data and provide a concise, actionable insight in 2-3 sentences.

Card: {card_name}
Current Price: ${avg_price}
Price Change (7d): {price_change_pct_7d}%
Price Change (30d): {price_change_pct_30d}%
Market Spread: {spread_pct}%
Volatility (7d): {volatility_7d}
Number of Listings: {total_listings}
{signals_context}

Guidelines:
- Focus on actionable insights, not just description
- Highlight key risk factors or opportunities
- Consider both short-term and medium-term outlook
- Be specific about what the data indicates

Example insights:
- "Strong upward momentum with 15% gain over 7 days suggests continued growth potential. However, high volatility (0.12) indicates price instability - consider taking profits on any spikes."
- "Price has stabilized after a 20% decline, trading within normal spread (8%). Low volatility suggests accumulation phase - good entry point for long-term holds."
- "Wide market spread (25%) indicates arbitrage opportunity, but low listing count suggests liquidity risk. Proceed with caution and verify availability."

Provide your analysis:"""


def get_enhanced_recommendation_prompt() -> str:
    """
    Enhanced prompt for recommendation rationales with structured context.
    """
    return """You are an expert MTG market analyst providing trading recommendations.

Generate a concise, data-driven rationale (2-3 sentences) for the following recommendation:

Card: {card_name}
Recommended Action: {action}
Confidence: {confidence:.0%}

Market Context:
- Current Price: ${current_price:.2f}
- 7-Day Change: {price_change_pct_7d:+.1f}%
- 30-Day Change: {price_change_pct_30d:+.1f}%
- Market Spread: {spread_pct:.1f}%
- Volatility (7d): {volatility_7d:.4f}
- Momentum: {momentum}
- Active Listings: {total_listings}
{signals_summary}
{historical_context}

Guidelines:
- Explain the primary factor driving this recommendation
- Mention any risks or counter-indicators
- Be specific about timing or conditions
- Use data to support your reasoning

Example rationales:
- BUY: "Strong upward momentum (7-day MA 8% above 30-day) combined with low volatility suggests sustainable growth. Current price is 12% below recent high, presenting a good entry point. Risk: High spread (22%) indicates market inefficiency."
- SELL: "Price has reached 30-day high with momentum slowing. Spread of 18% suggests premium pricing on this marketplace. Recommend taking profits before potential correction. Risk: Low listing count may limit exit liquidity."
- HOLD: "Mixed signals: Short-term momentum is positive but volatility is elevated (0.15). Price is trading within normal range. Wait for clearer directional signal or reduced volatility before taking action."

Provide your rationale:"""


def format_signals_context(signals: list[dict[str, Any]]) -> str:
    """
    Format signals into context string for prompts.
    
    Args:
        signals: List of signal dictionaries with type, confidence, value.
        
    Returns:
        Formatted string for prompt inclusion.
    """
    if not signals:
        return "Active Signals: None"
    
    signal_lines = []
    for signal in signals:
        signal_type = signal.get("type", "unknown")
        confidence = signal.get("confidence", 0)
        value = signal.get("value")
        
        signal_desc = f"- {signal_type.replace('_', ' ').title()}"
        if value is not None:
            try:
                # Ensure value is numeric before formatting
                value_float = float(value)
                signal_desc += f" (value: {value_float:.2f})"
            except (ValueError, TypeError):
                signal_desc += f" (value: {value})"
        try:
            # Ensure confidence is numeric before formatting
            confidence_float = float(confidence)
            signal_desc += f" [confidence: {confidence_float:.0%}]"
        except (ValueError, TypeError):
            signal_desc += f" [confidence: {confidence}]"
        signal_lines.append(signal_desc)
    
    return "Active Signals:\n" + "\n".join(signal_lines)


def format_historical_context(
    price_history: list[dict[str, Any]] | None = None,
    recent_recommendations: list[dict[str, Any]] | None = None,
) -> str:
    """
    Format historical context for prompts.
    
    Args:
        price_history: List of recent price points.
        recent_recommendations: List of recent recommendations.
        
    Returns:
        Formatted string for prompt inclusion.
    """
    context_parts = []
    
    if price_history:
        # Show price trend over last 7 days
        if len(price_history) >= 7:
            prices = []
            for p in price_history[-7:]:
                price_val = p.get("price")
                if price_val is not None:
                    try:
                        prices.append(float(price_val))
                    except (ValueError, TypeError):
                        pass  # Skip invalid price values
            
            if prices and len(prices) > 0:
                avg_7d = sum(prices) / len(prices)
                current = prices[-1]
                trend = "up" if current > avg_7d else "down"
                context_parts.append(f"Recent Trend: Price has trended {trend} over last 7 days (avg: ${avg_7d:.2f} → current: ${current:.2f})")
    
    if recent_recommendations:
        # Show recent recommendation accuracy
        recent_actions = [r.get("action") for r in recent_recommendations[-3:]]
        if recent_actions:
            action_counts = {}
            for action in recent_actions:
                action_counts[action] = action_counts.get(action, 0) + 1
            context_parts.append(f"Recent Recommendations: {', '.join([f'{k}: {v}' for k, v in action_counts.items()])}")
    
    return "\n".join(context_parts) if context_parts else ""

