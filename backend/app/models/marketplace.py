"""
Marketplace model representing MTG card marketplaces.
"""
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.price_snapshot import PriceSnapshot
    from app.models.recommendation import Recommendation


class Marketplace(Base):
    """
    Represents a marketplace where MTG cards can be bought/sold.
    
    Examples: TCGPlayer, CardMarket, Card Kingdom, etc.
    """
    
    __tablename__ = "marketplaces"
    
    # Identity
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    
    # Configuration
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    api_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Status
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    supports_api: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Currency
    default_currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    
    # Scraping config
    rate_limit_seconds: Mapped[float] = mapped_column(default=1.0, nullable=False)
    
    # Relationships
    price_snapshots: Mapped[list["PriceSnapshot"]] = relationship(
        "PriceSnapshot", back_populates="marketplace", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(
        "Recommendation", back_populates="marketplace"
    )
    
    def __repr__(self) -> str:
        return f"<Marketplace {self.name}>"

