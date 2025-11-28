"""
API module for FastAPI routes.
"""
from fastapi import APIRouter

from app.api.routes import health, cards, recommendations, dashboard, settings, marketplaces

api_router = APIRouter()

# Include all route modules
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(cards.router, prefix="/cards", tags=["Cards"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(marketplaces.router, prefix="/marketplaces", tags=["Marketplaces"])

