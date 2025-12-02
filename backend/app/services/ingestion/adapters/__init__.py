"""
Marketplace adapter implementations.
"""
from app.services.ingestion.adapters.tcgplayer import TCGPlayerAdapter
from app.services.ingestion.adapters.cardmarket import CardMarketAdapter
from app.services.ingestion.adapters.cardkingdom import CardKingdomAdapter
from app.services.ingestion.adapters.mtgjson import MTGJSONAdapter
from app.services.ingestion.adapters.mock import MockMarketplaceAdapter

__all__ = [
    "TCGPlayerAdapter",
    "CardMarketAdapter",
    "CardKingdomAdapter",
    "MTGJSONAdapter",
    "MockMarketplaceAdapter",
]

