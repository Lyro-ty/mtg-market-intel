"""
Tournament models for TopDeck.gg integration.

Stores tournament data including standings, decklists, and aggregated meta statistics.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card


class Tournament(Base):
    """
    Represents a tournament event from TopDeck.gg.

    Stores tournament metadata and relationships to standings.
    """

    __tablename__ = "tournaments"

    # Identity
    # String(100) for topdeck_id allows alphanumeric IDs + room for future formats
    topdeck_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    format: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # Standard, Modern, Pioneer, etc.
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Tournament structure
    player_count: Mapped[int] = mapped_column(Integer, nullable=False)
    swiss_rounds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    top_cut_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Top 8, Top 16, etc.

    # Location
    city: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    venue: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Attribution
    topdeck_url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Relationships
    standings: Mapped[list["TournamentStanding"]] = relationship(
        "TournamentStanding", back_populates="tournament", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_tournaments_format_date", "format", "date"),
        Index("ix_tournaments_date_desc", "date", postgresql_ops={"date": "DESC"}),
    )

    def __repr__(self) -> str:
        return f"<Tournament {self.name} ({self.format} - {self.date.strftime('%Y-%m-%d')})>"


class TournamentStanding(Base):
    """
    Represents a player's standing in a tournament.

    Links players to their performance and decklists.
    """

    __tablename__ = "tournament_standings"

    # Foreign keys
    tournament_id: Mapped[int] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Player info
    player_name: Mapped[str] = mapped_column(String(255), nullable=False)
    player_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # TopDeck.gg player ID

    # Standing
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    wins: Mapped[int] = mapped_column(Integer, nullable=False)
    losses: Mapped[int] = mapped_column(Integer, nullable=False)
    draws: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    win_rate: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    tournament: Mapped["Tournament"] = relationship("Tournament", back_populates="standings")
    decklist: Mapped[Optional["Decklist"]] = relationship(
        "Decklist", back_populates="standing", uselist=False, cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_tournament_standings_tournament_rank", "tournament_id", "rank"),
        CheckConstraint("wins >= 0", name="check_wins_non_negative"),
        CheckConstraint("losses >= 0", name="check_losses_non_negative"),
        CheckConstraint("draws >= 0", name="check_draws_non_negative"),
        CheckConstraint("win_rate >= 0 AND win_rate <= 1", name="check_win_rate_range"),
    )

    def __repr__(self) -> str:
        return f"<TournamentStanding {self.player_name} - Rank {self.rank} ({self.wins}-{self.losses}-{self.draws})>"


class Decklist(Base):
    """
    Represents a player's decklist in a tournament.

    One-to-one relationship with TournamentStanding.
    """

    __tablename__ = "decklists"

    # Foreign keys
    standing_id: Mapped[int] = mapped_column(
        ForeignKey("tournament_standings.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )

    # Deck metadata
    archetype_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Relationships
    standing: Mapped["TournamentStanding"] = relationship("TournamentStanding", back_populates="decklist")
    cards: Mapped[list["DecklistCard"]] = relationship(
        "DecklistCard", back_populates="decklist", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        archetype = self.archetype_name or "Unknown"
        return f"<Decklist {archetype}>"


class DecklistCard(Base):
    """
    Represents a card in a decklist.

    Links cards to decklists with quantity and section information.
    """

    __tablename__ = "decklist_cards"

    # Foreign keys
    decklist_id: Mapped[int] = mapped_column(
        ForeignKey("decklists.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Card details
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(
        Enum("mainboard", "sideboard", "commander", name="decklist_section"),
        nullable=False
    )

    # Relationships
    decklist: Mapped["Decklist"] = relationship("Decklist", back_populates="cards")
    card: Mapped["Card"] = relationship("Card")

    # Indexes
    __table_args__ = (
        Index("ix_decklist_cards_decklist_section", "decklist_id", "section"),
        Index("ix_decklist_cards_card_section", "card_id", "section"),
        CheckConstraint("quantity > 0", name="check_quantity_positive"),
    )

    def __repr__(self) -> str:
        return f"<DecklistCard card_id={self.card_id} qty={self.quantity} section={self.section}>"


class CardMetaStats(Base):
    """
    Aggregated tournament statistics for cards.

    Tracks meta performance over different time periods.
    """

    __tablename__ = "card_meta_stats"

    # Foreign keys
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Aggregation context
    format: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    period: Mapped[str] = mapped_column(
        Enum("7d", "30d", "90d", name="meta_period"),
        nullable=False
    )

    # Aggregated statistics
    deck_inclusion_rate: Mapped[float] = mapped_column(Float, nullable=False)  # % of decks including this card
    avg_copies: Mapped[float] = mapped_column(Float, nullable=False)  # Average copies per deck when included
    top8_rate: Mapped[float] = mapped_column(Float, nullable=False)  # % of top 8 decks including this card
    win_rate_delta: Mapped[float] = mapped_column(Float, nullable=False)  # Win rate difference from format average

    # Relationships
    card: Mapped["Card"] = relationship("Card")

    # Indexes
    __table_args__ = (
        Index("ix_card_meta_stats_card_format_period", "card_id", "format", "period", unique=True),
        Index("ix_card_meta_stats_format_period", "format", "period"),
        CheckConstraint("deck_inclusion_rate >= 0 AND deck_inclusion_rate <= 1", name="check_inclusion_rate_range"),
        CheckConstraint("avg_copies >= 0", name="check_avg_copies_non_negative"),
        CheckConstraint("top8_rate >= 0 AND top8_rate <= 1", name="check_top8_rate_range"),
        CheckConstraint("win_rate_delta >= -1 AND win_rate_delta <= 1", name="check_win_rate_delta_range"),
    )

    def __repr__(self) -> str:
        return f"<CardMetaStats card_id={self.card_id} {self.format} {self.period} inclusion={self.deck_inclusion_rate:.2%}>"
