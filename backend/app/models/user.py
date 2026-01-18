"""
User model for authentication.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card
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
    from app.models.social import (
        NotificationPreference,
        UserFavorite,
        UserFormatSpecialty,
        UserNote,
    )
    from app.models.trading_post import TradingPost, TradeQuote
    from app.models.user_milestone import UserMilestone
    from app.models.want_list import WantListItem
    from app.models.reputation import UserReputation
    from app.models.trade import TradeProposal
    from app.models.achievement import UserAchievement, UserFrame


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

    # Profile card fields (social trading)
    tagline: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    signature_card_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("cards.id", ondelete="SET NULL"),
        nullable=True,
    )
    card_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # collector, trader, brewer, investor
    card_type_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Extended location fields
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    shipping_preference: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # local, domestic, international

    # Frame and discovery
    active_frame_tier: Mapped[str] = mapped_column(String(20), default="bronze", nullable=False)
    discovery_score: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    # Privacy settings
    show_in_directory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_in_search: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_online_status: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_portfolio_tier: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Onboarding
    onboarding_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
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

    # Trading Post relationships
    trading_post: Mapped[Optional["TradingPost"]] = relationship(
        "TradingPost",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    trade_quotes: Mapped[list["TradeQuote"]] = relationship(
        "TradeQuote",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Reputation relationship
    reputation: Mapped[Optional["UserReputation"]] = relationship(
        "UserReputation",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

    # Trade proposal relationships
    sent_trade_proposals: Mapped[list["TradeProposal"]] = relationship(
        "TradeProposal",
        foreign_keys="TradeProposal.proposer_id",
        cascade="all, delete-orphan"
    )
    received_trade_proposals: Mapped[list["TradeProposal"]] = relationship(
        "TradeProposal",
        foreign_keys="TradeProposal.recipient_id",
        cascade="all, delete-orphan"
    )

    # Achievement relationships
    achievements: Mapped[list["UserAchievement"]] = relationship(
        "UserAchievement",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    frames: Mapped[list["UserFrame"]] = relationship(
        "UserFrame",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Social trading relationships
    signature_card: Mapped[Optional["Card"]] = relationship(
        "Card",
        foreign_keys=[signature_card_id],
        lazy="joined",
    )
    favorites: Mapped[list["UserFavorite"]] = relationship(
        "UserFavorite",
        foreign_keys="UserFavorite.user_id",
        cascade="all, delete-orphan",
    )
    notes: Mapped[list["UserNote"]] = relationship(
        "UserNote",
        foreign_keys="UserNote.user_id",
        cascade="all, delete-orphan",
    )
    format_specialties: Mapped[list["UserFormatSpecialty"]] = relationship(
        "UserFormatSpecialty",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    notification_preferences: Mapped[Optional["NotificationPreference"]] = relationship(
        "NotificationPreference",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.email})>"

