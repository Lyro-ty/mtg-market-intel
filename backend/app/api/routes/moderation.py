"""
User Moderation API endpoints.

Handles blocking and reporting users.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User, BlockedUser, UserReport
from app.schemas.connection import BlockUserCreate, ReportUserCreate, BlockedUserResponse

router = APIRouter(prefix="/moderation", tags=["moderation"])
logger = structlog.get_logger(__name__)


@router.post("/users/{user_id}/block", status_code=201)
async def block_user(
    user_id: int,
    block_data: BlockUserCreate = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Block a user from messaging and connecting.

    Blocked users cannot send you messages or connection requests.
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot block yourself")

    # Check if already blocked
    existing = await db.execute(
        select(BlockedUser).where(
            BlockedUser.blocker_id == current_user.id,
            BlockedUser.blocked_id == user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already blocked")

    block = BlockedUser(
        blocker_id=current_user.id,
        blocked_id=user_id,
        reason=block_data.reason if block_data else None,
    )
    db.add(block)
    await db.commit()

    logger.info(
        "User blocked",
        blocker_id=current_user.id,
        blocked_id=user_id,
    )

    return {"status": "blocked", "message": "User blocked successfully"}


@router.delete("/users/{user_id}/block")
async def unblock_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Unblock a previously blocked user.
    """
    result = await db.execute(
        select(BlockedUser).where(
            BlockedUser.blocker_id == current_user.id,
            BlockedUser.blocked_id == user_id,
        )
    )
    block = result.scalar_one_or_none()

    if not block:
        raise HTTPException(status_code=404, detail="User not blocked")

    await db.delete(block)
    await db.commit()

    logger.info(
        "User unblocked",
        blocker_id=current_user.id,
        unblocked_id=user_id,
    )

    return {"status": "unblocked", "message": "User unblocked"}


@router.get("/blocked", response_model=list[BlockedUserResponse])
async def get_blocked_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get list of users you have blocked.
    """
    result = await db.execute(
        select(BlockedUser, User)
        .join(User, BlockedUser.blocked_id == User.id)
        .where(BlockedUser.blocker_id == current_user.id)
        .order_by(BlockedUser.created_at.desc())
    )
    rows = result.all()

    return [
        BlockedUserResponse(
            id=block.id,
            blocked_id=user.id,
            blocked_username=user.username,
            reason=block.reason,
            created_at=block.created_at,
        )
        for block, user in rows
    ]


@router.post("/users/{user_id}/report", status_code=201)
async def report_user(
    user_id: int,
    report_data: ReportUserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Report a user for inappropriate behavior.

    Reports are reviewed by moderators.
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot report yourself")

    # Check target exists
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    report = UserReport(
        reporter_id=current_user.id,
        reported_id=user_id,
        reason=report_data.reason,
        details=report_data.details,
    )
    db.add(report)
    await db.commit()

    logger.warning(
        "User report submitted",
        reporter_id=current_user.id,
        reported_id=user_id,
        reason=report_data.reason,
    )

    return {"status": "reported", "message": "Report submitted for review"}


@router.get("/check/{user_id}")
async def check_block_status(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check if a user is blocked or has blocked you.
    """
    # Check if you blocked them
    result1 = await db.execute(
        select(BlockedUser).where(
            BlockedUser.blocker_id == current_user.id,
            BlockedUser.blocked_id == user_id,
        )
    )
    you_blocked_them = result1.scalar_one_or_none() is not None

    # Check if they blocked you
    result2 = await db.execute(
        select(BlockedUser).where(
            BlockedUser.blocker_id == user_id,
            BlockedUser.blocked_id == current_user.id,
        )
    )
    they_blocked_you = result2.scalar_one_or_none() is not None

    return {
        "you_blocked_them": you_blocked_them,
        "they_blocked_you": they_blocked_you,
        "any_block": you_blocked_them or they_blocked_you,
    }
