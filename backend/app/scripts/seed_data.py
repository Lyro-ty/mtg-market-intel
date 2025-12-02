"""
Seed data script for initial database population.

This script populates the database with:
- Default marketplace records
- Default settings
- Sample cards from popular sets (via Scryfall)
- Optionally: Real scraped price data from marketplaces

Usage:
    # Seed with mock data (default)
    python -m app.scripts.seed_data
    
    # Seed with real scraped data
    python -m app.scripts.seed_data --scrape-prices
    
    # Seed with scraped data for specific marketplaces only
    python -m app.scripts.seed_data --scrape-prices --marketplaces tcgplayer cardmarket
"""
import asyncio
import sys
import argparse
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
    # Note: Mock marketplace removed - use add_mock_marketplace.py if needed for testing
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


async def seed_with_scraped_data(
    db: AsyncSession,
    marketplace_slugs: list[str] | None = None,
    card_limit: int = 100,
) -> int:
    """
    Seed price data by scraping real marketplaces.
    
    Args:
        db: Database session.
        marketplace_slugs: List of marketplace slugs to scrape. If None, uses all enabled.
        card_limit: Maximum number of cards to scrape prices for.
        
    Returns:
        Number of price snapshots created.
    """
    from app.services.ingestion import get_adapter
    from app.services.agents.normalization import NormalizationService
    
    # Get marketplaces to scrape
    if marketplace_slugs:
        query = select(Marketplace).where(
            Marketplace.slug.in_(marketplace_slugs),
            Marketplace.is_enabled == True
        )
    else:
        query = select(Marketplace).where(Marketplace.is_enabled == True)
    
    result = await db.execute(query)
    marketplaces = result.scalars().all()
    
    if not marketplaces:
        logger.warning("No enabled marketplaces found for scraping")
        return 0
    
    # Get cards to scrape (limit to recent cards)
    cards_query = select(Card).order_by(Card.id.desc()).limit(card_limit)
    result = await db.execute(cards_query)
    cards = list(result.scalars().all())
    
    if not cards:
        logger.warning("No cards found to scrape")
        return 0
    
    logger.info(
        "Starting price scraping",
        marketplaces=[mp.slug for mp in marketplaces],
        cards=len(cards)
    )
    
    normalizer = NormalizationService(db)
    total_snapshots = 0
    
    try:
        for marketplace in marketplaces:
            try:
                adapter = get_adapter(marketplace.slug, cached=False)
                logger.info("Scraping marketplace", marketplace=marketplace.slug)
                
                for card in cards:
                    try:
                        # Fetch price data
                        price_data = await adapter.fetch_price(
                            card_name=card.name,
                            set_code=card.set_code,
                            collector_number=card.collector_number,
                            scryfall_id=card.scryfall_id,
                        )
                        
                        if price_data and price_data.price > 0:
                            # Create price snapshot
                            snapshot = PriceSnapshot(
                                card_id=card.id,
                                marketplace_id=marketplace.id,
                                snapshot_time=datetime.utcnow(),
                                price=price_data.price,
                                currency=price_data.currency,
                                price_foil=price_data.price_foil,
                                min_price=price_data.price_low,
                                max_price=price_data.price_high,
                                avg_price=price_data.price_mid,
                                median_price=price_data.price_market,
                                num_listings=price_data.num_listings,
                                total_quantity=price_data.total_quantity,
                            )
                            db.add(snapshot)
                            total_snapshots += 1
                            
                            # Flush periodically to avoid memory issues
                            if total_snapshots % 50 == 0:
                                await db.flush()
                                logger.debug("Flushed snapshots", count=total_snapshots)
                    
                    except Exception as e:
                        logger.warning(
                            "Failed to scrape card",
                            card=card.name,
                            marketplace=marketplace.slug,
                            error=str(e)
                        )
                        continue
                
                # Close adapter
                if hasattr(adapter, 'close'):
                    await adapter.close()
                
                await db.flush()
                logger.info(
                    "Completed scraping marketplace",
                    marketplace=marketplace.slug,
                    snapshots=total_snapshots
                )
            
            except Exception as e:
                logger.error(
                    "Failed to scrape marketplace",
                    marketplace=marketplace.slug,
                    error=str(e)
                )
                continue
    
    finally:
        await normalizer.close()
    
    return total_snapshots


async def main():
    """Main seed function."""
    parser = argparse.ArgumentParser(description="Seed database with initial data")
    parser.add_argument(
        "--scrape-prices",
        action="store_true",
        help="Scrape real price data from marketplaces instead of generating mock data"
    )
    parser.add_argument(
        "--marketplaces",
        nargs="+",
        help="Specific marketplace slugs to scrape (only used with --scrape-prices)"
    )
    parser.add_argument(
        "--card-limit",
        type=int,
        default=100,
        help="Maximum number of cards to scrape prices for (default: 100)"
    )
    parser.add_argument(
        "--cards-per-set",
        type=int,
        default=30,
        help="Number of cards to fetch per set from Scryfall (default: 30)"
    )
    
    args = parser.parse_args()
    
    logger.info("Starting database seed", scrape_prices=args.scrape_prices)
    
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
                db, SEED_SETS, cards_per_set=args.cards_per_set
            )
            logger.info("Seeded cards", count=cards_count)
            
            # Seed prices (either scraped or mock)
            if args.scrape_prices:
                logger.info("Scraping real price data from marketplaces")
                prices_count = await seed_with_scraped_data(
                    db,
                    marketplace_slugs=args.marketplaces,
                    card_limit=args.card_limit
                )
                logger.info("Scraped price snapshots", count=prices_count)
            else:
                logger.info("Generating mock price data")
                prices_count = await seed_sample_prices(db)
                logger.info("Seeded mock price snapshots", count=prices_count)
            
            # Commit all changes
            await db.commit()
            
            logger.info(
                "Database seed completed",
                marketplaces=mp_count,
                settings=settings_count,
                cards=cards_count,
                prices=prices_count,
                data_source="scraped" if args.scrape_prices else "mock",
            )
            
        except Exception as e:
            logger.error("Seed failed", error=str(e))
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())

