"""
Format Specialties API endpoints.

Allows users to manage their MTG format specialties for discovery purposes.
Users can indicate which formats they specialize in (e.g., Commander, Modern, Standard).
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.models.social import UserFormatSpecialty
from app.schemas.format_specialty import (
    AddFormatRequest,
    FormatSpecialtiesResponse,
    ReplaceFormatsRequest,
)

router = APIRouter(prefix="/profile/me/formats", tags=["Format Specialties"])
logger = structlog.get_logger(__name__)

MAX_FORMATS = 10


@router.get("", response_model=FormatSpecialtiesResponse)
async def get_my_formats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's format specialties.

    Returns the list of MTG formats the user has indicated as specialties,
    ordered alphabetically.
    """
    result = await db.execute(
        select(UserFormatSpecialty.format)
        .where(UserFormatSpecialty.user_id == current_user.id)
        .order_by(UserFormatSpecialty.format)
    )
    formats = [row[0] for row in result.all()]

    return FormatSpecialtiesResponse(formats=formats, count=len(formats))


@router.post("", response_model=FormatSpecialtiesResponse)
async def add_format(
    request: AddFormatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Add a format specialty.

    Validates that:
    - The format is one of the allowed MTG formats
    - The user hasn't already added this format
    - The user hasn't reached the maximum limit (10 formats)

    Returns the updated list of format specialties.
    """
    # Check current count
    count_result = await db.scalar(
        select(func.count())
        .select_from(UserFormatSpecialty)
        .where(UserFormatSpecialty.user_id == current_user.id)
    )
    if count_result >= MAX_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_FORMATS} formats allowed",
        )

    # Check if already exists
    existing = await db.scalar(
        select(UserFormatSpecialty)
        .where(UserFormatSpecialty.user_id == current_user.id)
        .where(UserFormatSpecialty.format == request.format)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Format already added")

    # Add new format
    specialty = UserFormatSpecialty(user_id=current_user.id, format=request.format)
    db.add(specialty)
    await db.commit()

    logger.info(
        "Format specialty added",
        user_id=current_user.id,
        format=request.format,
    )

    # Return updated list
    result = await db.execute(
        select(UserFormatSpecialty.format)
        .where(UserFormatSpecialty.user_id == current_user.id)
        .order_by(UserFormatSpecialty.format)
    )
    formats = [row[0] for row in result.all()]

    return FormatSpecialtiesResponse(formats=formats, count=len(formats))


@router.delete("/{format_name}")
async def remove_format(
    format_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Remove a format specialty.

    Returns 404 if the format is not in the user's specialties.
    """
    result = await db.execute(
        delete(UserFormatSpecialty)
        .where(UserFormatSpecialty.user_id == current_user.id)
        .where(UserFormatSpecialty.format == format_name)
    )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Format not found")

    await db.commit()

    logger.info(
        "Format specialty removed",
        user_id=current_user.id,
        format=format_name,
    )

    return {"message": "Format removed"}


@router.put("", response_model=FormatSpecialtiesResponse)
async def replace_formats(
    request: ReplaceFormatsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Replace all format specialties.

    Deletes all existing format specialties and adds the new ones.
    Validates that the request contains valid formats and max 10 formats.

    Returns the updated list of format specialties.
    """
    # Delete all existing formats for this user
    await db.execute(
        delete(UserFormatSpecialty).where(
            UserFormatSpecialty.user_id == current_user.id
        )
    )

    # Add new formats (deduplicate by converting to set)
    unique_formats = list(set(request.formats))
    for fmt in unique_formats:
        specialty = UserFormatSpecialty(user_id=current_user.id, format=fmt)
        db.add(specialty)

    await db.commit()

    logger.info(
        "Format specialties replaced",
        user_id=current_user.id,
        formats=unique_formats,
        count=len(unique_formats),
    )

    # Return in alphabetical order
    sorted_formats = sorted(unique_formats)
    return FormatSpecialtiesResponse(formats=sorted_formats, count=len(sorted_formats))
