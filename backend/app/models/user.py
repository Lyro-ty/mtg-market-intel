"""
User model for authentication.
"""
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.collection_stats import CollectionStats
    from app.models.inventory import InventoryItem
    from app.models.notification import Notification
    from app.models.settings import AppSettings
    from app.models.session import UserSession
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

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.email})>"

