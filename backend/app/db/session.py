"""
Database session management.

Provides async session factory and dependency injection for FastAPI.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

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
    pool_timeout=20,  # Wait up to 20 seconds for a connection from the pool (reduced from 30)
    connect_args={
        "server_settings": {
            "statement_timeout": "25000",  # 25 second query timeout (in milliseconds)
            "application_name": "mtg_market_intel_api",
        },
        "command_timeout": 25,  # asyncpg command timeout (in seconds)
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
    
    Ensures proper connection cleanup and error handling.
    
    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    session = None
    try:
        async with async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                # Log the error for debugging
                import structlog
                logger = structlog.get_logger()
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
                    "Database session error",
                    error=str(e),
                    error_type=type(e).__name__,
                    **pool_info
                )
                raise
            finally:
                # Explicitly close the session to release the connection
                await session.close()
    except Exception as e:
        # Ensure session is closed even if there's an error creating it
        if session:
            try:
                await session.close()
            except Exception:
                pass
        raise

