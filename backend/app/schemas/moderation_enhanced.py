"""
Enhanced moderation Pydantic schemas for API request/response validation.

Provides schemas for:
- Moderation queue items and cases
- Moderation actions (warn, restrict, suspend, ban)
- Appeals for moderation actions
- Trade disputes
- Moderator notes
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============ Nested User Info ============


class ModTargetUserInfo(BaseModel):
    """Basic user info for moderation context."""

    id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ Moderation Queue ============


class ModerationQueueItem(BaseModel):
    """Item in the moderation queue for review."""

    id: int
    target_user_id: int
    target_username: str
    flag_level: str  # low, medium, high, critical
    flag_type: str  # report, auto_flag, dispute
    flag_reason: str
    report_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class ModerationQueueResponse(BaseModel):
    """Paginated moderation queue response."""

    items: list[ModerationQueueItem]
    total: int
    pending_count: int
    high_priority_count: int


# ============ Report and Flag Info ============


class ReportInfo(BaseModel):
    """Summary of a user report."""

    id: int
    reporter_id: int
    reporter_username: str
    reason: str
    details: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AutoFlagInfo(BaseModel):
    """Summary of an auto-generated flag."""

    id: int
    flag_type: str
    severity: str
    reason: str
    created_at: datetime

    class Config:
        from_attributes = True


class PreviousActionInfo(BaseModel):
    """Summary of a previous moderation action."""

    id: int
    action_type: str
    reason: Optional[str] = None
    moderator_username: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ModNoteInfo(BaseModel):
    """Summary of a moderator note."""

    id: int
    moderator_id: int
    moderator_username: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class TradeStatsSummary(BaseModel):
    """Trade statistics for a user."""

    total_trades: int = 0
    completed_trades: int = 0
    cancelled_trades: int = 0
    disputed_trades: int = 0
    completion_rate: float = 0.0


class RecentTradeInfo(BaseModel):
    """Brief info about a recent trade."""

    id: int
    other_party_username: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None


class ReportedMessageInfo(BaseModel):
    """A message that was flagged/reported."""

    id: int
    content: str
    recipient_username: str
    sent_at: datetime


# ============ Moderation Case Detail ============


class ModerationCaseDetail(BaseModel):
    """Detailed case information for moderator review."""

    id: int
    target_user_id: int
    target_user: dict[str, Any]  # Full user info as dict
    reports: list[ReportInfo] = []
    auto_flags: list[AutoFlagInfo] = []
    previous_actions: list[PreviousActionInfo] = []
    mod_notes: list[ModNoteInfo] = []
    trade_stats: TradeStatsSummary
    recent_trades: list[RecentTradeInfo] = []
    reported_messages: list[ReportedMessageInfo] = []


# ============ Moderation Action Schemas ============


class TakeActionRequest(BaseModel):
    """Request to take a moderation action."""

    action: str = Field(
        ...,
        description="Action type: dismiss, warn, restrict, suspend, ban, escalate",
    )
    reason: str = Field(..., min_length=1, max_length=2000)
    duration_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=365,
        description="Duration in days for temporary actions",
    )
    related_report_id: Optional[int] = None


class ModerationActionResponse(BaseModel):
    """Response for a moderation action."""

    id: int
    action_type: str
    reason: Optional[str] = None
    duration_days: Optional[int] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============ Appeal Schemas ============


class AppealResponse(BaseModel):
    """Response for a user appeal."""

    id: int
    user_id: int
    username: str
    moderation_action: ModerationActionResponse
    appeal_text: str
    evidence_urls: list[str] = []
    status: str  # pending, upheld, reduced, overturned
    resolution_notes: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ResolveAppealRequest(BaseModel):
    """Request to resolve an appeal."""

    resolution: str = Field(
        ...,
        description="Resolution: upheld, reduced, overturned",
    )
    notes: str = Field(..., min_length=1, max_length=2000)


# ============ Trade Dispute Schemas ============


class TradeDisputeResponse(BaseModel):
    """Response for a trade dispute."""

    id: int
    trade_proposal_id: Optional[int] = None
    filed_by: int
    filer_username: str
    dispute_type: str  # item_not_as_described, didnt_ship, other
    description: Optional[str] = None
    status: str  # open, evidence_requested, resolved
    assigned_moderator_id: Optional[int] = None
    resolution: Optional[str] = None  # buyer_wins, seller_wins, mutual_cancel, inconclusive
    resolution_notes: Optional[str] = None
    evidence_snapshot: Optional[dict[str, Any]] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FileDisputeRequest(BaseModel):
    """Request to file a trade dispute."""

    trade_id: int
    dispute_type: str = Field(
        ...,
        description="Type: item_not_as_described, didnt_ship, other",
    )
    description: str = Field(..., min_length=10, max_length=2000)


class ResolveDisputeRequest(BaseModel):
    """Request to resolve a trade dispute."""

    resolution: str = Field(
        ...,
        description="Resolution: buyer_wins, seller_wins, mutual_cancel, inconclusive",
    )
    notes: str = Field(..., min_length=1, max_length=2000)


# ============ Moderator Note Schemas ============


class AddModNoteRequest(BaseModel):
    """Request to add a moderator note."""

    content: str = Field(..., min_length=1, max_length=2000)
