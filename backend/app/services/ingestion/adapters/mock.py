"""
Mock marketplace adapter for testing and development.

Generates realistic fake data for system testing without
hitting external APIs.
"""
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.ingestion.base import (
    AdapterConfig,
    CardListing,
    CardPrice,
    MarketplaceAdapter,
)


class MockMarketplaceAdapter(MarketplaceAdapter):
    """
    Mock adapter that generates realistic fake marketplace data.
    
    Useful for testing the full system flow without external dependencies.
    """
    
    def __init__(self, config: AdapterConfig | None = None, name: str = "Mock Market"):
        if config is None:
            config = AdapterConfig(
                base_url="https://mock-marketplace.example.com",
                rate_limit_seconds=0.1,
            )
        super().__init__(config)
        self._name = name
        self._slug = name.lower().replace(" ", "_")
    
    @property
    def marketplace_name(self) -> str:
        return self._name
    
    @property
    def marketplace_slug(self) -> str:
        return self._slug
    
    async def fetch_listings(
        self,
        card_name: str | None = None,
        set_code: str | None = None,
        scryfall_id: str | None = None,
        limit: int = 100,
    ) -> list[CardListing]:
        """Generate mock listings for a card."""
        if not card_name:
            return []
        
        # Generate between 3-15 mock listings
        num_listings = random.randint(3, min(15, limit))
        base_price = random.uniform(0.5, 100.0)
        
        listings = []
        conditions = ["NM", "LP", "MP", "HP"]
        sellers = ["GoodSeller", "MTGDeals", "CardShop", "ValueCards", "ProSeller"]
        
        for i in range(num_listings):
            condition = random.choice(conditions)
            # Price varies by condition
            condition_multiplier = {
                "NM": 1.0,
                "LP": 0.85,
                "MP": 0.70,
                "HP": 0.55,
            }
            price = base_price * condition_multiplier[condition]
            # Add some variance
            price *= random.uniform(0.9, 1.15)
            
            listings.append(CardListing(
                card_name=card_name,
                set_code=set_code or "XXX",
                collector_number=str(random.randint(1, 300)),
                scryfall_id=scryfall_id,
                price=round(price, 2),
                currency="USD",
                quantity=random.randint(1, 8),
                condition=condition,
                language="English",
                is_foil=random.random() < 0.15,
                seller_name=random.choice(sellers),
                seller_rating=round(random.uniform(4.0, 5.0), 2),
                external_id=f"mock-{i}-{random.randint(1000, 9999)}",
                listing_url=f"{self.config.base_url}/listing/{i}",
            ))
        
        return listings
    
    async def fetch_price(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
    ) -> CardPrice | None:
        """Generate mock price data for a card."""
        # Generate a base price based on card name hash for consistency
        name_hash = hash(card_name + set_code)
        random.seed(name_hash)
        
        base_price = random.uniform(0.25, 150.0)
        
        # Generate price variants
        price_low = base_price * 0.75
        price_high = base_price * 1.3
        price_mid = base_price
        price_market = base_price * random.uniform(0.95, 1.05)
        
        # Reset random seed
        random.seed()
        
        return CardPrice(
            card_name=card_name,
            set_code=set_code,
            collector_number=collector_number or "1",
            scryfall_id=scryfall_id,
            price=round(price_market, 2),
            currency="USD",
            price_low=round(price_low, 2),
            price_mid=round(price_mid, 2),
            price_high=round(price_high, 2),
            price_market=round(price_market, 2),
            price_foil=round(base_price * 2.5, 2) if random.random() < 0.8 else None,
            num_listings=random.randint(5, 50),
            total_quantity=random.randint(10, 200),
            snapshot_time=datetime.now(timezone.utc),
        )
    
    async def fetch_price_history(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
        days: int = 30,
    ) -> list[CardPrice]:
        """Generate mock price history."""
        # Generate consistent base price
        name_hash = hash(card_name + set_code)
        random.seed(name_hash)
        base_price = random.uniform(0.25, 150.0)
        random.seed()
        
        history = []
        current_price = base_price
        
        for i in range(days, 0, -1):
            # Add some random walk to simulate price movement
            change = random.uniform(-0.05, 0.05)
            current_price *= (1 + change)
            current_price = max(0.10, current_price)  # Floor at $0.10
            
            history.append(CardPrice(
                card_name=card_name,
                set_code=set_code,
                collector_number=collector_number or "1",
                scryfall_id=scryfall_id,
                price=round(current_price, 2),
                currency="USD",
                num_listings=random.randint(5, 50),
                total_quantity=random.randint(10, 200),
                snapshot_time=datetime.now(timezone.utc) - timedelta(days=i),
            ))
        
        return history
    
    async def search_cards(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return mock search results."""
        # Generate some fake card names based on query
        mock_cards = [
            {"name": f"{query} Dragon", "set_code": "M21", "rarity": "rare"},
            {"name": f"{query} Knight", "set_code": "ELD", "rarity": "uncommon"},
            {"name": f"{query}'s Triumph", "set_code": "WAR", "rarity": "rare"},
            {"name": f"Ancient {query}", "set_code": "BFZ", "rarity": "mythic"},
            {"name": f"{query} of the Realm", "set_code": "DOM", "rarity": "uncommon"},
        ]
        return mock_cards[:limit]
    
    async def health_check(self) -> bool:
        """Mock adapter is always healthy."""
        return True

