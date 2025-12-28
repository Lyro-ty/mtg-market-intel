"""
Generate synthetic multi-day price history for demo/testing.

This utility is useful after importing the full Scryfall catalog so the UI
has historical price data (including Card Kingdom) to render metrics and
charts without waiting for real marketplace ingestion to run for weeks.
"""
import argparse
import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.db.session import async_session_maker
from app.models.card import Card
from app.models.marketplace import Marketplace
from app.models.price_snapshot import PriceSnapshot


RARITY_PRICE_RANGES = {
    "common": (0.08, 0.45),
    "uncommon": (0.20, 1.50),
    "rare": (0.80, 20.0),
    "mythic": (3.0, 75.0),
}


async def generate_history(
    card_limit: int,
    days: int,
    marketplaces: list[str] | None,
    purge_existing: bool,
    seed: int | None,
) -> dict[str, int]:
    """Generate synthetic history for the requested subset."""
    if seed is not None:
        random.seed(seed)
    
    async with async_session_maker() as session:
        card_query = select(Card).order_by(Card.id)
        if card_limit:
            card_query = card_query.limit(card_limit)
        cards = (await session.execute(card_query)).scalars().all()
        
        if not cards:
            return {"cards": 0, "snapshots": 0}
        
        marketplace_query = select(Marketplace).where(Marketplace.is_enabled == True)
        if marketplaces:
            marketplace_query = marketplace_query.where(Marketplace.slug.in_(marketplaces))
        marketplace_rows = (await session.execute(marketplace_query)).scalars().all()
        
        if not marketplace_rows:
            return {"cards": len(cards), "snapshots": 0}
        
        card_ids = [c.id for c in cards]
        marketplace_ids = [m.id for m in marketplace_rows]
        
        now = datetime.now(tz=timezone.utc)
        horizon = now - timedelta(days=days + 1)
        
        if purge_existing:
            await session.execute(
                delete(PriceSnapshot)
                .where(PriceSnapshot.card_id.in_(card_ids))
                .where(PriceSnapshot.marketplace_id.in_(marketplace_ids))
                .where(PriceSnapshot.time >= horizon)
            )
            await session.commit()
        
        snapshots_created = 0
        for card in cards:
            rarity_range = RARITY_PRICE_RANGES.get(card.rarity or "", (0.25, 8.0))
            base_price = random.uniform(*rarity_range)
            
            for marketplace in marketplace_rows:
                price = base_price * random.uniform(0.9, 1.1)
                
                for day in range(days, -1, -1):
                    snapshot_time = now - timedelta(days=day)
                    delta = random.uniform(-0.04, 0.04)
                    price = max(0.05, price * (1 + delta))
                    min_price = round(price * 0.92, 2)
                    max_price = round(price * 1.08, 2)
                    avg_price = round(price, 2)
                    
                    snapshot = PriceSnapshot(
                        card_id=card.id,
                        marketplace_id=marketplace.id,
                        snapshot_time=snapshot_time,
                        price=avg_price,
                        currency=marketplace.default_currency,
                        min_price=min_price,
                        max_price=max_price,
                        avg_price=avg_price,
                        median_price=avg_price,
                        price_foil=avg_price * 1.35 if card.rarity in {"rare", "mythic"} else None,
                        num_listings=random.randint(5, 60),
                        total_quantity=random.randint(10, 250),
                    )
                    session.add(snapshot)
                    snapshots_created += 1
                    
                    if snapshots_created % 2000 == 0:
                        await session.flush()
        
        await session.commit()
        return {
            "cards": len(cards),
            "marketplaces": len(marketplace_rows),
            "snapshots": snapshots_created,
        }


async def main():
    parser = argparse.ArgumentParser(description="Generate synthetic price history")
    parser.add_argument(
        "--card-limit",
        type=int,
        default=250,
        help="Number of cards to backfill (default: 250)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days of history to synthesize (default: 30)",
    )
    parser.add_argument(
        "--marketplaces",
        nargs="*",
        help="Optional list of marketplace slugs (default: all enabled)",
    )
    parser.add_argument(
        "--no-purge",
        action="store_true",
        help="Do not delete overlapping snapshots before generating",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Random seed for reproducible results",
    )
    args = parser.parse_args()
    
    results = await generate_history(
        card_limit=max(args.card_limit, 1),
        days=max(args.days, 1),
        marketplaces=args.marketplaces,
        purge_existing=not args.no_purge,
        seed=args.seed,
    )
    
    print(
        f"Generated {results.get('snapshots', 0):,} snapshots "
        f"for {results.get('cards', 0)} cards across "
        f"{results.get('marketplaces', 0)} marketplaces."
    )


if __name__ == "__main__":
    asyncio.run(main())

