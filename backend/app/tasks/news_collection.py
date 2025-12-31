"""
News collection task for fetching MTG news from RSS feeds.

Fetches articles from MTGGoldfish, ChannelFireball, and other MTG news sources.
Extracts card mentions and links them to the card database.
"""
import re
from datetime import datetime, timezone
from typing import Any

import feedparser
import structlog
from celery import shared_task
from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert

from app.db.session import async_session_maker
from app.models import Card, NewsArticle, CardNewsMention
from app.tasks.utils import run_async

logger = structlog.get_logger()

# RSS feed sources
RSS_FEEDS = {
    "mtggoldfish": "https://www.mtggoldfish.com/articles.rss",
    "channelfireball": "https://www.channelfireball.com/feed/",
    "tcgplayer": "https://infinite.tcgplayer.com/feed",
}

# Minimum card name length to avoid false positives like "Go" or "Ow"
MIN_CARD_NAME_LENGTH = 4


@shared_task(bind=True, max_retries=3, default_retry_delay=300, name="collect_news")
def collect_news(self, source: str = None) -> dict[str, Any]:
    """
    Collect news articles from RSS feeds.

    Args:
        source: Specific source to fetch (optional, defaults to all)

    Returns:
        Dict with collection statistics
    """
    return run_async(_collect_news_async(source))


async def _collect_news_async(source: str = None) -> dict[str, Any]:
    """Async implementation of news collection."""
    stats = {
        "sources_fetched": 0,
        "articles_created": 0,
        "articles_skipped": 0,
        "card_mentions_created": 0,
        "errors": [],
    }

    feeds_to_fetch = {source: RSS_FEEDS[source]} if source else RSS_FEEDS

    async with async_session_maker() as db:
        try:
            # Pre-load card names for mention extraction
            card_names = await _load_card_names(db)
            logger.info("Loaded card names for matching", count=len(card_names))

            for source_name, feed_url in feeds_to_fetch.items():
                try:
                    source_stats = await _fetch_source(db, source_name, feed_url, card_names)
                    stats["sources_fetched"] += 1
                    stats["articles_created"] += source_stats["articles_created"]
                    stats["articles_skipped"] += source_stats["articles_skipped"]
                    stats["card_mentions_created"] += source_stats["card_mentions_created"]
                except Exception as e:
                    error_msg = f"Failed to fetch {source_name}: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)

            await db.commit()
            logger.info("News collection completed", **stats)

        except Exception as e:
            error_msg = f"News collection failed: {str(e)}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)
            await db.rollback()

    return stats


async def _load_card_names(db) -> dict[str, int]:
    """
    Load card names from database for mention matching.

    Returns dict mapping lowercase card name -> card_id
    """
    query = select(Card.id, Card.name)
    result = await db.execute(query)

    card_names = {}
    for row in result:
        name = row.name.lower()
        # Only include names long enough to avoid false positives
        if len(name) >= MIN_CARD_NAME_LENGTH:
            card_names[name] = row.id

    return card_names


async def _fetch_source(
    db,
    source_name: str,
    feed_url: str,
    card_names: dict[str, int],
) -> dict[str, int]:
    """Fetch and process a single RSS feed."""
    stats = {
        "articles_created": 0,
        "articles_skipped": 0,
        "card_mentions_created": 0,
    }

    logger.info("Fetching RSS feed", source=source_name, url=feed_url)

    # Parse RSS feed
    feed = feedparser.parse(feed_url)

    if feed.bozo:
        logger.warning("Feed parsing had issues", source=source_name, error=str(feed.bozo_exception))

    for entry in feed.entries:
        try:
            article_stats = await _process_entry(db, source_name, entry, card_names)
            if article_stats["created"]:
                stats["articles_created"] += 1
                stats["card_mentions_created"] += article_stats["mentions"]
            else:
                stats["articles_skipped"] += 1
        except Exception as e:
            logger.error("Failed to process entry", source=source_name, title=entry.get("title"), error=str(e))

    logger.debug("Source fetch complete", source=source_name, **stats)
    return stats


async def _process_entry(
    db,
    source: str,
    entry: dict,
    card_names: dict[str, int],
) -> dict[str, Any]:
    """Process a single RSS entry."""
    url = entry.get("link", "")
    title = entry.get("title", "")
    summary = entry.get("summary", "") or entry.get("description", "")
    author = entry.get("author", "")

    # Parse published date
    published_at = None
    if entry.get("published_parsed"):
        try:
            published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass

    # Get categories/tags
    categories = None
    if entry.get("tags"):
        categories = ",".join(t.get("term", "") for t in entry.tags if t.get("term"))

    # Check if article already exists
    existing = await db.scalar(
        select(NewsArticle).where(NewsArticle.url == url)
    )

    if existing:
        return {"created": False, "mentions": 0}

    # Create article
    article = NewsArticle(
        source=source,
        url=url,
        title=title,
        summary=summary[:2000] if summary else None,  # Limit summary length
        author=author[:100] if author else None,
        published_at=published_at,
        fetched_at=datetime.now(timezone.utc),
        categories=categories,
    )
    db.add(article)
    await db.flush()  # Get the article ID

    # Extract and create card mentions
    mentions_created = await _extract_card_mentions(db, article, card_names)

    return {"created": True, "mentions": mentions_created}


async def _extract_card_mentions(
    db,
    article: NewsArticle,
    card_names: dict[str, int],
) -> int:
    """
    Extract card mentions from article title and summary.

    Uses simple substring matching against known card names.
    """
    mentions_created = 0

    # Combine title and summary for searching
    text = f"{article.title} {article.summary or ''}"
    text_lower = text.lower()

    # Track which cards we've already mentioned in this article
    mentioned_cards = set()

    for card_name, card_id in card_names.items():
        if card_id in mentioned_cards:
            continue

        # Look for the card name in the text
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(card_name) + r'\b'
        match = re.search(pattern, text_lower)

        if match:
            # Extract context around the match
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end].strip()

            # Add ellipsis if truncated
            if start > 0:
                context = "..." + context
            if end < len(text):
                context = context + "..."

            mention = CardNewsMention(
                article_id=article.id,
                card_id=card_id,
                mention_context=context[:500],
            )
            db.add(mention)
            mentioned_cards.add(card_id)
            mentions_created += 1

    return mentions_created
