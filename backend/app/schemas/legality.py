"""
Legality change schemas.
"""
from datetime import datetime
from pydantic import BaseModel


class LegalityChangeItem(BaseModel):
    """Single legality change record."""
    id: int
    format: str
    old_status: str | None
    new_status: str
    changed_at: datetime
    source: str | None = None
    announcement_url: str | None = None
    is_ban: bool
    is_unban: bool

    class Config:
        from_attributes = True


class CardLegalityHistoryResponse(BaseModel):
    """Legality change history for a card."""
    card_id: int
    card_name: str
    changes: list[LegalityChangeItem]
    total: int
    has_been_banned: bool
    currently_banned_in: list[str]


class RecentBansResponse(BaseModel):
    """Response for recent bans across all formats."""
    bans: list[dict]
    total: int
    from_date: datetime
