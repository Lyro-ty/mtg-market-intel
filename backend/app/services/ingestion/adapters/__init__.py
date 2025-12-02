"""
Marketplace adapter implementations.

Note: Web scrapers (TCGPlayer, Cardmarket, Card Kingdom) have been removed.
We now use Scryfall and MTGJSON as primary data sources for price data.
"""
from app.services.ingestion.adapters.mtgjson import MTGJSONAdapter
from app.services.ingestion.adapters.mock import MockMarketplaceAdapter

__all__ = [
    "MTGJSONAdapter",
    "MockMarketplaceAdapter",
]

