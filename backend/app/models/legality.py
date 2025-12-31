"""
LegalityChange model for tracking format legality changes.

Records when cards become banned, restricted, or legal in different formats.
This enables historical analysis and price impact correlation.
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card


class LegalityChange(Base):
    """
    Record of a legality status change for a card in a format.

    Tracks bans, unbans, restrictions, and new format introductions.
    Used for:
    - Historical ban list analysis
    - Price impact correlation (bans typically cause price crashes)
    - Format evolution tracking

    Attributes:
        id: Primary key
        card_id: Foreign key to the card
        format: Format name ('modern', 'standard', 'legacy', etc.)
        old_status: Previous legality status (None if newly tracked)
        new_status: New legality status
        changed_at: When the change occurred
        source: How we detected the change ('wotc_announcement', 'scryfall_sync')
        announcement_url: Optional URL to official announcement
    """

    __tablename__ = "legality_changes"

    id: Mapped[int] = mapped_column(primary_key=True)

    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    format: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    old_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    new_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    announcement_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    card: Mapped["Card"] = relationship("Card", back_populates="legality_changes")

    def __repr__(self) -> str:
        change_type = "BANNED" if self.new_status == "banned" else self.new_status.upper()
        return f"<LegalityChange {change_type} in {self.format}: {self.old_status} -> {self.new_status}>"

    @property
    def is_ban(self) -> bool:
        """Check if this change is a ban."""
        return self.new_status == "banned" and self.old_status in (None, "legal")

    @property
    def is_unban(self) -> bool:
        """Check if this change is an unban."""
        return self.new_status == "legal" and self.old_status == "banned"

    @property
    def is_restriction(self) -> bool:
        """Check if this change is a restriction."""
        return self.new_status == "restricted"
