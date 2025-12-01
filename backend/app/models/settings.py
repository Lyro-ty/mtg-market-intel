"""
AppSettings model for storing per-user application configuration.
"""
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class AppSettings(Base):
    """
    Per-user key-value store for application settings.
    
    Used for user-configurable options like enabled marketplaces,
    ROI thresholds, etc. Each user has their own settings.
    """
    
    __tablename__ = "app_settings"
    
    # User relationship
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Key-value pair
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Metadata
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    value_type: Mapped[str] = mapped_column(String(20), default="string", nullable=False)
    # Types: string, integer, float, boolean, json
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="settings")
    
    # Unique constraint: each user can only have one setting per key
    __table_args__ = (
        UniqueConstraint('user_id', 'key', name='uq_app_settings_user_key'),
    )
    
    def __repr__(self) -> str:
        return f"<AppSettings user_id={self.user_id} {self.key}={self.value[:50]}>"


# Default settings keys
DEFAULT_SETTINGS = {
    "enabled_marketplaces": {
        "value": '["tcgplayer", "cardmarket", "cardkingdom"]',
        "description": "List of enabled marketplace slugs",
        "value_type": "json"
    },
    "min_roi_threshold": {
        "value": "0.10",
        "description": "Minimum ROI threshold for buy recommendations (10%)",
        "value_type": "float"
    },
    "min_confidence_threshold": {
        "value": "0.60",
        "description": "Minimum confidence score for showing recommendations",
        "value_type": "float"
    },
    "recommendation_horizon_days": {
        "value": "7",
        "description": "Default time horizon for recommendations in days",
        "value_type": "integer"
    },
    "price_history_days": {
        "value": "90",
        "description": "Number of days of price history to display",
        "value_type": "integer"
    },
    "scraping_enabled": {
        "value": "true",
        "description": "Enable/disable automated scraping",
        "value_type": "boolean"
    },
    "analytics_enabled": {
        "value": "true",
        "description": "Enable/disable automated analytics",
        "value_type": "boolean"
    },
}

