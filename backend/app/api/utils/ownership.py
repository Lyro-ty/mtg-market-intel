"""
Ownership verification utilities for protecting against IDOR vulnerabilities.

IDOR (Insecure Direct Object Reference) vulnerabilities allow users to access
other users' data by guessing/incrementing IDs. This module provides utilities
to verify that the current user owns the resource they're trying to access.
"""
from typing import TypeVar, Type, Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


T = TypeVar("T")


async def verify_ownership(
    db: AsyncSession,
    model_class: Type[T],
    item_id: int,
    user: User,
    user_id_field: str = "user_id",
) -> T:
    """
    Fetch an item and verify the current user owns it.

    This function returns a 404 for both "not found" and "not owned" cases
    to prevent leaking information about the existence of other users' items.

    Args:
        db: Database session
        model_class: SQLAlchemy model class to query
        item_id: ID of the item to fetch
        user: Current authenticated user
        user_id_field: Name of the field containing the owner's user ID
                       (defaults to "user_id")

    Returns:
        The item if found and owned by the user

    Raises:
        HTTPException 404: If item not found or not owned by user
    """
    item = await db.get(model_class, item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    if getattr(item, user_id_field, None) != user.id:
        # Return 404 to not leak existence of other users' items
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    return item


async def verify_ownership_optional(
    db: AsyncSession,
    model_class: Type[T],
    item_id: int,
    user: User,
    user_id_field: str = "user_id",
) -> Optional[T]:
    """
    Fetch an item and verify the current user owns it, returning None if not found.

    Similar to verify_ownership but returns None instead of raising an exception
    when the item is not found or not owned.

    Args:
        db: Database session
        model_class: SQLAlchemy model class to query
        item_id: ID of the item to fetch
        user: Current authenticated user
        user_id_field: Name of the field containing the owner's user ID

    Returns:
        The item if found and owned by the user, None otherwise
    """
    item = await db.get(model_class, item_id)

    if not item:
        return None

    if getattr(item, user_id_field, None) != user.id:
        return None

    return item


def check_ownership(
    item: Any,
    user: User,
    user_id_field: str = "user_id",
) -> bool:
    """
    Check if a user owns an item (without fetching from database).

    Useful when you already have the item loaded and just need to verify ownership.

    Args:
        item: The item to check ownership of
        user: Current authenticated user
        user_id_field: Name of the field containing the owner's user ID

    Returns:
        True if user owns the item, False otherwise
    """
    return getattr(item, user_id_field, None) == user.id


def require_ownership(
    item: Any,
    user: User,
    user_id_field: str = "user_id",
    detail: str = "Item not found",
) -> None:
    """
    Verify ownership of an item that's already loaded.

    Raises 404 if the user doesn't own the item.

    Args:
        item: The item to check ownership of
        user: Current authenticated user
        user_id_field: Name of the field containing the owner's user ID
        detail: Error message to return (defaults to "Item not found")

    Raises:
        HTTPException 404: If user doesn't own the item
    """
    if getattr(item, user_id_field, None) != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )
