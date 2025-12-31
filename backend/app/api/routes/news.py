"""
News API endpoints for MTG news articles.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models import NewsArticle, CardNewsMention, Card
from app.schemas.news import (
    NewsListResponse,
    NewsArticleListItem,
    NewsArticleDetail,
    CardMentionResponse,
)

router = APIRouter()


def get_source_display(source: str) -> str:
    """Extract human-friendly source name from source field."""
    if source.startswith("newsapi:"):
        return source[8:]  # Remove "newsapi:" prefix
    return source.replace("_", " ").title()


@router.get("", response_model=NewsListResponse)
async def list_news(
    db: AsyncSession = Depends(get_db),
    source: str | None = Query(None, description="Filter by source"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List news articles, newest first.
    """
    # Build base query
    query = select(NewsArticle)
    count_query = select(func.count(NewsArticle.id))

    if source:
        query = query.where(NewsArticle.source.ilike(f"%{source}%"))
        count_query = count_query.where(NewsArticle.source.ilike(f"%{source}%"))

    # Get total count
    total = await db.scalar(count_query) or 0

    # Get articles with mention counts
    query = (
        query
        .outerjoin(CardNewsMention, CardNewsMention.article_id == NewsArticle.id)
        .group_by(NewsArticle.id)
        .add_columns(func.count(CardNewsMention.id).label("mention_count"))
        .order_by(desc(NewsArticle.published_at), desc(NewsArticle.id))
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    items = [
        NewsArticleListItem(
            id=article.id,
            title=article.title,
            source=article.source,
            source_display=get_source_display(article.source),
            published_at=article.published_at,
            external_url=article.external_url,
            summary=article.summary[:200] + "..." if article.summary and len(article.summary) > 200 else article.summary,
            card_mention_count=mention_count,
        )
        for article, mention_count in rows
    ]

    return NewsListResponse(
        items=items,
        total=total,
        has_more=offset + limit < total,
    )


@router.get("/sources")
async def list_sources(
    db: AsyncSession = Depends(get_db),
):
    """
    List available news sources with article counts.
    """
    query = (
        select(NewsArticle.source, func.count(NewsArticle.id).label("count"))
        .group_by(NewsArticle.source)
        .order_by(desc("count"))
    )
    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "source": row.source,
            "display": get_source_display(row.source),
            "count": row.count,
        }
        for row in rows
    ]


@router.get("/{article_id}", response_model=NewsArticleDetail)
async def get_news_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single news article with card mentions.
    """
    # Get article with mentions
    query = (
        select(NewsArticle)
        .options(selectinload(NewsArticle.card_mentions).selectinload(CardNewsMention.card))
        .where(NewsArticle.id == article_id)
    )
    result = await db.execute(query)
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    card_mentions = [
        CardMentionResponse(
            card_id=mention.card_id,
            card_name=mention.card.name if mention.card else "Unknown",
            context=mention.context,
        )
        for mention in article.card_mentions
    ]

    return NewsArticleDetail(
        id=article.id,
        title=article.title,
        source=article.source,
        source_display=get_source_display(article.source),
        published_at=article.published_at,
        external_url=article.external_url,
        summary=article.summary,
        author=article.author,
        category=article.category,
        card_mentions=card_mentions,
    )
