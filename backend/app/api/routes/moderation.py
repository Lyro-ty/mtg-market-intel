"""
User Moderation API endpoints.

Handles:
- User blocking and reporting (user-facing)
- Admin moderation queue
- Moderation actions (warn, restrict, suspend, ban)
- Appeals management
- Trade dispute resolution
- Moderator notes
- User-facing dispute filing
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import (
    Appeal,
    BlockedUser,
    ModerationAction,
    ModerationNote,
    TradeDispute,
    TradeProposal,
    User,
    UserReport,
)
from app.schemas.connection import BlockUserCreate, ReportUserCreate, BlockedUserResponse
from app.schemas.moderation_enhanced import (
    AddModNoteRequest,
    AppealResponse,
    FileDisputeRequest,
    ModNoteInfo,
    ModerationActionResponse,
    ModerationCaseDetail,
    ModerationQueueItem,
    ModerationQueueResponse,
    PreviousActionInfo,
    RecentTradeInfo,
    ReportInfo,
    ReportedMessageInfo,
    ResolveAppealRequest,
    ResolveDisputeRequest,
    TakeActionRequest,
    TradeDisputeResponse,
    TradeStatsSummary,
)

router = APIRouter(prefix="/moderation", tags=["moderation"])
admin_router = APIRouter(prefix="/admin/moderation", tags=["Admin Moderation"])
disputes_router = APIRouter(prefix="/disputes", tags=["Disputes"])
logger = structlog.get_logger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================


def require_moderator(user: User) -> None:
    """Raise 403 if user is not a moderator or admin."""
    if not (user.is_moderator or user.is_admin):
        raise HTTPException(
            status_code=403,
            detail="Moderator access required",
        )


def build_queue_item_from_report(
    report: UserReport, user: User, report_count: int = 1
) -> ModerationQueueItem:
    """Convert a UserReport to a ModerationQueueItem."""
    # Determine flag level based on number of reports
    if report_count >= 5:
        flag_level = "critical"
    elif report_count >= 3:
        flag_level = "high"
    elif report_count >= 2:
        flag_level = "medium"
    else:
        flag_level = "low"

    return ModerationQueueItem(
        id=report.id,
        target_user_id=report.reported_id,
        target_username=user.username,
        flag_level=flag_level,
        flag_type="report",
        flag_reason=report.reason,
        report_count=report_count,
        created_at=report.created_at,
    )


def build_queue_item_from_dispute(dispute: TradeDispute, user: User) -> ModerationQueueItem:
    """Convert a TradeDispute to a ModerationQueueItem."""
    return ModerationQueueItem(
        id=dispute.id,
        target_user_id=dispute.filed_by,
        target_username=user.username,
        flag_level="high",  # Disputes are typically high priority
        flag_type="dispute",
        flag_reason=dispute.dispute_type,
        report_count=0,
        created_at=dispute.created_at,
    )


def build_queue_item_from_appeal(
    appeal: Appeal, user: User, action: ModerationAction
) -> ModerationQueueItem:
    """Convert an Appeal to a ModerationQueueItem."""
    return ModerationQueueItem(
        id=appeal.id,
        target_user_id=appeal.user_id,
        target_username=user.username,
        flag_level="medium",
        flag_type="appeal",
        flag_reason=f"Appeal: {action.action_type}",
        report_count=0,
        created_at=appeal.created_at,
    )


def create_evidence_snapshot(trade: TradeProposal) -> dict[str, Any]:
    """Capture trade state for dispute evidence."""
    return {
        "trade_id": trade.id,
        "proposer_id": trade.proposer_id,
        "proposer_username": trade.proposer.username if trade.proposer else None,
        "recipient_id": trade.recipient_id,
        "recipient_username": trade.recipient.username if trade.recipient else None,
        "status": trade.status.value if hasattr(trade.status, "value") else str(trade.status),
        "message": trade.message,
        "created_at": trade.created_at.isoformat() if trade.created_at else None,
        "expires_at": trade.expires_at.isoformat() if trade.expires_at else None,
        "proposer_confirmed_at": (
            trade.proposer_confirmed_at.isoformat() if trade.proposer_confirmed_at else None
        ),
        "recipient_confirmed_at": (
            trade.recipient_confirmed_at.isoformat() if trade.recipient_confirmed_at else None
        ),
        "items": [
            {
                "card_id": item.card_id,
                "card_name": item.card.name if item.card else None,
                "side": item.side.value if hasattr(item.side, "value") else str(item.side),
                "quantity": item.quantity,
                "condition": item.condition,
                "price_at_proposal": float(item.price_at_proposal) if item.price_at_proposal else None,
            }
            for item in trade.items
        ],
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


async def build_case_detail(user_id: int, db: AsyncSession) -> ModerationCaseDetail:
    """Aggregate all case info for a user."""
    # Get target user
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Get reports against this user
    reports_result = await db.execute(
        select(UserReport, User)
        .join(User, UserReport.reporter_id == User.id)
        .where(UserReport.reported_id == user_id)
        .order_by(UserReport.created_at.desc())
        .limit(50)
    )
    reports_rows = reports_result.all()
    reports = [
        ReportInfo(
            id=r.id,
            reporter_id=r.reporter_id,
            reporter_username=u.username,
            reason=r.reason,
            details=r.details,
            created_at=r.created_at,
        )
        for r, u in reports_rows
    ]

    # Get previous moderation actions
    actions_result = await db.execute(
        select(ModerationAction, User)
        .outerjoin(User, ModerationAction.moderator_id == User.id)
        .where(ModerationAction.target_user_id == user_id)
        .order_by(ModerationAction.created_at.desc())
        .limit(20)
    )
    actions_rows = actions_result.all()
    previous_actions = [
        PreviousActionInfo(
            id=a.id,
            action_type=a.action_type,
            reason=a.reason,
            moderator_username=u.username if u else None,
            created_at=a.created_at,
            expires_at=a.expires_at,
        )
        for a, u in actions_rows
    ]

    # Get moderator notes
    notes_result = await db.execute(
        select(ModerationNote, User)
        .join(User, ModerationNote.moderator_id == User.id)
        .where(ModerationNote.target_user_id == user_id)
        .order_by(ModerationNote.created_at.desc())
        .limit(20)
    )
    notes_rows = notes_result.all()
    mod_notes = [
        ModNoteInfo(
            id=n.id,
            moderator_id=n.moderator_id,
            moderator_username=u.username,
            content=n.content,
            created_at=n.created_at,
        )
        for n, u in notes_rows
    ]

    # Get trade statistics
    trades_result = await db.execute(
        select(TradeProposal).where(
            or_(
                TradeProposal.proposer_id == user_id,
                TradeProposal.recipient_id == user_id,
            )
        )
    )
    all_trades = trades_result.scalars().all()

    total_trades = len(all_trades)
    completed_trades = sum(1 for t in all_trades if str(t.status) == "completed")
    cancelled_trades = sum(1 for t in all_trades if str(t.status) == "cancelled")

    # Count disputes involving this user
    disputes_result = await db.execute(
        select(func.count(TradeDispute.id)).where(
            or_(
                TradeDispute.filed_by == user_id,
                and_(
                    TradeDispute.trade_proposal_id.isnot(None),
                    TradeDispute.trade_proposal_id.in_(
                        select(TradeProposal.id).where(
                            or_(
                                TradeProposal.proposer_id == user_id,
                                TradeProposal.recipient_id == user_id,
                            )
                        )
                    ),
                ),
            )
        )
    )
    disputed_trades = disputes_result.scalar() or 0

    completion_rate = (completed_trades / total_trades * 100) if total_trades > 0 else 0.0

    trade_stats = TradeStatsSummary(
        total_trades=total_trades,
        completed_trades=completed_trades,
        cancelled_trades=cancelled_trades,
        disputed_trades=disputed_trades,
        completion_rate=completion_rate,
    )

    # Get recent trades
    recent_trades_result = await db.execute(
        select(TradeProposal, User)
        .outerjoin(
            User,
            and_(
                or_(
                    TradeProposal.proposer_id == User.id,
                    TradeProposal.recipient_id == User.id,
                ),
                User.id != user_id,
            ),
        )
        .where(
            or_(
                TradeProposal.proposer_id == user_id,
                TradeProposal.recipient_id == user_id,
            )
        )
        .order_by(TradeProposal.created_at.desc())
        .limit(10)
    )
    recent_trades_rows = recent_trades_result.all()
    recent_trades = [
        RecentTradeInfo(
            id=t.id,
            other_party_username=u.username if u else "Unknown",
            status=str(t.status.value) if hasattr(t.status, "value") else str(t.status),
            created_at=t.created_at,
            completed_at=t.completed_at,
        )
        for t, u in recent_trades_rows
    ]

    # Get reported messages (messages from this user that were reported)
    # For now, return empty list as there's no direct message flagging
    reported_messages: list[ReportedMessageInfo] = []

    return ModerationCaseDetail(
        id=user_id,
        target_user_id=user_id,
        target_user={
            "id": target.id,
            "username": target.username,
            "display_name": target.display_name,
            "email": target.email,
            "avatar_url": target.avatar_url,
            "created_at": target.created_at.isoformat() if target.created_at else None,
            "is_active": target.is_active,
            "is_verified": target.is_verified,
        },
        reports=reports,
        auto_flags=[],  # Auto-flags would come from automated detection systems
        previous_actions=previous_actions,
        mod_notes=mod_notes,
        trade_stats=trade_stats,
        recent_trades=recent_trades,
        reported_messages=reported_messages,
    )


# =============================================================================
# User-facing Moderation Endpoints (existing)
# =============================================================================


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


# =============================================================================
# Admin Moderation Queue (Task 6.1)
# =============================================================================


@admin_router.get("/queue", response_model=ModerationQueueResponse)
async def get_moderation_queue(
    status: Optional[str] = Query(None, description="Filter by status: pending, resolved"),
    priority: Optional[str] = Query(None, description="Filter by priority: low, medium, high, critical"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get pending moderation items.

    Aggregates reports, disputes, and appeals into a unified queue.
    Requires moderator or admin role.
    """
    require_moderator(current_user)

    queue_items: list[ModerationQueueItem] = []
    offset = (page - 1) * limit

    # Get pending reports grouped by reported user
    report_query = (
        select(
            UserReport.reported_id,
            func.min(UserReport.id).label("first_report_id"),
            func.min(UserReport.reason).label("reason"),
            func.min(UserReport.created_at).label("created_at"),
            func.count(UserReport.id).label("report_count"),
        )
        .where(UserReport.status == "pending")
        .group_by(UserReport.reported_id)
    )
    reports_result = await db.execute(report_query)
    reports_rows = reports_result.all()

    for row in reports_rows:
        user = await db.get(User, row.reported_id)
        if user:
            item = ModerationQueueItem(
                id=row.first_report_id,
                target_user_id=row.reported_id,
                target_username=user.username,
                flag_level="critical" if row.report_count >= 5 else "high" if row.report_count >= 3 else "medium" if row.report_count >= 2 else "low",
                flag_type="report",
                flag_reason=row.reason,
                report_count=row.report_count,
                created_at=row.created_at,
            )
            queue_items.append(item)

    # Get open disputes
    disputes_result = await db.execute(
        select(TradeDispute, User)
        .join(User, TradeDispute.filed_by == User.id)
        .where(TradeDispute.status.in_(["open", "evidence_requested"]))
        .order_by(TradeDispute.created_at.asc())
    )
    for dispute, user in disputes_result.all():
        item = build_queue_item_from_dispute(dispute, user)
        queue_items.append(item)

    # Get pending appeals
    appeals_result = await db.execute(
        select(Appeal, User, ModerationAction)
        .join(User, Appeal.user_id == User.id)
        .join(ModerationAction, Appeal.moderation_action_id == ModerationAction.id)
        .where(Appeal.status == "pending")
        .order_by(Appeal.created_at.asc())
    )
    for appeal, user, action in appeals_result.all():
        item = build_queue_item_from_appeal(appeal, user, action)
        queue_items.append(item)

    # Apply filters
    if status == "pending":
        pass  # Already filtering for pending items
    elif status == "resolved":
        queue_items = []  # Would need different queries for resolved items

    if priority:
        queue_items = [i for i in queue_items if i.flag_level == priority]

    # Calculate counts
    total = len(queue_items)
    pending_count = total
    high_priority_count = sum(1 for i in queue_items if i.flag_level in ("high", "critical"))

    # Sort by priority and date
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    queue_items.sort(key=lambda x: (priority_order.get(x.flag_level, 4), x.created_at))

    # Paginate
    paginated_items = queue_items[offset : offset + limit]

    return ModerationQueueResponse(
        items=paginated_items,
        total=total,
        pending_count=pending_count,
        high_priority_count=high_priority_count,
    )


# =============================================================================
# Case Detail and Action Endpoints (Task 6.2)
# =============================================================================


@admin_router.get("/users/{user_id}", response_model=ModerationCaseDetail)
async def get_case_detail(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed case information for a user.

    Returns reports, flags, previous actions, notes, and trade stats.
    Requires moderator or admin role.
    """
    require_moderator(current_user)
    return await build_case_detail(user_id, db)


@admin_router.post("/users/{user_id}/actions", response_model=ModerationActionResponse)
async def take_moderation_action(
    user_id: int,
    request: TakeActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Take a moderation action against a user.

    Actions: dismiss, warn, restrict, suspend, ban, escalate.
    Requires moderator or admin role.
    """
    require_moderator(current_user)

    # Validate action type
    valid_actions = ["dismiss", "warn", "restrict", "suspend", "ban", "escalate"]
    if request.action not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action. Must be one of: {', '.join(valid_actions)}",
        )

    # Check target exists
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Calculate expiration for temporary actions
    expires_at = None
    if request.duration_days and request.action in ("restrict", "suspend"):
        expires_at = datetime.now(timezone.utc) + timedelta(days=request.duration_days)

    # Create moderation action
    action = ModerationAction(
        moderator_id=current_user.id,
        target_user_id=user_id,
        action_type=request.action,
        reason=request.reason,
        duration_days=request.duration_days,
        expires_at=expires_at,
        related_report_id=request.related_report_id,
    )
    db.add(action)

    # Update user status based on action
    if request.action == "suspend":
        target.is_active = False
    elif request.action == "ban":
        target.is_active = False

    # Update related report status if provided
    if request.related_report_id:
        report = await db.get(UserReport, request.related_report_id)
        if report:
            report.status = "resolved"
            report.reviewed_at = datetime.now(timezone.utc)
            if request.action == "dismiss":
                report.status = "dismissed"

    await db.commit()
    await db.refresh(action)

    logger.info(
        "Moderation action taken",
        moderator_id=current_user.id,
        target_user_id=user_id,
        action=request.action,
        reason=request.reason,
    )

    return ModerationActionResponse(
        id=action.id,
        action_type=action.action_type,
        reason=action.reason,
        duration_days=action.duration_days,
        expires_at=action.expires_at,
        created_at=action.created_at,
    )


# =============================================================================
# Appeals Endpoints (Task 6.3)
# =============================================================================


@admin_router.get("/appeals", response_model=list[AppealResponse])
async def list_appeals(
    status: Optional[str] = Query(None, description="Filter by status: pending, upheld, reduced, overturned"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List appeals with optional filtering.

    Requires moderator or admin role.
    """
    require_moderator(current_user)

    offset = (page - 1) * limit
    query = (
        select(Appeal)
        .options(selectinload(Appeal.user), selectinload(Appeal.moderation_action))
        .order_by(Appeal.created_at.desc())
    )

    if status:
        query = query.where(Appeal.status == status)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    appeals = result.scalars().all()

    return [
        AppealResponse(
            id=appeal.id,
            user_id=appeal.user_id,
            username=appeal.user.username if appeal.user else "Unknown",
            moderation_action=ModerationActionResponse(
                id=appeal.moderation_action.id,
                action_type=appeal.moderation_action.action_type,
                reason=appeal.moderation_action.reason,
                duration_days=appeal.moderation_action.duration_days,
                expires_at=appeal.moderation_action.expires_at,
                created_at=appeal.moderation_action.created_at,
            ),
            appeal_text=appeal.appeal_text,
            evidence_urls=appeal.evidence_urls or [],
            status=appeal.status,
            resolution_notes=appeal.resolution_notes,
            created_at=appeal.created_at,
            resolved_at=appeal.resolved_at,
        )
        for appeal in appeals
    ]


@admin_router.get("/appeals/{appeal_id}", response_model=AppealResponse)
async def get_appeal_detail(
    appeal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information about an appeal.

    Requires moderator or admin role.
    """
    require_moderator(current_user)

    result = await db.execute(
        select(Appeal)
        .options(selectinload(Appeal.user), selectinload(Appeal.moderation_action))
        .where(Appeal.id == appeal_id)
    )
    appeal = result.scalar_one_or_none()

    if not appeal:
        raise HTTPException(status_code=404, detail="Appeal not found")

    return AppealResponse(
        id=appeal.id,
        user_id=appeal.user_id,
        username=appeal.user.username if appeal.user else "Unknown",
        moderation_action=ModerationActionResponse(
            id=appeal.moderation_action.id,
            action_type=appeal.moderation_action.action_type,
            reason=appeal.moderation_action.reason,
            duration_days=appeal.moderation_action.duration_days,
            expires_at=appeal.moderation_action.expires_at,
            created_at=appeal.moderation_action.created_at,
        ),
        appeal_text=appeal.appeal_text,
        evidence_urls=appeal.evidence_urls or [],
        status=appeal.status,
        resolution_notes=appeal.resolution_notes,
        created_at=appeal.created_at,
        resolved_at=appeal.resolved_at,
    )


@admin_router.post("/appeals/{appeal_id}/resolve", response_model=AppealResponse)
async def resolve_appeal(
    appeal_id: int,
    request: ResolveAppealRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Resolve an appeal.

    Resolutions: upheld, reduced, overturned.
    Requires moderator or admin role.
    """
    require_moderator(current_user)

    # Validate resolution
    valid_resolutions = ["upheld", "reduced", "overturned"]
    if request.resolution not in valid_resolutions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid resolution. Must be one of: {', '.join(valid_resolutions)}",
        )

    result = await db.execute(
        select(Appeal)
        .options(selectinload(Appeal.user), selectinload(Appeal.moderation_action))
        .where(Appeal.id == appeal_id)
    )
    appeal = result.scalar_one_or_none()

    if not appeal:
        raise HTTPException(status_code=404, detail="Appeal not found")

    if appeal.status != "pending":
        raise HTTPException(status_code=400, detail="Appeal already resolved")

    # Update appeal
    appeal.status = request.resolution
    appeal.resolution_notes = request.notes
    appeal.reviewed_by = current_user.id
    appeal.resolved_at = datetime.now(timezone.utc)

    # If overturned, reactivate user if they were suspended/banned
    if request.resolution == "overturned":
        target = await db.get(User, appeal.moderation_action.target_user_id)
        if target and not target.is_active:
            target.is_active = True

    await db.commit()
    await db.refresh(appeal)

    logger.info(
        "Appeal resolved",
        appeal_id=appeal_id,
        resolution=request.resolution,
        moderator_id=current_user.id,
    )

    return AppealResponse(
        id=appeal.id,
        user_id=appeal.user_id,
        username=appeal.user.username if appeal.user else "Unknown",
        moderation_action=ModerationActionResponse(
            id=appeal.moderation_action.id,
            action_type=appeal.moderation_action.action_type,
            reason=appeal.moderation_action.reason,
            duration_days=appeal.moderation_action.duration_days,
            expires_at=appeal.moderation_action.expires_at,
            created_at=appeal.moderation_action.created_at,
        ),
        appeal_text=appeal.appeal_text,
        evidence_urls=appeal.evidence_urls or [],
        status=appeal.status,
        resolution_notes=appeal.resolution_notes,
        created_at=appeal.created_at,
        resolved_at=appeal.resolved_at,
    )


# =============================================================================
# Trade Disputes Endpoints (Task 6.4)
# =============================================================================


@admin_router.get("/disputes", response_model=list[TradeDisputeResponse])
async def list_disputes(
    status: Optional[str] = Query(None, description="Filter by status: open, evidence_requested, resolved"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List trade disputes with optional filtering.

    Requires moderator or admin role.
    """
    require_moderator(current_user)

    offset = (page - 1) * limit
    query = (
        select(TradeDispute)
        .options(selectinload(TradeDispute.filer))
        .order_by(TradeDispute.created_at.desc())
    )

    if status:
        query = query.where(TradeDispute.status == status)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    disputes = result.scalars().all()

    return [
        TradeDisputeResponse(
            id=d.id,
            trade_proposal_id=d.trade_proposal_id,
            filed_by=d.filed_by,
            filer_username=d.filer.username if d.filer else "Unknown",
            dispute_type=d.dispute_type,
            description=d.description,
            status=d.status,
            assigned_moderator_id=d.assigned_moderator_id,
            resolution=d.resolution,
            resolution_notes=d.resolution_notes,
            evidence_snapshot=d.evidence_snapshot,
            created_at=d.created_at,
            resolved_at=d.resolved_at,
        )
        for d in disputes
    ]


@admin_router.get("/disputes/{dispute_id}", response_model=TradeDisputeResponse)
async def get_dispute_detail(
    dispute_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information about a trade dispute.

    Requires moderator or admin role.
    """
    require_moderator(current_user)

    result = await db.execute(
        select(TradeDispute)
        .options(selectinload(TradeDispute.filer))
        .where(TradeDispute.id == dispute_id)
    )
    dispute = result.scalar_one_or_none()

    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    return TradeDisputeResponse(
        id=dispute.id,
        trade_proposal_id=dispute.trade_proposal_id,
        filed_by=dispute.filed_by,
        filer_username=dispute.filer.username if dispute.filer else "Unknown",
        dispute_type=dispute.dispute_type,
        description=dispute.description,
        status=dispute.status,
        assigned_moderator_id=dispute.assigned_moderator_id,
        resolution=dispute.resolution,
        resolution_notes=dispute.resolution_notes,
        evidence_snapshot=dispute.evidence_snapshot,
        created_at=dispute.created_at,
        resolved_at=dispute.resolved_at,
    )


@admin_router.post("/disputes/{dispute_id}/assign")
async def assign_dispute_moderator(
    dispute_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Assign a moderator to a dispute.

    The current user becomes the assigned moderator.
    Requires moderator or admin role.
    """
    require_moderator(current_user)

    dispute = await db.get(TradeDispute, dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    dispute.assigned_moderator_id = current_user.id
    await db.commit()

    logger.info(
        "Dispute assigned",
        dispute_id=dispute_id,
        moderator_id=current_user.id,
    )

    return {"status": "assigned", "moderator_id": current_user.id}


@admin_router.post("/disputes/{dispute_id}/resolve", response_model=TradeDisputeResponse)
async def resolve_dispute(
    dispute_id: int,
    request: ResolveDisputeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Resolve a trade dispute.

    Resolutions: buyer_wins, seller_wins, mutual_cancel, inconclusive.
    Requires moderator or admin role.
    """
    require_moderator(current_user)

    # Validate resolution
    valid_resolutions = ["buyer_wins", "seller_wins", "mutual_cancel", "inconclusive"]
    if request.resolution not in valid_resolutions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid resolution. Must be one of: {', '.join(valid_resolutions)}",
        )

    result = await db.execute(
        select(TradeDispute)
        .options(selectinload(TradeDispute.filer))
        .where(TradeDispute.id == dispute_id)
    )
    dispute = result.scalar_one_or_none()

    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    if dispute.status == "resolved":
        raise HTTPException(status_code=400, detail="Dispute already resolved")

    # Update dispute
    dispute.status = "resolved"
    dispute.resolution = request.resolution
    dispute.resolution_notes = request.notes
    dispute.resolved_at = datetime.now(timezone.utc)
    if not dispute.assigned_moderator_id:
        dispute.assigned_moderator_id = current_user.id

    await db.commit()
    await db.refresh(dispute)

    logger.info(
        "Dispute resolved",
        dispute_id=dispute_id,
        resolution=request.resolution,
        moderator_id=current_user.id,
    )

    return TradeDisputeResponse(
        id=dispute.id,
        trade_proposal_id=dispute.trade_proposal_id,
        filed_by=dispute.filed_by,
        filer_username=dispute.filer.username if dispute.filer else "Unknown",
        dispute_type=dispute.dispute_type,
        description=dispute.description,
        status=dispute.status,
        assigned_moderator_id=dispute.assigned_moderator_id,
        resolution=dispute.resolution,
        resolution_notes=dispute.resolution_notes,
        evidence_snapshot=dispute.evidence_snapshot,
        created_at=dispute.created_at,
        resolved_at=dispute.resolved_at,
    )


# =============================================================================
# Moderator Notes Endpoints (Task 6.5)
# =============================================================================


@admin_router.get("/users/{user_id}/notes", response_model=list[ModNoteInfo])
async def get_user_notes(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all moderator notes for a user.

    Requires moderator or admin role.
    """
    require_moderator(current_user)

    # Check user exists
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(
        select(ModerationNote, User)
        .join(User, ModerationNote.moderator_id == User.id)
        .where(ModerationNote.target_user_id == user_id)
        .order_by(ModerationNote.created_at.desc())
    )
    rows = result.all()

    return [
        ModNoteInfo(
            id=note.id,
            moderator_id=note.moderator_id,
            moderator_username=mod.username,
            content=note.content,
            created_at=note.created_at,
        )
        for note, mod in rows
    ]


@admin_router.post("/users/{user_id}/notes", response_model=ModNoteInfo, status_code=201)
async def add_user_note(
    user_id: int,
    request: AddModNoteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Add a moderator note about a user.

    Requires moderator or admin role.
    """
    require_moderator(current_user)

    # Check user exists
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    note = ModerationNote(
        moderator_id=current_user.id,
        target_user_id=user_id,
        content=request.content,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)

    logger.info(
        "Moderator note added",
        moderator_id=current_user.id,
        target_user_id=user_id,
    )

    return ModNoteInfo(
        id=note.id,
        moderator_id=note.moderator_id,
        moderator_username=current_user.username,
        content=note.content,
        created_at=note.created_at,
    )


# =============================================================================
# User-Facing Dispute Endpoints (Task 6.6)
# =============================================================================


@disputes_router.post("", response_model=TradeDisputeResponse, status_code=201)
async def file_dispute(
    request: FileDisputeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    File a dispute for a trade.

    User must be a participant in the trade.
    """
    # Validate dispute type
    valid_types = ["item_not_as_described", "didnt_ship", "other"]
    if request.dispute_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid dispute type. Must be one of: {', '.join(valid_types)}",
        )

    # Get trade and verify user is participant
    result = await db.execute(
        select(TradeProposal)
        .options(
            selectinload(TradeProposal.proposer),
            selectinload(TradeProposal.recipient),
            selectinload(TradeProposal.items),
        )
        .where(TradeProposal.id == request.trade_id)
    )
    trade = result.scalar_one_or_none()

    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    if trade.proposer_id != current_user.id and trade.recipient_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You must be a participant in the trade to file a dispute",
        )

    # Check for existing dispute
    existing = await db.execute(
        select(TradeDispute).where(
            TradeDispute.trade_proposal_id == request.trade_id,
            TradeDispute.filed_by == current_user.id,
            TradeDispute.status != "resolved",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="You already have an open dispute for this trade",
        )

    # Create dispute with evidence snapshot
    evidence = create_evidence_snapshot(trade)

    dispute = TradeDispute(
        trade_proposal_id=request.trade_id,
        filed_by=current_user.id,
        dispute_type=request.dispute_type,
        description=request.description,
        status="open",
        evidence_snapshot=evidence,
    )
    db.add(dispute)
    await db.commit()
    await db.refresh(dispute)

    logger.warning(
        "Trade dispute filed",
        dispute_id=dispute.id,
        trade_id=request.trade_id,
        filed_by=current_user.id,
        dispute_type=request.dispute_type,
    )

    return TradeDisputeResponse(
        id=dispute.id,
        trade_proposal_id=dispute.trade_proposal_id,
        filed_by=dispute.filed_by,
        filer_username=current_user.username,
        dispute_type=dispute.dispute_type,
        description=dispute.description,
        status=dispute.status,
        assigned_moderator_id=dispute.assigned_moderator_id,
        resolution=dispute.resolution,
        resolution_notes=dispute.resolution_notes,
        evidence_snapshot=dispute.evidence_snapshot,
        created_at=dispute.created_at,
        resolved_at=dispute.resolved_at,
    )


@disputes_router.get("", response_model=list[TradeDisputeResponse])
async def get_my_disputes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get disputes filed by or involving the current user.
    """
    # Get user's trade IDs
    trades_result = await db.execute(
        select(TradeProposal.id).where(
            or_(
                TradeProposal.proposer_id == current_user.id,
                TradeProposal.recipient_id == current_user.id,
            )
        )
    )
    user_trade_ids = [t for t in trades_result.scalars().all()]

    # Get disputes
    result = await db.execute(
        select(TradeDispute)
        .options(selectinload(TradeDispute.filer))
        .where(
            or_(
                TradeDispute.filed_by == current_user.id,
                TradeDispute.trade_proposal_id.in_(user_trade_ids) if user_trade_ids else False,
            )
        )
        .order_by(TradeDispute.created_at.desc())
    )
    disputes = result.scalars().all()

    return [
        TradeDisputeResponse(
            id=d.id,
            trade_proposal_id=d.trade_proposal_id,
            filed_by=d.filed_by,
            filer_username=d.filer.username if d.filer else "Unknown",
            dispute_type=d.dispute_type,
            description=d.description,
            status=d.status,
            assigned_moderator_id=d.assigned_moderator_id,
            resolution=d.resolution,
            resolution_notes=d.resolution_notes,
            evidence_snapshot=d.evidence_snapshot,
            created_at=d.created_at,
            resolved_at=d.resolved_at,
        )
        for d in disputes
    ]
