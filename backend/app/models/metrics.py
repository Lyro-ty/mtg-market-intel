"""
MetricsCardsDaily model for aggregated daily card metrics.
"""
from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, ForeignKey, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card


class MetricsCardsDaily(Base):
    """
    Daily aggregated metrics for a card across all marketplaces.
    
    Pre-computed for efficient dashboard and analytics queries.
    """
    
    __tablename__ = "metrics_cards_daily"
    
    # Foreign key
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Date
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    # Price metrics (across all marketplaces)
    avg_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    min_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    max_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    median_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    
    # Spread metrics
    spread: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)  # max - min
    spread_pct: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)  # spread as %
    
    # Volume proxies
    total_listings: Mapped[Optional[int]] = mapped_column(nullable=True)
    total_quantity: Mapped[Optional[int]] = mapped_column(nullable=True)
    num_marketplaces: Mapped[Optional[int]] = mapped_column(nullable=True)
    
    # Price change metrics
    price_change_1d: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    price_change_7d: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    price_change_30d: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    
    price_change_pct_1d: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    price_change_pct_7d: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    price_change_pct_30d: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    
    # Moving averages
    ma_7d: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    ma_30d: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    
    # Volatility
    volatility_7d: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    volatility_30d: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    
    # Relationship
    card: Mapped["Card"] = relationship("Card", back_populates="metrics")
    
    # Indexes
    __table_args__ = (
        Index("ix_metrics_card_date", "card_id", "date", unique=True),
        Index("ix_metrics_date", "date"),
        Index("ix_metrics_spread", "spread_pct"),
        Index("ix_metrics_change", "price_change_pct_7d"),
    )
    
    def __repr__(self) -> str:
        return f"<MetricsCardsDaily {self.card_id} on {self.date}: avg={self.avg_price}>"

