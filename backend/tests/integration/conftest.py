"""
Fixtures for integration tests that require PostgreSQL.

These fixtures provide a real PostgreSQL/TimescaleDB connection for testing
database-specific features that don't work with SQLite (composite keys,
TimescaleDB hypertables, etc.).

Usage:
    Mark tests with @pytest.mark.integration and use pg_session fixture:

    @pytest.mark.integration
    async def test_something(pg_session):
        # Test with real PostgreSQL
        pass

Run with:
    INTEGRATION_DATABASE_URL="postgresql+asyncpg://..." pytest -m integration
"""
import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Integration tests require PostgreSQL
INTEGRATION_DB_URL = os.getenv(
    "INTEGRATION_DATABASE_URL",
    "postgresql+asyncpg://test_user:test_pass@localhost:5433/test_db"
)


@pytest.fixture(scope="session")
def integration_db_url():
    """Get integration test database URL."""
    return INTEGRATION_DB_URL


@pytest_asyncio.fixture(scope="function")
async def pg_engine(integration_db_url):
    """Create PostgreSQL engine for integration tests."""
    engine = create_async_engine(integration_db_url, echo=False)

    from app.db.base import Base
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def pg_session(pg_engine) -> AsyncSession:
    """Create PostgreSQL session for integration tests."""
    session_maker = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session
        await session.rollback()
