"""
AI Agent services for analytics, recommendations, and validation.

Contains the core business logic for:
- Analytics: Compute metrics, detect trends, generate insights
- Recommendations: Generate actionable buy/sell/hold signals
- Inventory Recommendations: Aggressive recommendations for owned cards
- Normalization: Map marketplace data to canonical card identities
- Implementation: Validate implementation completeness
- CodeQuality: Check code patterns and quality
- DataIntegrity: Monitor data quality and integrity
"""
from app.services.agents.analytics import AnalyticsAgent
from app.services.agents.recommendation import RecommendationAgent
from app.services.agents.inventory_recommendation import InventoryRecommendationAgent
from app.services.agents.normalization import NormalizationService
from app.services.agents.implementation import ImplementationValidator
from app.services.agents.code_quality import CodeQualityAgent
from app.services.agents.data_integrity import DataIntegrityAgent

__all__ = [
    "AnalyticsAgent",
    "RecommendationAgent",
    "InventoryRecommendationAgent",
    "NormalizationService",
    "ImplementationValidator",
    "CodeQualityAgent",
    "DataIntegrityAgent",
]

