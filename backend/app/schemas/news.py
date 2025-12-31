"""
News article schemas for API responses.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CardMentionResponse(BaseModel):
    """A card mentioned in a news article."""
    card_id: int
    card_name: str
    context: Optional[str] = None

    class Config:
        from_attributes = True


class NewsArticleBase(BaseModel):
    """Base news article fields."""
    id: int
    title: str
    source: str
    source_display: str = Field(description="Human-friendly source name")
    published_at: Optional[datetime] = None
    external_url: str
    summary: Optional[str] = None

    class Config:
        from_attributes = True


class NewsArticleListItem(NewsArticleBase):
    """News article in list view with mention count."""
    card_mention_count: int = 0


class NewsArticleDetail(NewsArticleBase):
    """Full news article with card mentions."""
    author: Optional[str] = None
    category: Optional[str] = None
    card_mentions: list[CardMentionResponse] = []


class NewsListResponse(BaseModel):
    """Paginated list of news articles."""
    items: list[NewsArticleListItem]
    total: int
    has_more: bool


class CardNewsItem(BaseModel):
    """News article for card detail page."""
    id: int
    title: str
    source_display: str
    published_at: Optional[datetime] = None
    external_url: str
    context: Optional[str] = None

    class Config:
        from_attributes = True


class CardNewsResponse(BaseModel):
    """News articles mentioning a specific card."""
    items: list[CardNewsItem]
    total: int
