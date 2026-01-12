"""
Transaction management utilities.

Provides context managers for explicit transaction boundaries
to prevent partial commits on multi-step operations.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger()


@asynccontextmanager
async def atomic(db: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    """
    Execute operations atomically - all or nothing.

    Usage:
        async with atomic(db) as session:
            session.add(obj1)
            session.add(obj2)
            # Auto-commits on success, auto-rollbacks on exception

    Args:
        db: SQLAlchemy async session

    Yields:
        The same session for chaining

    Raises:
        Exception: Re-raises any exception after rollback
    """
    try:
        yield db
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error("Transaction rolled back", error=str(e), exc_info=True)
        raise


@asynccontextmanager
async def savepoint(db: AsyncSession, name: str = "sp") -> AsyncGenerator[AsyncSession, None]:
    """
    Create a savepoint for partial rollback capability.

    Usage:
        async with savepoint(db, "batch_insert") as session:
            # If this fails, only this block rolls back
            session.add(obj)

    Args:
        db: SQLAlchemy async session
        name: Savepoint name for debugging

    Yields:
        The same session
    """
    async with db.begin_nested():
        try:
            yield db
        except Exception as e:
            logger.warning(f"Savepoint {name} rolled back", error=str(e))
            raise
