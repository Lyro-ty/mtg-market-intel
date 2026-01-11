"""
Database session management.

Provides async session factory and dependency injection for FastAPI.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
)

# async_sessionmaker was added in SQLAlchemy 1.4+
# Check if it's available, provide helpful error if not
try:
    from sqlalchemy.ext.asyncio import async_sessionmaker
except ImportError as e:
    raise ImportError(
        f"async_sessionmaker is not available in your SQLAlchemy installation. "
        f"This requires SQLAlchemy 1.4+ (you have an older version).\n"
        f"Error: {e}\n"
        f"Please install the correct version: pip install 'sqlalchemy[asyncio]>=2.0.0'\n"
        f"Or run migrations inside Docker: docker-compose exec backend alembic upgrade head"
    ) from e

from app.core.config import settings


# Create async engine with improved connection pool settings
# Increased pool size to handle concurrent requests better
engine = create_async_engine(
    settings.database_url_computed,
    echo=settings.api_debug,
    pool_pre_ping=True,  # Verify connections before using them
    pool_size=20,  # Increased from 10 to handle more concurrent requests
    max_overflow=30,  # Increased from 20 to allow more overflow connections
    pool_recycle=1800,  # Recycle connections after 30 minutes (reduced from 1 hour)
    pool_timeout=settings.db_pool_timeout,  # Wait for a connection from the pool
    connect_args={
        "server_settings": {
            "statement_timeout": f"{settings.db_query_timeout * 1000}",  # Query timeout (in milliseconds)
            "idle_in_transaction_session_timeout": "300000",  # 5 min - auto-terminate idle transactions
            "application_name": "mtg_market_intel_api",
        },
        "command_timeout": settings.db_query_timeout,  # asyncpg command timeout (in seconds)
    },
)
# Note: statement_timeout is set via connect_args.server_settings above
# No need for a connection event listener since asyncpg doesn't support sync cursor context managers

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides an async database session.

    IMPORTANT: This does NOT auto-commit. Routes must explicitly commit.
    On exception, the session is rolled back.

    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
            await db.commit()  # Explicit commit required for writes
    """
    import structlog
    logger = structlog.get_logger()

    async with async_session_maker() as session:
        try:
            yield session
            # NOTE: No auto-commit - routes must explicitly call await db.commit()
        except Exception as e:
            await session.rollback()
            try:
                pool_info = {
                    "pool_size": engine.pool.size(),
                    "pool_checked_in": engine.pool.checkedin(),
                    "pool_checked_out": engine.pool.checkedout(),
                    "pool_overflow": engine.pool.overflow(),
                }
            except Exception:
                pool_info = {"pool_info": "unavailable"}
            logger.error(
                "Database session error - rolled back",
                error=str(e),
                error_type=type(e).__name__,
                **pool_info
            )
            raise

