"""
Signal model for analytics signals and AI-generated insights.
"""
from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card


class Signal(Base):
    """
    Analytics signals and AI-generated insights for cards.
    
    Stores computed indicators and LLM-generated explanations.
    """
    
    __tablename__ = "signals"
    
    # Foreign key
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Date
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    # Signal type
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # Types: momentum_up, momentum_down, volatility_high, volatility_low,
    #        spread_high, spike_up, spike_down, trend_bullish, trend_bearish, stable
    
    # Signal value (numeric representation)
    value: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    
    # Confidence score (0-1)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    
    # Detailed data (JSON)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # LLM-generated insight
    llm_insight: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Relationship
    card: Mapped["Card"] = relationship("Card", back_populates="signals")
    
    # Indexes
    __table_args__ = (
        Index("ix_signals_card_date", "card_id", "date"),
        Index("ix_signals_type_date", "signal_type", "date"),
        Index("ix_signals_card_type", "card_id", "signal_type"),
    )
    
    def __repr__(self) -> str:
        return f"<Signal {self.signal_type} for {self.card_id} on {self.date}>"

