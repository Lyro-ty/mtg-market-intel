"""
Marketplace adapter implementations.

Note: Web scrapers (TCGPlayer, Cardmarket, Card Kingdom) have been removed.
We now use Scryfall and MTGJSON as primary data sources for price data,
with Manapool as an additional European marketplace API source.
"""
from app.services.ingestion.adapters.manapool import ManapoolAdapter
from app.services.ingestion.adapters.mtgjson import MTGJSONAdapter
from app.services.ingestion.adapters.mock import MockMarketplaceAdapter

__all__ = [
    "ManapoolAdapter",
    "MTGJSONAdapter",
    "MockMarketplaceAdapter",
]

