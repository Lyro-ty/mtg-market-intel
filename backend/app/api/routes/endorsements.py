"""
User Endorsements API endpoints.

Community-based endorsement system for users.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User, UserEndorsement
from app.api.routes.connections import check_connection
from app.schemas.connection import (
    EndorsementCreate,
    EndorsementResponse,
    EndorsementSummary,
    ConnectionRequestorInfo,
)

router = APIRouter(prefix="/endorsements", tags=["endorsements"])
logger = structlog.get_logger(__name__)

# Valid endorsement types
ENDORSEMENT_TYPES = ["trustworthy", "knowledgeable", "responsive", "fair_trader"]


@router.post("/users/{user_id}", response_model=EndorsementResponse, status_code=201)
async def endorse_user(
    user_id: int,
    endorsement: EndorsementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Endorse another user.

    You must be connected to endorse someone.
    Valid types: trustworthy, knowledgeable, responsive, fair_trader
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot endorse yourself")

    if endorsement.endorsement_type not in ENDORSEMENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid endorsement type. Must be one of: {', '.join(ENDORSEMENT_TYPES)}"
        )

    # Check user exists
    target_user = await db.get(User, user_id)
    if not target_user or not target_user.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    # Must have connection to endorse
    connected = await check_connection(db, current_user.id, user_id)
    if not connected:
        raise HTTPException(status_code=403, detail="Must be connected to endorse")

    # Check if already endorsed for this type
    existing = await db.execute(
        select(UserEndorsement).where(
            UserEndorsement.endorser_id == current_user.id,
            UserEndorsement.endorsed_id == user_id,
            UserEndorsement.endorsement_type == endorsement.endorsement_type,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already endorsed for this type")

    endo = UserEndorsement(
        endorser_id=current_user.id,
        endorsed_id=user_id,
        endorsement_type=endorsement.endorsement_type,
        comment=endorsement.comment,
    )
    db.add(endo)
    await db.commit()
    await db.refresh(endo)

    logger.info(
        "User endorsed",
        endorser_id=current_user.id,
        endorsed_id=user_id,
        type=endorsement.endorsement_type,
    )

    return EndorsementResponse(
        id=endo.id,
        endorser_id=endo.endorser_id,
        endorsed_id=endo.endorsed_id,
        endorsement_type=endo.endorsement_type,
        comment=endo.comment,
        created_at=endo.created_at,
        endorser=ConnectionRequestorInfo(
            id=current_user.id,
            username=current_user.username,
            display_name=current_user.display_name,
            avatar_url=current_user.avatar_url,
            location=current_user.location,
        ),
    )


@router.get("/users/{user_id}/summary", response_model=EndorsementSummary)
async def get_user_endorsement_summary(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get endorsement summary for a user.

    Returns counts by type.
    """
    result = await db.execute(
        select(
            UserEndorsement.endorsement_type,
            func.count().label("count")
        )
        .where(UserEndorsement.endorsed_id == user_id)
        .group_by(UserEndorsement.endorsement_type)
    )
    rows = result.all()

    summary = {row[0]: row[1] for row in rows}
    total = sum(summary.values())

    return EndorsementSummary(
        trustworthy=summary.get("trustworthy", 0),
        knowledgeable=summary.get("knowledgeable", 0),
        responsive=summary.get("responsive", 0),
        fair_trader=summary.get("fair_trader", 0),
        total=total,
    )


@router.get("/users/{user_id}", response_model=list[EndorsementResponse])
async def get_user_endorsements(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all endorsements for a user.
    """
    result = await db.execute(
        select(UserEndorsement)
        .where(UserEndorsement.endorsed_id == user_id)
        .options(selectinload(UserEndorsement.endorser))
        .order_by(UserEndorsement.created_at.desc())
    )
    endorsements = result.scalars().all()

    return [
        EndorsementResponse(
            id=e.id,
            endorser_id=e.endorser_id,
            endorsed_id=e.endorsed_id,
            endorsement_type=e.endorsement_type,
            comment=e.comment,
            created_at=e.created_at,
            endorser=ConnectionRequestorInfo(
                id=e.endorser.id,
                username=e.endorser.username,
                display_name=e.endorser.display_name,
                avatar_url=e.endorser.avatar_url,
                location=e.endorser.location,
            ) if e.endorser else None,
        )
        for e in endorsements
    ]


@router.delete("/users/{user_id}/{endorsement_type}")
async def remove_endorsement(
    user_id: int,
    endorsement_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Remove an endorsement you gave.
    """
    result = await db.execute(
        select(UserEndorsement).where(
            UserEndorsement.endorser_id == current_user.id,
            UserEndorsement.endorsed_id == user_id,
            UserEndorsement.endorsement_type == endorsement_type,
        )
    )
    endorsement = result.scalar_one_or_none()

    if not endorsement:
        raise HTTPException(status_code=404, detail="Endorsement not found")

    await db.delete(endorsement)
    await db.commit()

    logger.info(
        "Endorsement removed",
        endorser_id=current_user.id,
        endorsed_id=user_id,
        type=endorsement_type,
    )

    return {"status": "removed", "message": "Endorsement removed"}


@router.get("/my-endorsements")
async def get_my_endorsements(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get endorsements I've given to others.
    """
    result = await db.execute(
        select(UserEndorsement)
        .where(UserEndorsement.endorser_id == current_user.id)
        .options(selectinload(UserEndorsement.endorsed))
        .order_by(UserEndorsement.created_at.desc())
    )
    endorsements = result.scalars().all()

    return [
        {
            "id": e.id,
            "endorsed_user": {
                "id": e.endorsed.id,
                "username": e.endorsed.username,
                "display_name": e.endorsed.display_name,
                "avatar_url": e.endorsed.avatar_url,
            } if e.endorsed else None,
            "endorsement_type": e.endorsement_type,
            "comment": e.comment,
            "created_at": e.created_at,
        }
        for e in endorsements
    ]
