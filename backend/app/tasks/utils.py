"""
Shared utilities for Celery tasks.

Provides common functions for database session management and async execution.
"""
import asyncio
from typing import Any, Callable, Coroutine

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
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
    
    Creates a new event loop, runs the coroutine, and cleans up.
    
    Args:
        coro: Async coroutine to execute.
        
    Returns:
        Result of the coroutine execution.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

