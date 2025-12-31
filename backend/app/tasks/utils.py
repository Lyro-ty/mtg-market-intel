"""
Shared utilities for Celery tasks.

Provides common functions for database session management and async execution.
"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Coroutine, List, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
)

# async_sessionmaker was added in SQLAlchemy 1.4+
try:
    from sqlalchemy.ext.asyncio import async_sessionmaker
except ImportError:
    raise ImportError(
        "async_sessionmaker requires SQLAlchemy 1.4+. "
        "Please upgrade: pip install 'sqlalchemy[asyncio]>=1.4.0'"
    )

from app.core.config import settings

logger = None  # Lazy import to avoid circular dependencies


def get_logger():
    """Lazy import structlog to avoid circular dependencies."""
    global logger
    if logger is None:
        import structlog
        logger = structlog.get_logger()
    return logger


def create_task_session_maker():
    """
    Create a new async engine and session maker for the current event loop.
    
    This function is used by Celery tasks to create database sessions.
    Each task creates its own engine to avoid connection pool conflicts.
    
    Returns:
        Tuple of (async_sessionmaker, engine). The engine should be disposed
        after use to free resources.
    """
    engine = create_async_engine(
        settings.database_url_computed,
        echo=settings.api_debug,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args={
            "server_settings": {
                "statement_timeout": "60000",  # 60 second query timeout for tasks
                "idle_in_transaction_session_timeout": "300000",  # 5 min - auto-terminate idle transactions
                "application_name": "mtg_market_intel_worker",
            },
            "command_timeout": 60,  # asyncpg command timeout (in seconds)
        },
    )
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    ), engine


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """
    Run async function in sync context (for Celery tasks).

    Uses asyncio.run() which properly:
    - Creates a new event loop
    - Runs the coroutine to completion
    - Closes the loop and cleans up async generators
    - Handles threadpool executor shutdown

    Args:
        coro: Async coroutine to execute.

    Returns:
        Result of the coroutine execution.
    """
    return asyncio.run(coro)


# =============================================================================
# Two-Phase Transaction Pattern Utilities
# =============================================================================
# These utilities help avoid "idle in transaction" issues by separating
# data collection (external API calls) from database writes.


@dataclass
class CollectedPriceData:
    """
    Holds price data collected from external APIs for later batch writing.

    This dataclass is used in the two-phase pattern:
    1. Collect prices from APIs (no DB transaction)
    2. Write collected data in batched transactions
    """
    card_id: int
    marketplace_id: int
    price: Decimal
    currency: str = "USD"
    time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    condition: str = "near_mint"
    is_foil: bool = False
    language: str = "en"
    price_low: Optional[Decimal] = None
    price_mid: Optional[Decimal] = None
    price_high: Optional[Decimal] = None
    price_market: Optional[Decimal] = None
    num_listings: Optional[int] = None
    total_quantity: Optional[int] = None
    source: str = "api"


@dataclass
class CollectedBuylistData:
    """Holds buylist data collected from external APIs for batch writing."""
    card_id: int
    vendor_id: int
    price: Decimal
    currency: str = "USD"
    time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    condition: str = "near_mint"
    is_foil: bool = False
    quantity_buying: Optional[int] = None
    credit_price: Optional[Decimal] = None


@asynccontextmanager
async def short_transaction(session_maker):
    """
    Context manager for short-lived database transactions.

    Use this for quick read or write operations that should not
    hold the connection during external API calls.

    Example:
        async with short_transaction(session_maker) as db:
            result = await db.execute(select(Card).limit(10))
            cards = list(result.scalars().all())
        # Transaction is committed and connection released here
    """
    async with session_maker() as db:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def write_price_snapshots_batch(
    session_maker,
    collected_prices: List[CollectedPriceData],
    batch_size: int = 100,
) -> dict:
    """
    Write collected price data to database in short batched transactions.

    Each batch is committed separately, so partial success is possible.
    This is acceptable for price data where we'd rather have some data
    than none due to a single failure.

    Args:
        session_maker: Async session maker from create_task_session_maker()
        collected_prices: List of CollectedPriceData to write
        batch_size: Number of records per transaction (default 100)

    Returns:
        dict with 'written' and 'errors' counts
    """
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert
    from app.models.price import PriceSnapshot

    log = get_logger()
    stats = {"written": 0, "errors": 0, "batches": 0}

    for i in range(0, len(collected_prices), batch_size):
        batch = collected_prices[i:i + batch_size]

        async with session_maker() as db:
            try:
                for price_data in batch:
                    # Use upsert to handle duplicates gracefully
                    stmt = insert(PriceSnapshot).values(
                        time=price_data.time,
                        card_id=price_data.card_id,
                        marketplace_id=price_data.marketplace_id,
                        condition=price_data.condition,
                        is_foil=price_data.is_foil,
                        language=price_data.language,
                        price=price_data.price,
                        price_low=price_data.price_low,
                        price_mid=price_data.price_mid,
                        price_high=price_data.price_high,
                        price_market=price_data.price_market,
                        currency=price_data.currency,
                        num_listings=price_data.num_listings,
                        total_quantity=price_data.total_quantity,
                        source=price_data.source,
                    ).on_conflict_do_update(
                        index_elements=['time', 'card_id', 'marketplace_id', 'condition', 'is_foil', 'language'],
                        set_={
                            'price': price_data.price,
                            'price_low': price_data.price_low,
                            'price_mid': price_data.price_mid,
                            'price_high': price_data.price_high,
                            'price_market': price_data.price_market,
                            'num_listings': price_data.num_listings,
                            'total_quantity': price_data.total_quantity,
                        }
                    )
                    await db.execute(stmt)
                    stats["written"] += 1

                await db.commit()
                stats["batches"] += 1

            except Exception as e:
                await db.rollback()
                stats["errors"] += len(batch)
                log.warning(
                    "Batch write failed",
                    batch_start=i,
                    batch_size=len(batch),
                    error=str(e),
                )

    return stats


async def write_buylist_snapshots_batch(
    session_maker,
    collected_buylists: List[CollectedBuylistData],
    batch_size: int = 100,
) -> dict:
    """
    Write collected buylist data to database in short batched transactions.

    Args:
        session_maker: Async session maker from create_task_session_maker()
        collected_buylists: List of CollectedBuylistData to write
        batch_size: Number of records per transaction (default 100)

    Returns:
        dict with 'written' and 'errors' counts
    """
    from sqlalchemy.dialects.postgresql import insert
    from app.models.buylist import BuylistSnapshot

    log = get_logger()
    stats = {"written": 0, "errors": 0, "batches": 0}

    for i in range(0, len(collected_buylists), batch_size):
        batch = collected_buylists[i:i + batch_size]

        async with session_maker() as db:
            try:
                for buylist_data in batch:
                    stmt = insert(BuylistSnapshot).values(
                        time=buylist_data.time,
                        card_id=buylist_data.card_id,
                        vendor_id=buylist_data.vendor_id,
                        condition=buylist_data.condition,
                        is_foil=buylist_data.is_foil,
                        price=buylist_data.price,
                        currency=buylist_data.currency,
                        quantity_buying=buylist_data.quantity_buying,
                        credit_price=buylist_data.credit_price,
                    ).on_conflict_do_update(
                        index_elements=['time', 'card_id', 'vendor_id', 'condition', 'is_foil'],
                        set_={
                            'price': buylist_data.price,
                            'quantity_buying': buylist_data.quantity_buying,
                            'credit_price': buylist_data.credit_price,
                        }
                    )
                    await db.execute(stmt)
                    stats["written"] += 1

                await db.commit()
                stats["batches"] += 1

            except Exception as e:
                await db.rollback()
                stats["errors"] += len(batch)
                log.warning(
                    "Buylist batch write failed",
                    batch_start=i,
                    batch_size=len(batch),
                    error=str(e),
                )

    return stats


def log_pool_status(engine, context: str = ""):
    """
    Log connection pool status for debugging.

    Useful for monitoring connection pool health during long-running tasks.
    """
    log = get_logger()
    try:
        pool = engine.pool
        log.info(
            f"Connection pool status{' - ' + context if context else ''}",
            pool_size=pool.size(),
            checked_in=pool.checkedin(),
            checked_out=pool.checkedout(),
            overflow=pool.overflow(),
        )
    except Exception as e:
        log.debug("Could not get pool status", error=str(e))

