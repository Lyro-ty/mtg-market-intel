"""
API module for FastAPI routes.
"""
from fastapi import APIRouter

from app.api.routes import (
    auth,
    health,
    cards,
    recommendations,
    dashboard,
    settings,
    marketplaces,
    inventory,
    market,
    websocket,
    tournaments,
    search,
    oauth,
    sessions,
    sets,
    notifications,
    collection,
    want_list,
)

api_router = APIRouter()

# Include all route modules
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(oauth.router, prefix="/auth", tags=["OAuth"])
api_router.include_router(cards.router, prefix="/cards", tags=["Cards"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(marketplaces.router, prefix="/marketplaces", tags=["Marketplaces"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
api_router.include_router(market.router, prefix="/market", tags=["Market"])
api_router.include_router(tournaments.router, prefix="/tournaments", tags=["Tournaments"])
api_router.include_router(tournaments.meta_router, prefix="/meta", tags=["Meta"])
api_router.include_router(tournaments.cards_meta_router, prefix="/cards", tags=["Cards"])

api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(sets.router, tags=["Sets"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(collection.router, prefix="/collection", tags=["Collection"])
api_router.include_router(want_list.router, prefix="/want-list", tags=["Want List"])

# WebSocket route (no prefix - connects at /api/ws)
api_router.include_router(websocket.router, tags=["WebSocket"])

# Session management
api_router.include_router(sessions.router)

