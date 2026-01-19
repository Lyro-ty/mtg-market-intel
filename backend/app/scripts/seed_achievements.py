"""
Seed Achievement Definitions for the social trading platform.

Achievement definitions unlock frame tiers and boost discovery priority.

Usage:
    python -m app.scripts.seed_achievements
"""
import asyncio
import sys

import structlog

# Add parent directory to path for imports
sys.path.insert(0, "/app")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.models.achievement import AchievementDefinition

logger = structlog.get_logger()


# Achievement definitions organized by category
ACHIEVEMENT_DEFINITIONS = [
    # ============================================================
    # Trade Milestones - Unlock frames through trading activity
    # ============================================================
    {
        "key": "first_deal",
        "name": "First Deal",
        "description": "Complete your first trade",
        "category": "trade",
        "icon": "handshake",
        "threshold": {"trades": 1},
        "discovery_points": 5,
        "frame_tier_unlock": None,
        "is_hidden": False,
        "is_seasonal": False,
    },
    {
        "key": "regular_trader",
        "name": "Regular Trader",
        "description": "Complete 10 trades",
        "category": "trade",
        "icon": "scale",
        "threshold": {"trades": 10},
        "discovery_points": 15,
        "frame_tier_unlock": "silver",
        "is_hidden": False,
        "is_seasonal": False,
    },
    {
        "key": "seasoned_dealer",
        "name": "Seasoned Dealer",
        "description": "Complete 50 trades",
        "category": "trade",
        "icon": "coins",
        "threshold": {"trades": 50},
        "discovery_points": 30,
        "frame_tier_unlock": "gold",
        "is_hidden": False,
        "is_seasonal": False,
    },
    {
        "key": "trade_master",
        "name": "Trade Master",
        "description": "Complete 100 trades",
        "category": "trade",
        "icon": "scroll",
        "threshold": {"trades": 100},
        "discovery_points": 50,
        "frame_tier_unlock": "platinum",
        "is_hidden": False,
        "is_seasonal": False,
    },
    {
        "key": "market_legend",
        "name": "Market Legend",
        "description": "Complete 500 trades",
        "category": "trade",
        "icon": "crown",
        "threshold": {"trades": 500},
        "discovery_points": 100,
        "frame_tier_unlock": "legendary",
        "is_hidden": False,
        "is_seasonal": False,
    },
    # ============================================================
    # Reputation Tiers - Unlock frames through positive reviews
    # ============================================================
    {
        "key": "newcomer",
        "name": "Newcomer",
        "description": "Start your trading journey",
        "category": "reputation",
        "icon": "seedling",
        "threshold": {"reviews": 0},
        "discovery_points": 10,
        "frame_tier_unlock": None,
        "is_hidden": False,
        "is_seasonal": False,
    },
    {
        "key": "established",
        "name": "Established",
        "description": "5+ reviews with 4.0+ average",
        "category": "reputation",
        "icon": "tree",
        "threshold": {"reviews": 5, "avg_rating": 4.0},
        "discovery_points": 30,
        "frame_tier_unlock": "silver",
        "is_hidden": False,
        "is_seasonal": False,
    },
    {
        "key": "trusted",
        "name": "Trusted",
        "description": "20+ reviews with 4.5+ average",
        "category": "reputation",
        "icon": "shield",
        "threshold": {"reviews": 20, "avg_rating": 4.5},
        "discovery_points": 60,
        "frame_tier_unlock": "gold",
        "is_hidden": False,
        "is_seasonal": False,
    },
    {
        "key": "elite",
        "name": "Elite",
        "description": "50+ reviews with 4.7+ average",
        "category": "reputation",
        "icon": "temple",
        "threshold": {"reviews": 50, "avg_rating": 4.7},
        "discovery_points": 100,
        "frame_tier_unlock": "platinum",
        "is_hidden": False,
        "is_seasonal": False,
    },
    # ============================================================
    # Portfolio Value - Recognize collection milestones
    # ============================================================
    {
        "key": "starter_collection",
        "name": "Starter Collection",
        "description": "$100+ tracked portfolio",
        "category": "portfolio",
        "icon": "gem",
        "threshold": {"portfolio_value": 100},
        "discovery_points": 5,
        "frame_tier_unlock": None,
        "is_hidden": False,
        "is_seasonal": False,
    },
    {
        "key": "growing_hoard",
        "name": "Growing Hoard",
        "description": "$1,000+ tracked portfolio",
        "category": "portfolio",
        "icon": "chest",
        "threshold": {"portfolio_value": 1000},
        "discovery_points": 10,
        "frame_tier_unlock": "silver",
        "is_hidden": False,
        "is_seasonal": False,
    },
    {
        "key": "serious_collector",
        "name": "Serious Collector",
        "description": "$10,000+ tracked portfolio",
        "category": "portfolio",
        "icon": "trophy",
        "threshold": {"portfolio_value": 10000},
        "discovery_points": 20,
        "frame_tier_unlock": "gold",
        "is_hidden": False,
        "is_seasonal": False,
    },
    {
        "key": "dragons_hoard",
        "name": "Dragon's Hoard",
        "description": "$50,000+ tracked portfolio",
        "category": "portfolio",
        "icon": "dragon",
        "threshold": {"portfolio_value": 50000},
        "discovery_points": 35,
        "frame_tier_unlock": "platinum",
        "is_hidden": False,
        "is_seasonal": False,
    },
    {
        "key": "legendary_vault",
        "name": "Legendary Vault",
        "description": "$100,000+ tracked portfolio",
        "category": "portfolio",
        "icon": "castle",
        "threshold": {"portfolio_value": 100000},
        "discovery_points": 50,
        "frame_tier_unlock": "legendary",
        "is_hidden": False,
        "is_seasonal": False,
    },
    # ============================================================
    # Community Contribution - Reward helpful community members
    # ============================================================
    {
        "key": "friendly",
        "name": "Friendly",
        "description": "Give 5 endorsements",
        "category": "community",
        "icon": "hand-wave",
        "threshold": {"endorsements_given": 5},
        "discovery_points": 10,
        "frame_tier_unlock": None,
        "is_hidden": False,
        "is_seasonal": False,
    },
    {
        "key": "helpful",
        "name": "Helpful",
        "description": "Write 20 reviews",
        "category": "community",
        "icon": "pen",
        "threshold": {"reviews_written": 20},
        "discovery_points": 20,
        "frame_tier_unlock": None,
        "is_hidden": False,
        "is_seasonal": False,
    },
    {
        "key": "community_pillar",
        "name": "Community Pillar",
        "description": "Give 50+ endorsements",
        "category": "community",
        "icon": "pillar",
        "threshold": {"endorsements_given": 50},
        "discovery_points": 40,
        "frame_tier_unlock": "gold",
        "is_hidden": False,
        "is_seasonal": False,
    },
    {
        "key": "veteran",
        "name": "Veteran",
        "description": "1 year member",
        "category": "community",
        "icon": "calendar",
        "threshold": {"member_days": 365},
        "discovery_points": 25,
        "frame_tier_unlock": None,
        "is_hidden": False,
        "is_seasonal": False,
    },
    # ============================================================
    # Special Achievements - Unique accomplishments
    # ============================================================
    {
        "key": "negotiator",
        "name": "Negotiator",
        "description": "10 counter-offers accepted",
        "category": "special",
        "icon": "chess-pawn",
        "threshold": {"counter_offers_accepted": 10},
        "discovery_points": 25,
        "frame_tier_unlock": None,
        "is_hidden": False,
        "is_seasonal": False,
    },
    {
        "key": "big_deal",
        "name": "Big Deal",
        "description": "Single trade over $500",
        "category": "special",
        "icon": "diamond",
        "threshold": {"single_trade_value": 500},
        "discovery_points": 20,
        "frame_tier_unlock": None,
        "is_hidden": False,
        "is_seasonal": False,
    },
    {
        "key": "whale_trade",
        "name": "Whale Trade",
        "description": "Single trade over $2,000",
        "category": "special",
        "icon": "whale",
        "threshold": {"single_trade_value": 2000},
        "discovery_points": 40,
        "frame_tier_unlock": None,
        "is_hidden": False,
        "is_seasonal": False,
    },
    {
        "key": "perfect_record",
        "name": "Perfect Record",
        "description": "50+ trades with 100% success",
        "category": "special",
        "icon": "shield-check",
        "threshold": {"trades": 50, "success_rate": 100},
        "discovery_points": 50,
        "frame_tier_unlock": "platinum",
        "is_hidden": False,
        "is_seasonal": False,
    },
    {
        "key": "speed_dealer",
        "name": "Speed Dealer",
        "description": "10 trades completed within 24h",
        "category": "special",
        "icon": "lightning",
        "threshold": {"fast_trades": 10},
        "discovery_points": 15,
        "frame_tier_unlock": None,
        "is_hidden": False,
        "is_seasonal": False,
    },
    # ============================================================
    # Hidden Achievements - Surprise unlocks for special moments
    # ============================================================
    {
        "key": "night_owl",
        "name": "Night Owl",
        "description": "Complete a trade between 2-4 AM",
        "category": "special",
        "icon": "owl",
        "threshold": {"night_trade": True},
        "discovery_points": 10,
        "frame_tier_unlock": None,
        "is_hidden": True,
        "is_seasonal": False,
    },
    {
        "key": "early_bird",
        "name": "Early Bird",
        "description": "Complete a trade before 6 AM",
        "category": "special",
        "icon": "sunrise",
        "threshold": {"early_trade": True},
        "discovery_points": 10,
        "frame_tier_unlock": None,
        "is_hidden": True,
        "is_seasonal": False,
    },
    {
        "key": "weekend_warrior",
        "name": "Weekend Warrior",
        "description": "Complete 10 trades on weekends",
        "category": "special",
        "icon": "sword",
        "threshold": {"weekend_trades": 10},
        "discovery_points": 15,
        "frame_tier_unlock": None,
        "is_hidden": True,
        "is_seasonal": False,
    },
    {
        "key": "collector_supreme",
        "name": "Collector Supreme",
        "description": "Own a card worth over $1,000",
        "category": "portfolio",
        "icon": "star",
        "threshold": {"max_card_value": 1000},
        "discovery_points": 30,
        "frame_tier_unlock": None,
        "is_hidden": True,
        "is_seasonal": False,
    },
]


async def seed_achievements(db: AsyncSession) -> tuple[int, int]:
    """
    Seed achievement definitions.

    Returns:
        Tuple of (new achievements added, existing achievements skipped)
    """
    added = 0
    skipped = 0

    for ach_data in ACHIEVEMENT_DEFINITIONS:
        # Check if already exists
        result = await db.execute(
            select(AchievementDefinition).where(
                AchievementDefinition.key == ach_data["key"]
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.debug("Achievement already exists", key=ach_data["key"])
            skipped += 1
            continue

        achievement = AchievementDefinition(
            key=ach_data["key"],
            name=ach_data["name"],
            description=ach_data["description"],
            category=ach_data["category"],
            icon=ach_data["icon"],
            threshold=ach_data["threshold"],
            discovery_points=ach_data["discovery_points"],
            frame_tier_unlock=ach_data["frame_tier_unlock"],
            is_hidden=ach_data["is_hidden"],
            is_seasonal=ach_data["is_seasonal"],
        )
        db.add(achievement)
        added += 1
        logger.info("Created achievement", key=ach_data["key"], name=ach_data["name"])

    await db.flush()
    return added, skipped


async def main():
    """Main seed function."""
    logger.info("Starting achievement definitions seed")

    async with async_session_maker() as db:
        try:
            added, skipped = await seed_achievements(db)

            await db.commit()

            logger.info(
                "Achievement seed completed",
                added=added,
                skipped=skipped,
                total_definitions=len(ACHIEVEMENT_DEFINITIONS),
            )

        except Exception as e:
            logger.error("Seed failed", error=str(e))
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())
