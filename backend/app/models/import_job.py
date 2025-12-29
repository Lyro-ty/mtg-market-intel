"""Import job model for tracking collection imports from external platforms."""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ImportPlatform(str, Enum):
    """Supported import platforms."""
    MOXFIELD = "moxfield"
    ARCHIDEKT = "archidekt"
    DECKBOX = "deckbox"
    TCGPLAYER = "tcgplayer"
    GENERIC_CSV = "generic_csv"


class ImportStatus(str, Enum):
    """Import job status."""
    PENDING = "pending"          # Uploaded, awaiting preview
    PREVIEWING = "previewing"    # Parsing file for preview
    PREVIEW_READY = "preview_ready"  # Preview ready for user confirmation
    IMPORTING = "importing"      # User confirmed, importing cards
    COMPLETED = "completed"      # Import finished
    FAILED = "failed"           # Import failed
    CANCELLED = "cancelled"     # User cancelled


class ImportJob(Base):
    """Tracks collection import jobs from external platforms."""

    __tablename__ = "import_jobs"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    platform: Mapped[ImportPlatform] = mapped_column(
        String(30),
        nullable=False,
        index=True
    )
    status: Mapped[ImportStatus] = mapped_column(
        String(20),
        default=ImportStatus.PENDING,
        nullable=False,
        index=True
    )

    # File info
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False)

    # Raw content stored temporarily for processing
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Parsed preview data (JSON array of parsed rows)
    preview_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Import statistics
    total_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    matched_cards: Mapped[int] = mapped_column(default=0, nullable=False)
    unmatched_cards: Mapped[int] = mapped_column(default=0, nullable=False)
    imported_count: Mapped[int] = mapped_column(default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(default=0, nullable=False)

    # Error details
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    errors_detail: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="import_jobs")

    __table_args__ = (
        Index("ix_import_jobs_user_status", "user_id", "status"),
        Index("ix_import_jobs_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ImportJob id={self.id} platform={self.platform} status={self.status}>"
