"""
AI Agent services for analytics and recommendations.

Contains the core business logic for:
- Analytics: Compute metrics, detect trends, generate insights
- Recommendations: Generate actionable buy/sell/hold signals
- Inventory Recommendations: Aggressive recommendations for owned cards
- Normalization: Map marketplace data to canonical card identities
"""
from app.services.agents.analytics import AnalyticsAgent
from app.services.agents.recommendation import RecommendationAgent
from app.services.agents.inventory_recommendation import InventoryRecommendationAgent
from app.services.agents.normalization import NormalizationService

__all__ = [
    "AnalyticsAgent",
    "RecommendationAgent",
    "InventoryRecommendationAgent",
    "NormalizationService",
]

