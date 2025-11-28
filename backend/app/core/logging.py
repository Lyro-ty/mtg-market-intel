"""
Logging configuration for the application.
"""
import logging
import sys

import structlog

from app.core.config import settings


def setup_logging():
    """
    Configure structured logging for the application.
    """
    # Set log level based on debug mode
    log_level = logging.DEBUG if settings.api_debug else logging.INFO
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            # Use console renderer in debug mode, JSON otherwise
            structlog.dev.ConsoleRenderer()
            if settings.api_debug
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    
    # Reduce noise from libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.api_debug else logging.WARNING
    )


def get_logger(name: str | None = None):
    """
    Get a structured logger.
    
    Args:
        name: Optional logger name.
        
    Returns:
        Structured logger instance.
    """
    return structlog.get_logger(name)
