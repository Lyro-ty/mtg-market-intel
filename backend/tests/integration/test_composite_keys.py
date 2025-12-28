"""
Integration tests for composite key operations on PriceSnapshot table.

These tests verify the behavior of the composite primary key:
(time, card_id, marketplace_id, condition, is_foil, language)

To run these tests:
    pytest tests/integration/test_composite_keys.py -v

Note: These tests require a running PostgreSQL/TimescaleDB instance.
They will be skipped if the database is unavailable.
"""
import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, and_, func, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.core.constants import CardCondition, CardLanguage
from app.models import Card, Marketplace, PriceSnapshot
from app.db.base import Base


# Skip all tests if not using PostgreSQL
pytestmark = pytest.mark.skipif(
    "sqlite" in settings.database_url.lower(),
    reason="Composite key tests require PostgreSQL/TimescaleDB"
)


# Note: event_loop fixture is now handled automatically by pytest-asyncio >= 0.23.0
# with asyncio_mode = "auto" in pytest.ini


@pytest.fixture(scope="module")
async def test_engine():
    """Create test database engine connected to real PostgreSQL."""
    # Use the real database URL from settings
    engine = create_async_engine(
        settings.database_url,
        echo=False,
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncSession:
    """Create test database session."""
    async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
async def test_card(db_session: AsyncSession) -> Card:
    """Create a test card for use in tests."""
    # Check if test card already exists
    result = await db_session.execute(
        select(Card).where(Card.scryfall_id == "test-composite-key-card")
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    card = Card(
        scryfall_id="test-composite-key-card",
        oracle_id="test-oracle-id",
        name="Test Composite Key Card",
        set_code="TST",
        set_name="Test Set",
        collector_number="001",
        rarity="rare",
    )
    db_session.add(card)
    await db_session.flush()
    return card


@pytest.fixture(scope="function")
async def test_marketplace(db_session: AsyncSession) -> Marketplace:
    """Create a test marketplace for use in tests."""
    # Check if test marketplace already exists
    result = await db_session.execute(
        select(Marketplace).where(Marketplace.slug == "test-composite-mp")
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    marketplace = Marketplace(
        name="Test Composite Marketplace",
        slug="test-composite-mp",
        base_url="https://test-composite.example.com",
        is_enabled=True,
        supports_api=True,
        default_currency="USD",
        rate_limit_seconds=1.0,
    )
    db_session.add(marketplace)
    await db_session.flush()
    return marketplace


class TestCompositeKeyInsert:
    """Tests for inserting price snapshots with composite keys."""

    async def test_insert_single_snapshot(
        self, db_session: AsyncSession, test_card: Card, test_marketplace: Marketplace
    ):
        """Test inserting a single price snapshot."""
        now = datetime.now(timezone.utc)

        snapshot = PriceSnapshot(
            time=now,
            card_id=test_card.id,
            marketplace_id=test_marketplace.id,
            condition=CardCondition.NEAR_MINT.value,
            is_foil=False,
            language=CardLanguage.ENGLISH.value,
            price=Decimal("10.99"),
            currency="USD",
        )
        db_session.add(snapshot)
        await db_session.flush()

        # Verify the snapshot was inserted
        result = await db_session.execute(
            select(PriceSnapshot).where(
                and_(
                    PriceSnapshot.card_id == test_card.id,
                    PriceSnapshot.marketplace_id == test_marketplace.id,
                    PriceSnapshot.time == now,
                )
            )
        )
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert float(fetched.price) == 10.99
        assert fetched.condition == CardCondition.NEAR_MINT.value

    async def test_insert_multiple_conditions(
        self, db_session: AsyncSession, test_card: Card, test_marketplace: Marketplace
    ):
        """Test inserting snapshots with different conditions at same time."""
        now = datetime.now(timezone.utc)

        conditions = [
            (CardCondition.MINT, Decimal("15.99")),
            (CardCondition.NEAR_MINT, Decimal("12.99")),
            (CardCondition.LIGHTLY_PLAYED, Decimal("10.99")),
            (CardCondition.MODERATELY_PLAYED, Decimal("8.99")),
        ]

        for condition, price in conditions:
            snapshot = PriceSnapshot(
                time=now,
                card_id=test_card.id,
                marketplace_id=test_marketplace.id,
                condition=condition.value,
                is_foil=False,
                language=CardLanguage.ENGLISH.value,
                price=price,
                currency="USD",
            )
            db_session.add(snapshot)

        await db_session.flush()

        # Verify all snapshots were inserted
        result = await db_session.execute(
            select(func.count(PriceSnapshot.time)).where(
                and_(
                    PriceSnapshot.card_id == test_card.id,
                    PriceSnapshot.marketplace_id == test_marketplace.id,
                    PriceSnapshot.time == now,
                )
            )
        )
        count = result.scalar()
        assert count == 4

    async def test_insert_foil_and_nonfoil(
        self, db_session: AsyncSession, test_card: Card, test_marketplace: Marketplace
    ):
        """Test inserting both foil and non-foil snapshots at same time."""
        now = datetime.now(timezone.utc)

        # Non-foil
        snapshot_regular = PriceSnapshot(
            time=now,
            card_id=test_card.id,
            marketplace_id=test_marketplace.id,
            condition=CardCondition.NEAR_MINT.value,
            is_foil=False,
            language=CardLanguage.ENGLISH.value,
            price=Decimal("10.99"),
            currency="USD",
        )

        # Foil
        snapshot_foil = PriceSnapshot(
            time=now,
            card_id=test_card.id,
            marketplace_id=test_marketplace.id,
            condition=CardCondition.NEAR_MINT.value,
            is_foil=True,
            language=CardLanguage.ENGLISH.value,
            price=Decimal("25.99"),
            currency="USD",
        )

        db_session.add(snapshot_regular)
        db_session.add(snapshot_foil)
        await db_session.flush()

        # Verify both were inserted (one foil, one non-foil)
        result = await db_session.execute(
            select(PriceSnapshot).where(
                and_(
                    PriceSnapshot.card_id == test_card.id,
                    PriceSnapshot.marketplace_id == test_marketplace.id,
                    PriceSnapshot.time == now,
                    PriceSnapshot.condition == CardCondition.NEAR_MINT.value,
                )
            )
        )
        snapshots = result.scalars().all()
        assert len(snapshots) == 2

        prices = {s.is_foil: float(s.price) for s in snapshots}
        assert prices[False] == 10.99
        assert prices[True] == 25.99

    async def test_insert_multiple_languages(
        self, db_session: AsyncSession, test_card: Card, test_marketplace: Marketplace
    ):
        """Test inserting snapshots with different languages at same time."""
        now = datetime.now(timezone.utc)

        languages = [
            (CardLanguage.ENGLISH, Decimal("10.99")),
            (CardLanguage.JAPANESE, Decimal("15.99")),
            (CardLanguage.GERMAN, Decimal("9.99")),
        ]

        for language, price in languages:
            snapshot = PriceSnapshot(
                time=now,
                card_id=test_card.id,
                marketplace_id=test_marketplace.id,
                condition=CardCondition.NEAR_MINT.value,
                is_foil=False,
                language=language.value,
                price=price,
                currency="USD",
            )
            db_session.add(snapshot)

        await db_session.flush()

        # Verify all were inserted
        result = await db_session.execute(
            select(func.count(PriceSnapshot.time)).where(
                and_(
                    PriceSnapshot.card_id == test_card.id,
                    PriceSnapshot.marketplace_id == test_marketplace.id,
                    PriceSnapshot.time == now,
                )
            )
        )
        count = result.scalar()
        assert count == 3


class TestCompositeKeyUpsert:
    """Tests for upsert operations with composite keys."""

    async def test_upsert_insert_new(
        self, db_session: AsyncSession, test_card: Card, test_marketplace: Marketplace
    ):
        """Test upsert inserts when no conflict."""
        now = datetime.now(timezone.utc) + timedelta(hours=1)  # Different time

        values_dict = {
            'time': now,
            'card_id': test_card.id,
            'marketplace_id': test_marketplace.id,
            'condition': CardCondition.NEAR_MINT.value,
            'is_foil': False,
            'language': CardLanguage.ENGLISH.value,
            'price': Decimal("11.99"),
            'currency': "USD",
        }

        stmt = pg_insert(PriceSnapshot).values(**values_dict)
        stmt = stmt.on_conflict_do_update(
            index_elements=['time', 'card_id', 'marketplace_id', 'condition', 'is_foil', 'language'],
            set_={'price': stmt.excluded.price}
        )

        await db_session.execute(stmt)
        await db_session.flush()

        # Verify insert
        result = await db_session.execute(
            select(PriceSnapshot).where(
                and_(
                    PriceSnapshot.card_id == test_card.id,
                    PriceSnapshot.time == now,
                )
            )
        )
        snapshot = result.scalar_one_or_none()
        assert snapshot is not None
        assert float(snapshot.price) == 11.99

    async def test_upsert_update_existing(
        self, db_session: AsyncSession, test_card: Card, test_marketplace: Marketplace
    ):
        """Test upsert updates when there's a conflict."""
        now = datetime.now(timezone.utc) + timedelta(hours=2)

        # First insert
        initial_values = {
            'time': now,
            'card_id': test_card.id,
            'marketplace_id': test_marketplace.id,
            'condition': CardCondition.NEAR_MINT.value,
            'is_foil': False,
            'language': CardLanguage.ENGLISH.value,
            'price': Decimal("10.00"),
            'currency': "USD",
        }

        stmt1 = pg_insert(PriceSnapshot).values(**initial_values)
        stmt1 = stmt1.on_conflict_do_update(
            index_elements=['time', 'card_id', 'marketplace_id', 'condition', 'is_foil', 'language'],
            set_={'price': stmt1.excluded.price}
        )
        await db_session.execute(stmt1)
        await db_session.flush()

        # Second upsert with updated price
        updated_values = {
            'time': now,
            'card_id': test_card.id,
            'marketplace_id': test_marketplace.id,
            'condition': CardCondition.NEAR_MINT.value,
            'is_foil': False,
            'language': CardLanguage.ENGLISH.value,
            'price': Decimal("12.50"),
            'currency': "USD",
        }

        stmt2 = pg_insert(PriceSnapshot).values(**updated_values)
        stmt2 = stmt2.on_conflict_do_update(
            index_elements=['time', 'card_id', 'marketplace_id', 'condition', 'is_foil', 'language'],
            set_={'price': stmt2.excluded.price}
        )
        await db_session.execute(stmt2)
        await db_session.flush()

        # Verify only one row exists with updated price
        result = await db_session.execute(
            select(PriceSnapshot).where(
                and_(
                    PriceSnapshot.card_id == test_card.id,
                    PriceSnapshot.time == now,
                    PriceSnapshot.condition == CardCondition.NEAR_MINT.value,
                    PriceSnapshot.is_foil == False,
                    PriceSnapshot.language == CardLanguage.ENGLISH.value,
                )
            )
        )
        snapshots = result.scalars().all()
        assert len(snapshots) == 1
        assert float(snapshots[0].price) == 12.50

    async def test_upsert_different_conditions_same_time(
        self, db_session: AsyncSession, test_card: Card, test_marketplace: Marketplace
    ):
        """Test that different conditions create separate rows even with upsert."""
        now = datetime.now(timezone.utc) + timedelta(hours=3)

        conditions = [CardCondition.NEAR_MINT, CardCondition.LIGHTLY_PLAYED]

        for condition in conditions:
            values = {
                'time': now,
                'card_id': test_card.id,
                'marketplace_id': test_marketplace.id,
                'condition': condition.value,
                'is_foil': False,
                'language': CardLanguage.ENGLISH.value,
                'price': Decimal("10.00"),
                'currency': "USD",
            }

            stmt = pg_insert(PriceSnapshot).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=['time', 'card_id', 'marketplace_id', 'condition', 'is_foil', 'language'],
                set_={'price': stmt.excluded.price}
            )
            await db_session.execute(stmt)

        await db_session.flush()

        # Verify two separate rows exist
        result = await db_session.execute(
            select(func.count(PriceSnapshot.time)).where(
                and_(
                    PriceSnapshot.card_id == test_card.id,
                    PriceSnapshot.time == now,
                )
            )
        )
        count = result.scalar()
        assert count == 2


class TestCompositeKeyQueries:
    """Tests for querying price snapshots using composite keys."""

    async def test_query_by_full_key(
        self, db_session: AsyncSession, test_card: Card, test_marketplace: Marketplace
    ):
        """Test querying by the full composite key."""
        now = datetime.now(timezone.utc) + timedelta(hours=4)

        snapshot = PriceSnapshot(
            time=now,
            card_id=test_card.id,
            marketplace_id=test_marketplace.id,
            condition=CardCondition.NEAR_MINT.value,
            is_foil=False,
            language=CardLanguage.ENGLISH.value,
            price=Decimal("9.99"),
            currency="USD",
        )
        db_session.add(snapshot)
        await db_session.flush()

        # Query by full composite key
        result = await db_session.execute(
            select(PriceSnapshot).where(
                and_(
                    PriceSnapshot.time == now,
                    PriceSnapshot.card_id == test_card.id,
                    PriceSnapshot.marketplace_id == test_marketplace.id,
                    PriceSnapshot.condition == CardCondition.NEAR_MINT.value,
                    PriceSnapshot.is_foil.is_(False),
                    PriceSnapshot.language == CardLanguage.ENGLISH.value,
                )
            )
        )
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert float(fetched.price) == 9.99

    async def test_query_by_partial_key(
        self, db_session: AsyncSession, test_card: Card, test_marketplace: Marketplace
    ):
        """Test querying by partial key (card_id, marketplace_id)."""
        now = datetime.now(timezone.utc) + timedelta(hours=5)

        # Create multiple snapshots for same card/marketplace
        for i in range(3):
            snapshot = PriceSnapshot(
                time=now + timedelta(minutes=i),
                card_id=test_card.id,
                marketplace_id=test_marketplace.id,
                condition=CardCondition.NEAR_MINT.value,
                is_foil=False,
                language=CardLanguage.ENGLISH.value,
                price=Decimal(f"{10.00 + i}"),
                currency="USD",
            )
            db_session.add(snapshot)

        await db_session.flush()

        # Query by partial key
        result = await db_session.execute(
            select(PriceSnapshot).where(
                and_(
                    PriceSnapshot.card_id == test_card.id,
                    PriceSnapshot.marketplace_id == test_marketplace.id,
                    PriceSnapshot.time >= now,
                )
            ).order_by(PriceSnapshot.time)
        )
        snapshots = result.scalars().all()
        assert len(snapshots) >= 3

    async def test_query_time_range(
        self, db_session: AsyncSession, test_card: Card, test_marketplace: Marketplace
    ):
        """Test querying snapshots within a time range."""
        base_time = datetime.now(timezone.utc) + timedelta(hours=6)

        # Create snapshots over time
        for i in range(5):
            snapshot = PriceSnapshot(
                time=base_time + timedelta(hours=i),
                card_id=test_card.id,
                marketplace_id=test_marketplace.id,
                condition=CardCondition.NEAR_MINT.value,
                is_foil=False,
                language=CardLanguage.ENGLISH.value,
                price=Decimal(f"{10.00 + i}"),
                currency="USD",
            )
            db_session.add(snapshot)

        await db_session.flush()

        # Query middle 3 hours
        result = await db_session.execute(
            select(PriceSnapshot).where(
                and_(
                    PriceSnapshot.card_id == test_card.id,
                    PriceSnapshot.time >= base_time + timedelta(hours=1),
                    PriceSnapshot.time < base_time + timedelta(hours=4),
                )
            ).order_by(PriceSnapshot.time)
        )
        snapshots = result.scalars().all()
        assert len(snapshots) == 3

    async def test_query_aggregate_by_condition(
        self, db_session: AsyncSession, test_card: Card, test_marketplace: Marketplace
    ):
        """Test aggregating prices by condition."""
        now = datetime.now(timezone.utc) + timedelta(hours=10)

        conditions_prices = [
            (CardCondition.MINT.value, Decimal("20.00")),
            (CardCondition.NEAR_MINT.value, Decimal("15.00")),
            (CardCondition.LIGHTLY_PLAYED.value, Decimal("12.00")),
            (CardCondition.MODERATELY_PLAYED.value, Decimal("9.00")),
        ]

        for condition, price in conditions_prices:
            snapshot = PriceSnapshot(
                time=now,
                card_id=test_card.id,
                marketplace_id=test_marketplace.id,
                condition=condition,
                is_foil=False,
                language=CardLanguage.ENGLISH.value,
                price=price,
                currency="USD",
            )
            db_session.add(snapshot)

        await db_session.flush()

        # Aggregate by condition
        result = await db_session.execute(
            select(
                PriceSnapshot.condition,
                func.avg(PriceSnapshot.price).label("avg_price")
            ).where(
                and_(
                    PriceSnapshot.card_id == test_card.id,
                    PriceSnapshot.time == now,
                )
            ).group_by(PriceSnapshot.condition)
        )

        condition_prices = {row.condition: float(row.avg_price) for row in result.all()}
        assert len(condition_prices) == 4
        assert condition_prices[CardCondition.MINT.value] == 20.00
        assert condition_prices[CardCondition.NEAR_MINT.value] == 15.00


class TestCompositeKeyConstraints:
    """Tests for composite key constraint behavior."""

    async def test_duplicate_key_raises_error(
        self, db_session: AsyncSession, test_card: Card, test_marketplace: Marketplace
    ):
        """Test that inserting duplicate composite key raises an error."""
        now = datetime.now(timezone.utc) + timedelta(hours=11)

        snapshot1 = PriceSnapshot(
            time=now,
            card_id=test_card.id,
            marketplace_id=test_marketplace.id,
            condition=CardCondition.NEAR_MINT.value,
            is_foil=False,
            language=CardLanguage.ENGLISH.value,
            price=Decimal("10.00"),
            currency="USD",
        )
        db_session.add(snapshot1)
        await db_session.flush()

        # Try to insert duplicate
        snapshot2 = PriceSnapshot(
            time=now,
            card_id=test_card.id,
            marketplace_id=test_marketplace.id,
            condition=CardCondition.NEAR_MINT.value,
            is_foil=False,
            language=CardLanguage.ENGLISH.value,
            price=Decimal("11.00"),
            currency="USD",
        )
        db_session.add(snapshot2)

        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            await db_session.flush()

        # Rollback to continue with other tests
        await db_session.rollback()

    async def test_different_time_same_other_keys_allowed(
        self, db_session: AsyncSession, test_card: Card, test_marketplace: Marketplace
    ):
        """Test that different times with same other keys are allowed."""
        base_time = datetime.now(timezone.utc) + timedelta(hours=12)

        for i in range(3):
            snapshot = PriceSnapshot(
                time=base_time + timedelta(minutes=i * 30),
                card_id=test_card.id,
                marketplace_id=test_marketplace.id,
                condition=CardCondition.NEAR_MINT.value,
                is_foil=False,
                language=CardLanguage.ENGLISH.value,
                price=Decimal(f"{10.00 + i}"),
                currency="USD",
            )
            db_session.add(snapshot)

        # Should not raise
        await db_session.flush()

        # Verify all three exist
        result = await db_session.execute(
            select(func.count(PriceSnapshot.time)).where(
                and_(
                    PriceSnapshot.card_id == test_card.id,
                    PriceSnapshot.time >= base_time,
                )
            )
        )
        count = result.scalar()
        assert count == 3


class TestHelperFunctions:
    """Tests for helper functions that work with composite keys."""

    async def test_get_latest_price_for_condition(
        self, db_session: AsyncSession, test_card: Card, test_marketplace: Marketplace
    ):
        """Test getting the latest price for a specific condition."""
        base_time = datetime.now(timezone.utc) + timedelta(hours=13)

        # Create price history
        for i in range(5):
            snapshot = PriceSnapshot(
                time=base_time + timedelta(hours=i),
                card_id=test_card.id,
                marketplace_id=test_marketplace.id,
                condition=CardCondition.NEAR_MINT.value,
                is_foil=False,
                language=CardLanguage.ENGLISH.value,
                price=Decimal(f"{10.00 + i}"),
                currency="USD",
            )
            db_session.add(snapshot)

        await db_session.flush()

        # Get latest price
        result = await db_session.execute(
            select(PriceSnapshot).where(
                and_(
                    PriceSnapshot.card_id == test_card.id,
                    PriceSnapshot.marketplace_id == test_marketplace.id,
                    PriceSnapshot.condition == CardCondition.NEAR_MINT.value,
                    PriceSnapshot.is_foil.is_(False),
                )
            ).order_by(PriceSnapshot.time.desc()).limit(1)
        )
        latest = result.scalar_one_or_none()
        assert latest is not None
        assert float(latest.price) == 14.00  # Last price (10 + 4)

    async def test_get_price_spread_across_conditions(
        self, db_session: AsyncSession, test_card: Card, test_marketplace: Marketplace
    ):
        """Test calculating price spread across conditions."""
        now = datetime.now(timezone.utc) + timedelta(hours=14)

        conditions_prices = [
            (CardCondition.MINT.value, Decimal("25.00")),
            (CardCondition.NEAR_MINT.value, Decimal("20.00")),
            (CardCondition.LIGHTLY_PLAYED.value, Decimal("15.00")),
            (CardCondition.MODERATELY_PLAYED.value, Decimal("10.00")),
            (CardCondition.HEAVILY_PLAYED.value, Decimal("5.00")),
        ]

        for condition, price in conditions_prices:
            snapshot = PriceSnapshot(
                time=now,
                card_id=test_card.id,
                marketplace_id=test_marketplace.id,
                condition=condition,
                is_foil=False,
                language=CardLanguage.ENGLISH.value,
                price=price,
                currency="USD",
            )
            db_session.add(snapshot)

        await db_session.flush()

        # Calculate spread
        result = await db_session.execute(
            select(
                func.min(PriceSnapshot.price).label("min_price"),
                func.max(PriceSnapshot.price).label("max_price"),
            ).where(
                and_(
                    PriceSnapshot.card_id == test_card.id,
                    PriceSnapshot.time == now,
                    PriceSnapshot.is_foil.is_(False),
                )
            )
        )
        row = result.one()
        assert float(row.min_price) == 5.00
        assert float(row.max_price) == 25.00

        spread_pct = ((float(row.max_price) - float(row.min_price)) / float(row.min_price)) * 100
        assert spread_pct == 400.0  # (25 - 5) / 5 * 100
