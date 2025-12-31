"""
User model for authentication.
"""
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.collection_stats import CollectionStats
    from app.models.connection import (
        ConnectionRequest,
        Message,
        UserEndorsement,
    )
    from app.models.import_job import ImportJob
    from app.models.inventory import InventoryItem
    from app.models.notification import Notification
    from app.models.portfolio_snapshot import PortfolioSnapshot
    from app.models.saved_search import SavedSearch
    from app.models.settings import AppSettings
    from app.models.session import UserSession
    from app.models.user_milestone import UserMilestone
    from app.models.want_list import WantListItem


class User(Base):
    """
    User model for authentication and authorization.
    
    Passwords are stored using bcrypt hashing.
    """
    
    __tablename__ = "users"
    
    # Core user fields
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    # Profile fields
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    discord_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, unique=True, index=True)
    discord_username: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    discord_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Account status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Security fields
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # OAuth fields
    oauth_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    oauth_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Notification preferences
    email_alerts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    price_drop_threshold: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    digest_frequency: Mapped[str] = mapped_column(String(10), default="instant", nullable=False)

    # Relationships
    inventory_items: Mapped[list["InventoryItem"]] = relationship(
        "InventoryItem",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    settings: Mapped[list["AppSettings"]] = relationship(
        "AppSettings",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    want_list_items: Mapped[list["WantListItem"]] = relationship(
        "WantListItem",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    collection_stats: Mapped[Optional["CollectionStats"]] = relationship(
        "CollectionStats",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    milestones: Mapped[list["UserMilestone"]] = relationship(
        "UserMilestone",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    import_jobs: Mapped[list["ImportJob"]] = relationship(
        "ImportJob",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    portfolio_snapshots: Mapped[list["PortfolioSnapshot"]] = relationship(
        "PortfolioSnapshot",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    saved_searches: Mapped[list["SavedSearch"]] = relationship(
        "SavedSearch",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Connection relationships
    sent_connection_requests: Mapped[list["ConnectionRequest"]] = relationship(
        "ConnectionRequest",
        foreign_keys="ConnectionRequest.requester_id",
        back_populates="requester",
        cascade="all, delete-orphan"
    )
    received_connection_requests: Mapped[list["ConnectionRequest"]] = relationship(
        "ConnectionRequest",
        foreign_keys="ConnectionRequest.recipient_id",
        back_populates="recipient",
        cascade="all, delete-orphan"
    )

    # Message relationships
    sent_messages: Mapped[list["Message"]] = relationship(
        "Message",
        foreign_keys="Message.sender_id",
        back_populates="sender",
        cascade="all, delete-orphan"
    )
    received_messages: Mapped[list["Message"]] = relationship(
        "Message",
        foreign_keys="Message.recipient_id",
        back_populates="recipient",
        cascade="all, delete-orphan"
    )

    # Endorsement relationships
    given_endorsements: Mapped[list["UserEndorsement"]] = relationship(
        "UserEndorsement",
        foreign_keys="UserEndorsement.endorser_id",
        back_populates="endorser",
        cascade="all, delete-orphan"
    )
    received_endorsements: Mapped[list["UserEndorsement"]] = relationship(
        "UserEndorsement",
        foreign_keys="UserEndorsement.endorsed_id",
        back_populates="endorsed",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.email})>"

