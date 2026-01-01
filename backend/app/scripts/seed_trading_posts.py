"""
Seed Trading Posts and Events for testing.

Creates sample LGS (Local Game Store) data with events.

Usage:
    python -m app.scripts.seed_trading_posts
"""
import asyncio
import sys
from datetime import datetime, timedelta
from decimal import Decimal
import random

import structlog

sys.path.insert(0, "/app")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.models.user import User
from app.models.trading_post import TradingPost, TradingPostEvent, EventType

logger = structlog.get_logger()

# Sample trading posts data
TRADING_POSTS = [
    {
        "store_name": "Dragon's Lair Games",
        "description": "Austin's premier gaming destination since 1996. We offer a wide selection of Magic singles, sealed product, and host daily events.",
        "address": "2438 West Anderson Lane",
        "city": "Austin",
        "state": "TX",
        "postal_code": "78757",
        "website": "https://dlair.net",
        "phone": "(512) 454-2399",
        "services": ["Singles", "Sealed Product", "Buylist", "Tournaments", "Commander Nights", "Draft Events", "Pre-releases"],
        "buylist_margin": Decimal("0.55"),
        "hours": {
            "monday": "11:00 AM - 10:00 PM",
            "tuesday": "11:00 AM - 10:00 PM",
            "wednesday": "11:00 AM - 10:00 PM",
            "thursday": "11:00 AM - 10:00 PM",
            "friday": "11:00 AM - 11:00 PM",
            "saturday": "10:00 AM - 11:00 PM",
            "sunday": "12:00 PM - 8:00 PM",
        },
        "verified": True,
    },
    {
        "store_name": "Card Kingdom",
        "description": "Seattle's legendary game store and online retailer. Massive selection of singles, competitive buylist prices, and the famous Cafe Mox.",
        "address": "5105 Leary Ave NW",
        "city": "Seattle",
        "state": "WA",
        "postal_code": "98107",
        "website": "https://www.cardkingdom.com",
        "phone": "(206) 523-2273",
        "services": ["Singles", "Sealed Product", "Buylist", "Tournaments", "Commander Nights", "Pre-releases", "Card Grading"],
        "buylist_margin": Decimal("0.60"),
        "hours": {
            "monday": "10:00 AM - 12:00 AM",
            "tuesday": "10:00 AM - 12:00 AM",
            "wednesday": "10:00 AM - 12:00 AM",
            "thursday": "10:00 AM - 12:00 AM",
            "friday": "10:00 AM - 12:00 AM",
            "saturday": "10:00 AM - 12:00 AM",
            "sunday": "10:00 AM - 12:00 AM",
        },
        "verified": True,
    },
    {
        "store_name": "Channel Fireball Game Center",
        "description": "Home of ChannelFireball.com, offering an incredible play space and competitive events in the Bay Area.",
        "address": "2855 Stevens Creek Blvd",
        "city": "Santa Clara",
        "state": "CA",
        "postal_code": "95050",
        "website": "https://store.channelfireball.com",
        "phone": "(408) 727-7171",
        "services": ["Singles", "Sealed Product", "Buylist", "Tournaments", "Draft Events", "Pre-releases"],
        "buylist_margin": Decimal("0.52"),
        "hours": {
            "monday": "12:00 PM - 10:00 PM",
            "tuesday": "12:00 PM - 10:00 PM",
            "wednesday": "12:00 PM - 10:00 PM",
            "thursday": "12:00 PM - 10:00 PM",
            "friday": "12:00 PM - 11:00 PM",
            "saturday": "11:00 AM - 11:00 PM",
            "sunday": "11:00 AM - 8:00 PM",
        },
        "verified": True,
    },
    {
        "store_name": "Face to Face Games Toronto",
        "description": "Canada's largest MTG retailer with an amazing play space. Weekly events, competitive buylist, and expert staff.",
        "address": "2737 Keele Street",
        "city": "Toronto",
        "state": "ON",
        "postal_code": "M3M 2G1",
        "website": "https://www.facetofacegames.com",
        "phone": "(416) 398-9588",
        "services": ["Singles", "Sealed Product", "Buylist", "Tournaments", "Commander Nights", "Draft Events", "Pre-releases"],
        "buylist_margin": Decimal("0.50"),
        "hours": {
            "monday": "11:00 AM - 9:00 PM",
            "tuesday": "11:00 AM - 9:00 PM",
            "wednesday": "11:00 AM - 9:00 PM",
            "thursday": "11:00 AM - 9:00 PM",
            "friday": "11:00 AM - 11:00 PM",
            "saturday": "10:00 AM - 10:00 PM",
            "sunday": "12:00 PM - 6:00 PM",
        },
        "verified": True,
    },
    {
        "store_name": "Mox Boarding House",
        "description": "Board game cafe and Magic haven in Bellevue. Great food, great games, and amazing Magic events.",
        "address": "13310 Bel-Red Rd",
        "city": "Bellevue",
        "state": "WA",
        "postal_code": "98005",
        "website": "https://www.moxboardinghouse.com",
        "phone": "(425) 586-1777",
        "services": ["Singles", "Sealed Product", "Tournaments", "Commander Nights", "Draft Events", "Pre-releases"],
        "buylist_margin": Decimal("0.48"),
        "hours": {
            "monday": "11:00 AM - 11:00 PM",
            "tuesday": "11:00 AM - 11:00 PM",
            "wednesday": "11:00 AM - 11:00 PM",
            "thursday": "11:00 AM - 11:00 PM",
            "friday": "11:00 AM - 12:00 AM",
            "saturday": "10:00 AM - 12:00 AM",
            "sunday": "10:00 AM - 10:00 PM",
        },
        "verified": True,
    },
    {
        "store_name": "Cool Stuff Games Orlando",
        "description": "Florida's premier gaming destination with multiple locations. Huge selection and active tournament scene.",
        "address": "12401 S Orange Blossom Trail",
        "city": "Orlando",
        "state": "FL",
        "postal_code": "32837",
        "website": "https://www.coolstuffinc.com",
        "phone": "(407) 601-5220",
        "services": ["Singles", "Sealed Product", "Buylist", "Tournaments", "Commander Nights", "Pre-releases"],
        "buylist_margin": Decimal("0.53"),
        "hours": {
            "monday": "11:00 AM - 9:00 PM",
            "tuesday": "11:00 AM - 9:00 PM",
            "wednesday": "11:00 AM - 9:00 PM",
            "thursday": "11:00 AM - 9:00 PM",
            "friday": "11:00 AM - 11:00 PM",
            "saturday": "10:00 AM - 11:00 PM",
            "sunday": "12:00 PM - 7:00 PM",
        },
        "verified": True,
    },
    {
        "store_name": "Pandemonium Books & Games",
        "description": "Cambridge's friendly local game store. Community-focused with great events and competitive prices.",
        "address": "4 Pleasant Street",
        "city": "Cambridge",
        "state": "MA",
        "postal_code": "02139",
        "website": "https://www.pandemoniumbooks.com",
        "phone": "(617) 547-3721",
        "services": ["Singles", "Sealed Product", "Tournaments", "Commander Nights", "Draft Events"],
        "buylist_margin": Decimal("0.45"),
        "hours": {
            "monday": "10:00 AM - 8:00 PM",
            "tuesday": "10:00 AM - 8:00 PM",
            "wednesday": "10:00 AM - 9:00 PM",
            "thursday": "10:00 AM - 9:00 PM",
            "friday": "10:00 AM - 9:00 PM",
            "saturday": "10:00 AM - 8:00 PM",
            "sunday": "12:00 PM - 6:00 PM",
        },
        "verified": False,
    },
    {
        "store_name": "The Game Cave",
        "description": "Your local game store in Denver! We specialize in MTG singles and host regular FNM and weekend events.",
        "address": "1440 S Broadway",
        "city": "Denver",
        "state": "CO",
        "postal_code": "80210",
        "website": "https://thegamecave.com",
        "phone": "(303) 777-2846",
        "services": ["Singles", "Sealed Product", "Buylist", "Tournaments", "Commander Nights"],
        "buylist_margin": Decimal("0.50"),
        "hours": {
            "monday": "Closed",
            "tuesday": "12:00 PM - 8:00 PM",
            "wednesday": "12:00 PM - 10:00 PM",
            "thursday": "12:00 PM - 8:00 PM",
            "friday": "12:00 PM - 10:00 PM",
            "saturday": "11:00 AM - 10:00 PM",
            "sunday": "12:00 PM - 6:00 PM",
        },
        "verified": False,
    },
    {
        "store_name": "Star City Games Retail Store",
        "description": "The legendary SCG retail location in Roanoke, VA. Home of the SCG Tour and premium singles.",
        "address": "5728 Williamson Rd",
        "city": "Roanoke",
        "state": "VA",
        "postal_code": "24012",
        "website": "https://starcitygames.com",
        "phone": "(540) 362-4400",
        "services": ["Singles", "Sealed Product", "Buylist", "Tournaments", "Pre-releases", "Card Grading"],
        "buylist_margin": Decimal("0.58"),
        "hours": {
            "monday": "10:00 AM - 7:00 PM",
            "tuesday": "10:00 AM - 7:00 PM",
            "wednesday": "10:00 AM - 7:00 PM",
            "thursday": "10:00 AM - 7:00 PM",
            "friday": "10:00 AM - 9:00 PM",
            "saturday": "10:00 AM - 9:00 PM",
            "sunday": "12:00 PM - 6:00 PM",
        },
        "verified": True,
    },
    {
        "store_name": "MTG Deals Chicago",
        "description": "Chicago's newest MTG singles destination. Competitive buylist and growing tournament scene.",
        "address": "1555 N Damen Ave",
        "city": "Chicago",
        "state": "IL",
        "postal_code": "60622",
        "website": "https://mtgdealschicago.com",
        "phone": "(312) 555-0123",
        "services": ["Singles", "Buylist", "Tournaments", "Commander Nights"],
        "buylist_margin": Decimal("0.55"),
        "hours": {
            "monday": "Closed",
            "tuesday": "2:00 PM - 9:00 PM",
            "wednesday": "2:00 PM - 9:00 PM",
            "thursday": "2:00 PM - 9:00 PM",
            "friday": "2:00 PM - 11:00 PM",
            "saturday": "11:00 AM - 11:00 PM",
            "sunday": "11:00 AM - 7:00 PM",
        },
        "verified": False,
    },
]

# Event templates
EVENT_TEMPLATES = [
    # Tournaments
    {
        "title": "Friday Night Magic - Modern",
        "description": "Weekly Modern tournament. Swiss rounds, prizes based on record.",
        "event_type": EventType.TOURNAMENT.value,
        "format": "Modern",
        "entry_fee": Decimal("15.00"),
        "max_players": 32,
        "day_offset": 4,  # Friday
    },
    {
        "title": "Friday Night Magic - Standard",
        "description": "Weekly Standard tournament. Swiss rounds, prizes based on record.",
        "event_type": EventType.TOURNAMENT.value,
        "format": "Standard",
        "entry_fee": Decimal("10.00"),
        "max_players": 24,
        "day_offset": 4,  # Friday
    },
    {
        "title": "Commander Night",
        "description": "Casual Commander pods. All power levels welcome!",
        "event_type": EventType.MEETUP.value,
        "format": "Commander",
        "entry_fee": Decimal("5.00"),
        "max_players": 40,
        "day_offset": 2,  # Wednesday
    },
    {
        "title": "Pioneer Weekly",
        "description": "Weekly Pioneer tournament. Great practice for RCQs!",
        "event_type": EventType.TOURNAMENT.value,
        "format": "Pioneer",
        "entry_fee": Decimal("12.00"),
        "max_players": 24,
        "day_offset": 5,  # Saturday
    },
    {
        "title": "Draft Night",
        "description": "8-player draft pods. Current set release.",
        "event_type": EventType.TOURNAMENT.value,
        "format": "Draft",
        "entry_fee": Decimal("18.00"),
        "max_players": 16,
        "day_offset": 6,  # Sunday
    },
    {
        "title": "Legacy Monthly",
        "description": "Monthly Legacy tournament with special prizes!",
        "event_type": EventType.TOURNAMENT.value,
        "format": "Legacy",
        "entry_fee": Decimal("25.00"),
        "max_players": 32,
        "day_offset": 12,  # Next week Saturday
    },
    # Sales
    {
        "title": "New Year Sale - 20% Off Singles",
        "description": "Start 2026 right! 20% off all singles over $5. In-store only.",
        "event_type": EventType.SALE.value,
        "format": None,
        "entry_fee": None,
        "max_players": None,
        "day_offset": 1,
    },
    {
        "title": "Buylist Bonus Week",
        "description": "Get 10% extra on all buylist trades this week!",
        "event_type": EventType.SALE.value,
        "format": None,
        "entry_fee": None,
        "max_players": None,
        "day_offset": 3,
    },
    # Releases
    {
        "title": "Aetherdrift Prerelease",
        "description": "Be the first to play with Aetherdrift! Multiple flights available.",
        "event_type": EventType.RELEASE.value,
        "format": "Sealed",
        "entry_fee": Decimal("35.00"),
        "max_players": 48,
        "day_offset": 14,
    },
    {
        "title": "Aetherdrift Launch Party",
        "description": "Celebrate the release of Aetherdrift! Drafts and prizes all day.",
        "event_type": EventType.RELEASE.value,
        "format": "Draft",
        "entry_fee": Decimal("20.00"),
        "max_players": 32,
        "day_offset": 21,
    },
    # Meetups
    {
        "title": "cEDH League Night",
        "description": "Competitive EDH league play. Bring your best deck!",
        "event_type": EventType.MEETUP.value,
        "format": "Commander",
        "entry_fee": Decimal("10.00"),
        "max_players": 20,
        "day_offset": 1,
    },
    {
        "title": "New Player Welcome Night",
        "description": "New to Magic? Join us for free learn-to-play sessions!",
        "event_type": EventType.MEETUP.value,
        "format": None,
        "entry_fee": Decimal("0.00"),
        "max_players": 12,
        "day_offset": 3,
    },
]


async def create_test_users(db: AsyncSession, count: int = 10) -> list[User]:
    """Create test users for trading post ownership."""
    from app.services.auth import get_password_hash

    users = []
    for i in range(count):
        username = f"store_owner_{i+1}"

        # Check if exists
        query = select(User).where(User.username == username)
        result = await db.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            users.append(existing)
            continue

        user = User(
            username=username,
            email=f"store{i+1}@example.com",
            hashed_password=get_password_hash("testpass123"),
            display_name=f"Store Owner {i+1}",
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        users.append(user)

    await db.flush()
    return users


async def seed_trading_posts(db: AsyncSession, users: list[User]) -> list[TradingPost]:
    """Seed trading posts with the provided users."""
    trading_posts = []

    for i, tp_data in enumerate(TRADING_POSTS):
        if i >= len(users):
            break

        user = users[i]

        # Check if user already has a trading post
        query = select(TradingPost).where(TradingPost.user_id == user.id)
        result = await db.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            trading_posts.append(existing)
            logger.info("Trading post already exists", store=existing.store_name)
            continue

        now = datetime.utcnow()
        trading_post = TradingPost(
            user_id=user.id,
            store_name=tp_data["store_name"],
            description=tp_data["description"],
            address=tp_data["address"],
            city=tp_data["city"],
            state=tp_data["state"],
            country="US" if tp_data["state"] != "ON" else "CA",
            postal_code=tp_data["postal_code"],
            phone=tp_data["phone"],
            website=tp_data["website"],
            hours=tp_data["hours"],
            services=tp_data["services"],
            buylist_margin=tp_data["buylist_margin"],
            email_verified_at=now if tp_data["verified"] else None,
            verified_at=now if tp_data["verified"] else None,
            verification_method="manual" if tp_data["verified"] else None,
        )
        db.add(trading_post)
        trading_posts.append(trading_post)
        logger.info("Created trading post", store=tp_data["store_name"])

    await db.flush()
    return trading_posts


async def seed_events(db: AsyncSession, trading_posts: list[TradingPost]) -> int:
    """Seed events for trading posts."""
    now = datetime.utcnow()
    # Start from today
    base_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

    event_count = 0

    for trading_post in trading_posts:
        # Check if store already has events
        query = select(TradingPostEvent).where(
            TradingPostEvent.trading_post_id == trading_post.id
        )
        result = await db.execute(query)
        existing_events = result.scalars().all()

        if len(existing_events) > 3:
            logger.info("Store already has events", store=trading_post.store_name)
            continue

        # Each store gets a random subset of events
        store_events = random.sample(EVENT_TEMPLATES, k=random.randint(4, len(EVENT_TEMPLATES)))

        for event_template in store_events:
            # Calculate event date
            event_date = base_date + timedelta(days=event_template["day_offset"])

            # Add some time variation
            hour = random.choice([17, 18, 19])  # 5-7 PM start
            if event_template["event_type"] == EventType.SALE.value:
                hour = 10  # Sales start at store open

            start_time = event_date.replace(hour=hour, minute=0)

            # End time 3-4 hours later for tournaments, all day for sales
            if event_template["event_type"] == EventType.SALE.value:
                end_time = start_time.replace(hour=21)
            else:
                end_time = start_time + timedelta(hours=random.randint(3, 5))

            event = TradingPostEvent(
                trading_post_id=trading_post.id,
                title=event_template["title"],
                description=event_template["description"],
                event_type=event_template["event_type"],
                format=event_template["format"],
                start_time=start_time,
                end_time=end_time,
                entry_fee=event_template["entry_fee"],
                max_players=event_template["max_players"],
            )
            db.add(event)
            event_count += 1

        logger.info(
            "Created events for store",
            store=trading_post.store_name,
            event_count=len(store_events)
        )

    await db.flush()
    return event_count


async def main():
    """Main seed function."""
    logger.info("Starting trading posts seed")

    async with async_session_maker() as db:
        try:
            # Create test users
            users = await create_test_users(db, count=len(TRADING_POSTS))
            logger.info("Created/found test users", count=len(users))

            # Seed trading posts
            trading_posts = await seed_trading_posts(db, users)
            logger.info("Seeded trading posts", count=len(trading_posts))

            # Seed events
            event_count = await seed_events(db, trading_posts)
            logger.info("Seeded events", count=event_count)

            # Commit
            await db.commit()

            logger.info(
                "Trading posts seed completed",
                trading_posts=len(trading_posts),
                events=event_count,
            )

        except Exception as e:
            logger.error("Seed failed", error=str(e))
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())
