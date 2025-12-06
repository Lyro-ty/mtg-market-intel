"""
Shared error handling utilities for API routes.

Provides consistent error handling patterns for database operations,
timeouts, and connection pool issues.
"""
from typing import Any, Callable, TypeVar, Optional
import asyncio

import structlog
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError, TimeoutError as SQLTimeoutError

logger = structlog.get_logger()

T = TypeVar('T')


def is_database_connection_error(error: Exception) -> bool:
    """
    Check if an error is a database connection/pool issue.
    
    Args:
        error: Exception to check
        
    Returns:
        True if error is related to database connection/pool
    """
    error_str = str(error).lower()
    error_type = type(error).__name__
    
    # Check for connection pool errors
    if "QueuePool" in error_str or "connection pool" in error_str:
        return True
    
    # Check for timeout errors
    if "connection timed out" in error_str or "timeout" in error_str:
        return True
    
    # Check for specific SQLAlchemy errors
    if isinstance(error, (OperationalError, SQLTimeoutError)):
        return True
    
    # Check for asyncio timeout
    if isinstance(error, asyncio.TimeoutError):
        return True
    
    return False


async def handle_database_query(
    query_func: Callable[[], Any],
    default_value: Any,
    error_context: dict[str, Any],
    timeout: Optional[float] = None,
) -> Any:
    """
    Execute a database query with standardized error handling.
    
    Args:
        query_func: Async function that executes the query
        default_value: Value to return on connection/timeout errors
        error_context: Context dict for logging (e.g., {"endpoint": "market_index"})
        timeout: Optional timeout in seconds (uses asyncio.wait_for if provided)
        
    Returns:
        Query result or default_value on connection/timeout errors
        
    Raises:
        HTTPException: For non-connection errors (500 status)
    """
    try:
        if timeout:
            result = await asyncio.wait_for(query_func(), timeout=timeout)
        else:
            result = await query_func()
        return result
    except (asyncio.TimeoutError, OperationalError, SQLTimeoutError) as e:
        logger.error(
            "Database query timeout or pool exhaustion",
            error=str(e),
            error_type=type(e).__name__,
            **error_context
        )
        return default_value
    except Exception as e:
        if is_database_connection_error(e):
            logger.error(
                "Database connection error",
                error=str(e),
                error_type=type(e).__name__,
                **error_context
            )
            return default_value
        
        # For other errors, log and re-raise as HTTPException
        logger.error(
            "Unexpected error in database query",
            error=str(e),
            error_type=type(e).__name__,
            **error_context
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute query: {error_context.get('endpoint', 'unknown')}"
        )


def get_empty_market_index_response(range: str, currency: Optional[str] = None) -> dict[str, Any]:
    """Get empty market index response structure."""
    return {
        "range": range,
        "currency": currency or "ALL",
        "points": [],
        "isMockData": False,
    }


def get_empty_top_movers_response(window: str) -> dict[str, Any]:
    """Get empty top movers response structure."""
    return {
        "window": window,
        "gainers": [],
        "losers": [],
        "isMockData": False,
    }


def get_empty_volume_by_format_response(days: int) -> dict[str, Any]:
    """Get empty volume by format response structure."""
    return {
        "days": days,
        "formats": [],
        "isMockData": False,
    }


def get_empty_market_overview_response() -> dict[str, Any]:
    """Get empty market overview response structure."""
    return {
        "totalCardsTracked": 0,
        "totalListings": 0,
        "volume24hUsd": 0.0,
        "avgPriceChange24hPct": None,
        "activeFormatsTracked": 10,
    }

