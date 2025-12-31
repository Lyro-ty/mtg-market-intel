"""
News models for MTG news articles and card mentions.

Stores articles from RSS feeds and links to cards mentioned in them.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card


class NewsArticle(Base):
    """
    A news article from an MTG news source.

    Sources include MTGGoldfish, Channel Fireball, etc.
    """

    __tablename__ = "news_articles"

    # Article identity
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # e.g., "mtggoldfish", "channelfireball", "tcgplayer"

    url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)

    # Content
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # RSS feeds usually provide summary/description, not full content

    author: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Timestamps
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow
    )

    # Categories/tags from the RSS feed
    categories: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Stored as comma-separated values

    # Relationships
    card_mentions: Mapped[list["CardNewsMention"]] = relationship(
        "CardNewsMention",
        back_populates="article",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_news_articles_source_published", "source", "published_at"),
    )

    def __repr__(self) -> str:
        return f"<NewsArticle {self.source}: {self.title[:50]}>"


class CardNewsMention(Base):
    """
    Links a card to a news article that mentions it.

    Used to show relevant news on card detail pages.
    """

    __tablename__ = "card_news_mentions"

    # Foreign keys
    article_id: Mapped[int] = mapped_column(
        ForeignKey("news_articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Context - where in the article was the card mentioned?
    mention_context: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # e.g., "...Ragavan, Nimble Pilferer sees play in Modern..."

    # Relationships
    article: Mapped["NewsArticle"] = relationship("NewsArticle", back_populates="card_mentions")
    card: Mapped["Card"] = relationship("Card", back_populates="news_mentions")

    # Constraints
    __table_args__ = (
        UniqueConstraint("article_id", "card_id", name="uq_card_news_mention"),
        Index("ix_card_news_mentions_card_article", "card_id", "article_id"),
    )

    def __repr__(self) -> str:
        return f"<CardNewsMention article={self.article_id} card={self.card_id}>"
