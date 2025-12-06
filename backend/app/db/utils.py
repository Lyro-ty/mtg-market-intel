"""
Database utility functions for safe operations.

Provides utilities for idempotent database operations, particularly
useful for Celery tasks that may be retried.
"""
from typing import Optional, TypeVar, Type
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

T = TypeVar('T', bound=DeclarativeBase)


async def get_or_create(
    db: AsyncSession,
    model: Type[T],
    defaults: Optional[dict] = None,
    **kwargs
) -> tuple[T, bool]:
    """
    Get an existing instance or create a new one (idempotent).
    
    This is useful for Celery tasks that may be retried, ensuring
    we don't create duplicate records.
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        defaults: Default values to use when creating
        **kwargs: Filter criteria to find existing instance
        
    Returns:
        Tuple of (instance, created) where created is True if new instance was created
        
    Example:
        marketplace, created = await get_or_create(
            db, Marketplace, slug="scryfall", defaults={"name": "Scryfall"}
        )
    """
    # Try to get existing instance
    query = select(model).filter_by(**kwargs)
    result = await db.execute(query)
    instance = result.scalar_one_or_none()
    
    if instance:
        return instance, False
    
    # Create new instance
    create_kwargs = {**kwargs}
    if defaults:
        create_kwargs.update(defaults)
    
    instance = model(**create_kwargs)
    db.add(instance)
    await db.flush()  # Flush to get ID, but don't commit yet
    
    return instance, True


async def upsert_metrics(
    db: AsyncSession,
    card_id: int,
    target_date,
    metrics_data: dict,
) -> bool:
    """
    Upsert daily metrics for a card (idempotent).
    
    Uses the unique constraint on (card_id, date) to ensure
    only one metrics record exists per card per day.
    
    Args:
        db: Database session
        card_id: Card ID
        target_date: Date for metrics
        metrics_data: Dictionary of metric values
        
    Returns:
        True if new record was created, False if existing was updated
    """
    from app.models import MetricsCardsDaily
    
    # Try to get existing metrics
    query = select(MetricsCardsDaily).where(
        MetricsCardsDaily.card_id == card_id,
        MetricsCardsDaily.date == target_date,
    )
    result = await db.execute(query)
    existing = result.scalar_one_or_none()
    
    if existing:
        # Update existing metrics
        for key, value in metrics_data.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
        return False
    else:
        # Create new metrics
        new_metrics = MetricsCardsDaily(
            card_id=card_id,
            date=target_date,
            **metrics_data
        )
        db.add(new_metrics)
        return True

