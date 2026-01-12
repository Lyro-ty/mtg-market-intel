"""
Tests for transaction context managers.

Tests atomic() and savepoint() behavior for proper transaction boundaries.
"""
import pytest
from sqlalchemy import select

from app.db.transaction import atomic, savepoint
from app.models import Card


@pytest.mark.asyncio
async def test_atomic_commits_on_success(db_session):
    """Atomic context commits all changes on success."""
    async with atomic(db_session) as session:
        card = Card(
            scryfall_id="test-atomic-123",
            name="Test Atomic Card",
            set_code="TST",
            collector_number="001",
        )
        session.add(card)

    # Verify committed
    result = await db_session.execute(
        select(Card).where(Card.scryfall_id == "test-atomic-123")
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_atomic_rollbacks_on_failure(db_session):
    """Atomic context rolls back all changes on exception."""
    with pytest.raises(ValueError):
        async with atomic(db_session) as session:
            card = Card(
                scryfall_id="test-rollback-123",
                name="Test Rollback Card",
                set_code="TST",
                collector_number="002",
            )
            session.add(card)
            await session.flush()  # Write to DB
            raise ValueError("Simulated failure")

    # Verify rolled back
    result = await db_session.execute(
        select(Card).where(Card.scryfall_id == "test-rollback-123")
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_savepoint_partial_rollback(db_session):
    """Savepoint allows partial rollback within transaction."""
    # First card succeeds
    card1 = Card(
        scryfall_id="test-sp-success-123",
        name="Success Card",
        set_code="TST",
        collector_number="003",
    )
    db_session.add(card1)
    await db_session.flush()

    # Second card in savepoint fails
    try:
        async with savepoint(db_session, "failing_batch"):
            card2 = Card(
                scryfall_id="test-sp-fail-123",
                name="Fail Card",
                set_code="TST",
                collector_number="004",
            )
            db_session.add(card2)
            await db_session.flush()
            raise ValueError("Batch failed")
    except ValueError:
        pass  # Expected

    await db_session.commit()

    # First card committed, second rolled back
    result1 = await db_session.execute(
        select(Card).where(Card.scryfall_id == "test-sp-success-123")
    )
    assert result1.scalar_one_or_none() is not None

    result2 = await db_session.execute(
        select(Card).where(Card.scryfall_id == "test-sp-fail-123")
    )
    assert result2.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_savepoint_commits_on_success(db_session):
    """Savepoint commits changes when no exception occurs."""
    async with savepoint(db_session, "success_batch") as session:
        card = Card(
            scryfall_id="test-sp-commit-123",
            name="Savepoint Commit Card",
            set_code="TST",
            collector_number="005",
        )
        session.add(card)

    await db_session.commit()

    # Verify committed
    result = await db_session.execute(
        select(Card).where(Card.scryfall_id == "test-sp-commit-123")
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_nested_savepoints(db_session):
    """Nested savepoints roll back independently."""
    # Outer savepoint
    async with savepoint(db_session, "outer") as session:
        card1 = Card(
            scryfall_id="test-nested-outer-123",
            name="Outer Card",
            set_code="TST",
            collector_number="006",
        )
        session.add(card1)
        await session.flush()

        # Inner savepoint fails
        try:
            async with savepoint(db_session, "inner"):
                card2 = Card(
                    scryfall_id="test-nested-inner-123",
                    name="Inner Card",
                    set_code="TST",
                    collector_number="007",
                )
                db_session.add(card2)
                await db_session.flush()
                raise ValueError("Inner failure")
        except ValueError:
            pass  # Expected

    await db_session.commit()

    # Outer card committed, inner rolled back
    result1 = await db_session.execute(
        select(Card).where(Card.scryfall_id == "test-nested-outer-123")
    )
    assert result1.scalar_one_or_none() is not None

    result2 = await db_session.execute(
        select(Card).where(Card.scryfall_id == "test-nested-inner-123")
    )
    assert result2.scalar_one_or_none() is None
