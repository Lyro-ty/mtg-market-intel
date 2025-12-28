"""
Tournament model for MTG tournament results.

Stores tournament data including decklists, placements, and card usage statistics.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card


class Tournament(Base):
    """
    Represents an MTG tournament event.
    
    Stores tournament metadata and results.
    """
    
    __tablename__ = "tournaments"
    
    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Standard, Modern, Legacy, etc.
    format: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Constructed, Limited, etc.
    
    # Tournament details
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    organizer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # MTGGoldfish, MTGTop8, etc.
    external_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)  # ID from source
    external_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Dates
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Statistics
    total_players: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_decks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Metadata
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # mtggoldfish, mtgtop8, etc.
    raw_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string of raw data
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    decklists: Mapped[list["Decklist"]] = relationship(
        "Decklist", back_populates="tournament", cascade="all, delete-orphan"
    )
    
    # Indexes (start_date already has index=True on column definition)
    __table_args__ = (
        Index("ix_tournaments_source", "source"),
        Index("ix_tournaments_external_id_source", "external_id", "source", unique=True),
    )
    
    def __repr__(self) -> str:
        return f"<Tournament {self.name} ({self.event_type})>"


class Decklist(Base):
    """
    Represents a decklist from a tournament.
    
    Links cards to tournaments and tracks their usage/performance.
    """
    
    __tablename__ = "decklists"
    
    # Foreign keys
    tournament_id: Mapped[int] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Deck information
    player_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    deck_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    archetype: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Aggro, Control, Combo, etc.
    
    # Performance
    placement: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)  # 1st, 2nd, etc.
    record: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # "6-0", "5-1", etc.
    
    # External reference
    external_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    external_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Raw decklist data (JSON string)
    mainboard: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON: {card_id: quantity}
    sideboard: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON: {card_id: quantity}
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    tournament: Mapped["Tournament"] = relationship("Tournament", back_populates="decklists")
    card_usages: Mapped[list["CardTournamentUsage"]] = relationship(
        "CardTournamentUsage", back_populates="decklist", cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_decklists_tournament_placement", "tournament_id", "placement"),
    )
    
    def __repr__(self) -> str:
        return f"<Decklist {self.deck_name} by {self.player_name} (Place: {self.placement})>"


class CardTournamentUsage(Base):
    """
    Tracks card usage in tournament decklists.
    
    Links cards to decklists and tournaments for popularity metrics.
    """
    
    __tablename__ = "card_tournament_usage"
    
    # Foreign keys
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    decklist_id: Mapped[int] = mapped_column(
        ForeignKey("decklists.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Usage data
    quantity_mainboard: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quantity_sideboard: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_commander: Mapped[bool] = mapped_column(default=False, nullable=False)  # For Commander format
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Relationships
    card: Mapped["Card"] = relationship("Card")
    decklist: Mapped["Decklist"] = relationship("Decklist", back_populates="card_usages")
    
    # Indexes
    __table_args__ = (
        Index("ix_card_tournament_usage_card_decklist", "card_id", "decklist_id", unique=True),
    )
    
    def __repr__(self) -> str:
        return f"<CardTournamentUsage card_id={self.card_id} decklist_id={self.decklist_id} qty={self.quantity_mainboard}>"

