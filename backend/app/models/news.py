"""
News model for MTG-related news articles and market updates.

Stores news articles, market updates, and other relevant information
that can impact card prices and be used for RAG retrieval.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.card import Card


class NewsArticle(Base):
    """
    Represents an MTG-related news article or market update.
    
    Stores articles from various sources that can impact card prices.
    """
    
    __tablename__ = "news_articles"
    
    # Identity
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Full article text
    
    # Source information
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # reddit, twitter, mtggoldfish, etc.
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)  # ID from source
    external_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Categorization
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # price_update, ban_announcement, set_release, etc.
    tags: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # JSON array of tags
    
    # Dates
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    
    # Engagement metrics (for popularity)
    upvotes: Mapped[Optional[int]] = mapped_column(default=0, nullable=True)
    comments_count: Mapped[Optional[int]] = mapped_column(default=0, nullable=True)
    views: Mapped[Optional[int]] = mapped_column(default=0, nullable=True)
    
    # Raw data
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
    card_mentions: Mapped[list["CardNewsMention"]] = relationship(
        "CardNewsMention", back_populates="article", cascade="all, delete-orphan"
    )
    
    # Indexes (published_at, source, external_id already have index=True on column definitions)
    __table_args__ = (
        Index("ix_news_articles_source_external_id", "source", "external_id", unique=True),
        Index("ix_news_articles_category", "category"),
    )
    
    def __repr__(self) -> str:
        return f"<NewsArticle {self.title[:50]}... ({self.source})>"


class CardNewsMention(Base):
    """
    Tracks card mentions in news articles.
    
    Links cards to news articles for popularity and relevance tracking.
    """
    
    __tablename__ = "card_news_mentions"
    
    # Foreign keys
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    article_id: Mapped[int] = mapped_column(
        ForeignKey("news_articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Mention data
    mention_count: Mapped[int] = mapped_column(default=1, nullable=False)  # How many times card is mentioned
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Surrounding text context
    sentiment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # positive, negative, neutral
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Relationships
    card: Mapped["Card"] = relationship("Card")
    article: Mapped["NewsArticle"] = relationship("NewsArticle", back_populates="card_mentions")
    
    # Indexes
    __table_args__ = (
        Index("ix_card_news_mentions_card_article", "card_id", "article_id", unique=True),
    )
    
    def __repr__(self) -> str:
        return f"<CardNewsMention card_id={self.card_id} article_id={self.article_id} count={self.mention_count}>"

