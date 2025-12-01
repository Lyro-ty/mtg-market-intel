"""
Seed data script for initial database population.

This script populates the database with:
- Default marketplace records
- Default settings
- Sample cards from popular sets (via Scryfall)
"""
import asyncio
import sys
from datetime import datetime, timedelta
import random

import structlog

# Add parent directory to path for imports
sys.path.insert(0, "/app")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.models import Card, Marketplace, AppSettings, PriceSnapshot
from app.models.settings import DEFAULT_SETTINGS
from app.services.ingestion.scryfall import ScryfallAdapter

logger = structlog.get_logger()


# Default marketplaces to create
DEFAULT_MARKETPLACES = [
    {
        "name": "TCGPlayer",
        "slug": "tcgplayer",
        "base_url": "https://www.tcgplayer.com",
        "api_url": "https://api.tcgplayer.com",
        "is_enabled": True,
        "supports_api": True,
        "default_currency": "USD",
        "rate_limit_seconds": 1.0,
    },
    {
        "name": "Cardmarket",
        "slug": "cardmarket",
        "base_url": "https://www.cardmarket.com",
        "api_url": "https://api.cardmarket.com",
        "is_enabled": True,
        "supports_api": True,
        "default_currency": "EUR",
        "rate_limit_seconds": 1.0,
    },
    {
        "name": "Card Kingdom",
        "slug": "cardkingdom",
        "base_url": "https://www.cardkingdom.com",
        "is_enabled": True,
        "supports_api": False,
        "default_currency": "USD",
        "rate_limit_seconds": 2.0,
    },
    {
        "name": "SCG (Star City Games)",
        "slug": "scg",
        "base_url": "https://starcitygames.com",
        "is_enabled": False,
        "supports_api": False,
        "default_currency": "USD",
        "rate_limit_seconds": 2.0,
    },
    {
        "name": "CoolStuffInc",
        "slug": "coolstuffinc",
        "base_url": "https://www.coolstuffinc.com",
        "is_enabled": False,
        "supports_api": False,
        "default_currency": "USD",
        "rate_limit_seconds": 2.0,
    },
    {
        "name": "Mock Market",
        "slug": "mock",
        "base_url": "https://mock-marketplace.example.com",
        "is_enabled": True,  # Enable for testing listings
        "supports_api": False,
        "default_currency": "USD",
        "rate_limit_seconds": 0.1,  # Fast for testing
    },
]

# Popular sets to seed (recent Standard + popular older sets)
SEED_SETS = [
    "MKM",  # Murders at Karlov Manor
    "LCI",  # Lost Caverns of Ixalan
    "WOE",  # Wilds of Eldraine
    "MOM",  # March of the Machine
    "ONE",  # Phyrexia: All Will Be One
]


async def seed_marketplaces(db: AsyncSession) -> int:
    """Seed default marketplace records."""
    created = 0
    
    for mp_data in DEFAULT_MARKETPLACES:
        # Check if exists
        query = select(Marketplace).where(Marketplace.slug == mp_data["slug"])
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        
        if not existing:
            marketplace = Marketplace(**mp_data)
            db.add(marketplace)
            created += 1
            logger.info("Created marketplace", name=mp_data["name"])
    
    await db.flush()
    return created


async def seed_settings(db: AsyncSession) -> int:
    """
    Seed default application settings for the system user.
    
    Note: Settings are now per-user. This seeds settings for the system user
    which can be used as defaults for global operations like recommendations.
    """
    from app.models.user import User
    
    # Get or create system user
    system_user_query = select(User).where(User.username == "system")
    system_result = await db.execute(system_user_query)
    system_user = system_result.scalar_one_or_none()
    
    if not system_user:
        logger.warning("System user not found, skipping settings seed")
        return 0
    
    created = 0
    
    for key, data in DEFAULT_SETTINGS.items():
        query = select(AppSettings).where(
            AppSettings.user_id == system_user.id,
            AppSettings.key == key
        )
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        
        if not existing:
            setting = AppSettings(
                user_id=system_user.id,
                key=key,
                value=data["value"],
                description=data["description"],
                value_type=data["value_type"],
            )
            db.add(setting)
            created += 1
    
    await db.flush()
    return created


async def seed_cards_from_scryfall(
    db: AsyncSession,
    set_codes: list[str],
    cards_per_set: int = 50,
) -> int:
    """
    Seed cards from Scryfall.
    
    Args:
        db: Database session.
        set_codes: Set codes to fetch.
        cards_per_set: Max cards to fetch per set.
        
    Returns:
        Number of cards created.
    """
    adapter = ScryfallAdapter()
    total_created = 0
    
    for set_code in set_codes:
        try:
            logger.info("Fetching cards from set", set_code=set_code)
            
            # Search for cards in set, prioritizing rares and mythics
            search_query = f"set:{set_code.lower()} (rarity:rare OR rarity:mythic)"
            cards_data = await adapter.search_cards(search_query, limit=cards_per_set)
            
            for card_data in cards_data:
                # Check if exists
                query = select(Card).where(Card.scryfall_id == card_data["scryfall_id"])
                result = await db.execute(query)
                existing = result.scalar_one_or_none()
                
                if not existing:
                    card = Card(
                        scryfall_id=card_data["scryfall_id"],
                        oracle_id=card_data.get("oracle_id"),
                        name=card_data["name"],
                        set_code=card_data["set_code"],
                        set_name=card_data.get("set_name"),
                        collector_number=card_data["collector_number"],
                        rarity=card_data.get("rarity"),
                        mana_cost=card_data.get("mana_cost"),
                        cmc=card_data.get("cmc"),
                        type_line=card_data.get("type_line"),
                        oracle_text=card_data.get("oracle_text"),
                        colors=card_data.get("colors"),
                        color_identity=card_data.get("color_identity"),
                        power=card_data.get("power"),
                        toughness=card_data.get("toughness"),
                        legalities=card_data.get("legalities"),
                        image_url=card_data.get("image_url"),
                        image_url_small=card_data.get("image_url_small"),
                        image_url_large=card_data.get("image_url_large"),
                    )
                    db.add(card)
                    total_created += 1
            
            await db.flush()
            logger.info("Seeded cards from set", set_code=set_code, count=len(cards_data))
            
        except Exception as e:
            logger.error("Failed to seed set", set_code=set_code, error=str(e))
    
    await adapter.close()
    return total_created


async def seed_sample_prices(db: AsyncSession) -> int:
    """
    Generate sample price data for seeded cards.
    
    This creates mock historical data for demonstration purposes.
    """
    # Get all cards and marketplaces
    cards_result = await db.execute(select(Card).limit(100))
    cards = cards_result.scalars().all()
    
    mp_result = await db.execute(select(Marketplace).where(Marketplace.is_enabled == True))
    marketplaces = mp_result.scalars().all()
    
    if not cards or not marketplaces:
        return 0
    
    created = 0
    now = datetime.utcnow()
    
    for card in cards:
        # Generate base price based on rarity
        rarity_prices = {
            "common": (0.10, 0.50),
            "uncommon": (0.25, 2.00),
            "rare": (1.00, 25.00),
            "mythic": (5.00, 100.00),
        }
        min_price, max_price = rarity_prices.get(card.rarity, (0.50, 10.00))
        base_price = random.uniform(min_price, max_price)
        
        # Generate 30 days of history for each marketplace
        for marketplace in marketplaces:
            current_price = base_price
            
            for days_ago in range(30, -1, -1):
                # Random walk the price
                change = random.uniform(-0.05, 0.05)
                current_price *= (1 + change)
                current_price = max(0.10, current_price)
                
                # Add some marketplace-specific variance
                mp_price = current_price * random.uniform(0.90, 1.15)
                
                # Create snapshot
                snapshot = PriceSnapshot(
                    card_id=card.id,
                    marketplace_id=marketplace.id,
                    snapshot_time=now - timedelta(days=days_ago),
                    price=round(mp_price, 2),
                    currency=marketplace.default_currency,
                    min_price=round(mp_price * 0.9, 2),
                    max_price=round(mp_price * 1.1, 2),
                    avg_price=round(mp_price, 2),
                    num_listings=random.randint(5, 50),
                    total_quantity=random.randint(10, 200),
                )
                db.add(snapshot)
                created += 1
        
        # Flush periodically
        if created % 500 == 0:
            await db.flush()
    
    await db.flush()
    return created


async def main():
    """Main seed function."""
    logger.info("Starting database seed")
    
    async with async_session_maker() as db:
        try:
            # Seed marketplaces
            mp_count = await seed_marketplaces(db)
            logger.info("Seeded marketplaces", count=mp_count)
            
            # Seed settings
            settings_count = await seed_settings(db)
            logger.info("Seeded settings", count=settings_count)
            
            # Seed cards from Scryfall
            cards_count = await seed_cards_from_scryfall(
                db, SEED_SETS, cards_per_set=30
            )
            logger.info("Seeded cards", count=cards_count)
            
            # Seed sample prices
            prices_count = await seed_sample_prices(db)
            logger.info("Seeded price snapshots", count=prices_count)
            
            # Commit all changes
            await db.commit()
            
            logger.info(
                "Database seed completed",
                marketplaces=mp_count,
                settings=settings_count,
                cards=cards_count,
                prices=prices_count,
            )
            
        except Exception as e:
            logger.error("Seed failed", error=str(e))
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())

