"""
Database connection utilities for MCP server.

Provides async database access independent of the main app.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from mcp_server.config import config


# Create engine lazily to avoid connection at import time
_engine = None
_session_maker = None


def get_engine():
    """Get or create the async engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            config.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_maker():
    """Get or create the session maker."""
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_maker


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def execute_query(query: str, params: dict | None = None) -> list[dict[str, Any]]:
    """Execute a read-only SQL query and return results as dicts."""
    # Safety: only allow SELECT queries
    query_upper = query.strip().upper()
    if not query_upper.startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed")

    async with get_db_session() as session:
        result = await session.execute(text(query), params or {})
        rows = result.fetchall()
        columns = result.keys()
        return [dict(zip(columns, row)) for row in rows]


async def get_table_names() -> list[str]:
    """Get all table names in the database."""
    query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    """
    rows = await execute_query(query)
    return [row["table_name"] for row in rows]


async def get_table_columns(table_name: str) -> list[dict[str, Any]]:
    """Get column information for a table."""
    query = """
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default,
            character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :table_name
        ORDER BY ordinal_position
    """
    return await execute_query(query, {"table_name": table_name})


async def get_row_count(table_name: str) -> int:
    """Get approximate row count for a table."""
    # Use reltuples for speed on large tables
    query = """
        SELECT reltuples::bigint as count
        FROM pg_class
        WHERE relname = :table_name
    """
    rows = await execute_query(query, {"table_name": table_name})
    if rows:
        return rows[0]["count"]
    return 0


async def check_connection() -> dict[str, Any]:
    """Check database connectivity and return status."""
    import time
    start = time.time()
    try:
        async with get_db_session() as session:
            result = await session.execute(text("SELECT 1"))
            result.fetchone()
        latency_ms = (time.time() - start) * 1000
        return {
            "connected": True,
            "latency_ms": round(latency_ms, 2),
            "database_url": config.database_url.split("@")[-1],  # Hide credentials
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
        }
