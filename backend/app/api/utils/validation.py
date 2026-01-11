"""
Input validation utilities for API routes.

Provides validation functions to protect against DoS attacks
via unbounded input sizes.
"""

from typing import List, TypeVar

from fastapi import HTTPException, status

from app.core.constants import MAX_IDS_PER_REQUEST

T = TypeVar("T")


def validate_id_list(ids: List[T], param_name: str = "ids") -> List[T]:
    """
    Validate that an ID list doesn't exceed the maximum allowed.

    This prevents DoS attacks where users could pass extremely large
    ID lists (100,000+ IDs) causing database performance issues.

    Args:
        ids: List of IDs to validate
        param_name: Name of the parameter for error messages

    Returns:
        The validated list (unchanged if valid)

    Raises:
        HTTPException: 400 Bad Request if too many IDs provided
    """
    if len(ids) > MAX_IDS_PER_REQUEST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many {param_name}. Maximum {MAX_IDS_PER_REQUEST} allowed.",
        )
    return ids
