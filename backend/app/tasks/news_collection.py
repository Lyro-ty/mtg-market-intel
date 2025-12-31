"""
News collection task for fetching MTG news from RSS feeds and NewsAPI.ai.

Fetches articles from:
- RSS feeds: Card Kingdom, MTGGoldfish, etc.
- NewsAPI.ai: Real-time MTG news from 30,000+ publishers

Extracts card mentions and links them to the card database.
"""
import re
from datetime import datetime, timezone, timedelta
from typing import Any

import feedparser
import httpx
import structlog
from celery import shared_task
from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.db.session import async_session_maker
from app.models import Card, NewsArticle, CardNewsMention
from app.tasks.utils import run_async

logger = structlog.get_logger()

# Browser-like headers to avoid being blocked
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, application/atom+xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# RSS feed sources - using known working feed URLs
RSS_FEEDS = {
    "mtggoldfish": "https://www.mtggoldfish.com/articles.rss",
    "starcitygames": "https://starcitygames.com/feed/",
    "cardkingdom": "https://blog.cardkingdom.com/feed/",
}

# NewsAPI.ai configuration
NEWSAPI_AI_URL = "https://eventregistry.org/api/v1/article/getArticles"
NEWSAPI_AI_KEYWORDS = [
    "Magic: The Gathering",
    "MTG Commander",
    "MTG Modern",
    "MTG Standard",
    "Wizards of the Coast MTG",
]

# Minimum card name length to avoid false positives like "Go" or "Ow"
MIN_CARD_NAME_LENGTH = 4

# HTTP client timeout
REQUEST_TIMEOUT = 30.0


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

    async with async_session_maker() as db:
        try:
            # Pre-load card names for mention extraction
            card_names = await _load_card_names(db)
            logger.info("Loaded card names for matching", count=len(card_names))

            # Fetch from RSS feeds
            if source is None or source in RSS_FEEDS:
                feeds_to_fetch = {source: RSS_FEEDS[source]} if source else RSS_FEEDS
                for source_name, feed_url in feeds_to_fetch.items():
                    try:
                        source_stats = await _fetch_rss_source(db, source_name, feed_url, card_names)
                        stats["sources_fetched"] += 1
                        stats["articles_created"] += source_stats["articles_created"]
                        stats["articles_skipped"] += source_stats["articles_skipped"]
                        stats["card_mentions_created"] += source_stats["card_mentions_created"]
                    except Exception as e:
                        error_msg = f"Failed to fetch {source_name}: {str(e)}"
                        logger.error(error_msg)
                        stats["errors"].append(error_msg)

            # Fetch from NewsAPI.ai if API key is configured
            if (source is None or source == "newsapi") and settings.newsapi_ai_key:
                try:
                    newsapi_stats = await _fetch_newsapi_ai(db, card_names)
                    stats["sources_fetched"] += 1
                    stats["articles_created"] += newsapi_stats["articles_created"]
                    stats["articles_skipped"] += newsapi_stats["articles_skipped"]
                    stats["card_mentions_created"] += newsapi_stats["card_mentions_created"]
                except Exception as e:
                    error_msg = f"Failed to fetch newsapi.ai: {str(e)}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)
            elif source == "newsapi" and not settings.newsapi_ai_key:
                stats["errors"].append("NewsAPI.ai API key not configured")

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


async def _fetch_rss_source(
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

    # Fetch RSS feed with proper headers using httpx
    try:
        async with httpx.AsyncClient(
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = await client.get(feed_url)
            response.raise_for_status()
            feed_content = response.text
    except httpx.HTTPStatusError as e:
        logger.error("HTTP error fetching feed", source=source_name, status=e.response.status_code)
        return stats
    except httpx.RequestError as e:
        logger.error("Request error fetching feed", source=source_name, error=str(e))
        return stats

    # Parse the fetched content with feedparser
    feed = feedparser.parse(feed_content)

    if feed.bozo:
        logger.warning("Feed parsing had issues", source=source_name, error=str(feed.bozo_exception))

    if not feed.entries:
        logger.warning("No entries found in feed", source=source_name)
        return stats

    logger.info("Found feed entries", source=source_name, count=len(feed.entries))

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


async def _fetch_newsapi_ai(
    db,
    card_names: dict[str, int],
) -> dict[str, int]:
    """
    Fetch MTG news from NewsAPI.ai (Event Registry).

    Uses a single API call with MTG-related keywords to stay within rate limits.
    Free tier: 2000 searches/month, so we fetch once per scheduled run.
    """
    stats = {
        "articles_created": 0,
        "articles_skipped": 0,
        "card_mentions_created": 0,
    }

    logger.info("Fetching from NewsAPI.ai")

    # Build the request payload
    # Search for articles from the last 2 days to avoid duplicates
    date_start = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")

    payload = {
        "apiKey": settings.newsapi_ai_key,
        "keyword": "Magic: The Gathering",  # Primary keyword
        "keywordOper": "or",
        "lang": "eng",  # English only
        "dateStart": date_start,
        "articlesPage": 1,
        "articlesCount": 50,  # Get up to 50 articles per call
        "articlesSortBy": "date",
        "articlesSortByAsc": False,  # Most recent first
        "includeArticleBody": False,  # Save bandwidth, we only need title/summary
        "resultType": "articles",
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                NEWSAPI_AI_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        logger.error("NewsAPI.ai HTTP error", status=e.response.status_code, response=e.response.text[:500])
        return stats
    except httpx.RequestError as e:
        logger.error("NewsAPI.ai request error", error=str(e))
        return stats

    # Extract articles from response
    articles_data = data.get("articles", {}).get("results", [])
    if not articles_data:
        logger.warning("No articles found from NewsAPI.ai")
        return stats

    logger.info("Found NewsAPI.ai articles", count=len(articles_data))

    for article in articles_data:
        try:
            article_stats = await _process_newsapi_article(db, article, card_names)
            if article_stats["created"]:
                stats["articles_created"] += 1
                stats["card_mentions_created"] += article_stats["mentions"]
            else:
                stats["articles_skipped"] += 1
        except Exception as e:
            logger.error("Failed to process NewsAPI article", title=article.get("title", "")[:50], error=str(e))

    logger.debug("NewsAPI.ai fetch complete", **stats)
    return stats


async def _process_newsapi_article(
    db,
    article: dict,
    card_names: dict[str, int],
) -> dict[str, Any]:
    """Process a single NewsAPI.ai article."""
    url = article.get("url", "")
    title = article.get("title", "")
    summary = article.get("body", "") or article.get("summary", "")
    author = ""

    # Get author from authors list
    authors = article.get("authors", [])
    if authors and isinstance(authors, list):
        author = authors[0].get("name", "") if isinstance(authors[0], dict) else str(authors[0])

    # Parse published date
    published_at = None
    date_str = article.get("dateTimePub") or article.get("date")
    if date_str:
        try:
            # NewsAPI.ai uses ISO format
            if "T" in date_str:
                published_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                published_at = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass

    # Get source info
    source_info = article.get("source", {})
    source_name = source_info.get("title", "newsapi") if isinstance(source_info, dict) else "newsapi"

    # Get categories
    category = None
    tags = None
    categories = article.get("categories", [])
    if categories:
        category = categories[0].get("label", "") if isinstance(categories[0], dict) else str(categories[0])
        tag_list = [c.get("label", "") if isinstance(c, dict) else str(c) for c in categories[:5]]
        tags = ",".join(tag_list)

    # Check if article already exists
    if not url:
        return {"created": False, "mentions": 0}

    existing = await db.scalar(
        select(NewsArticle).where(NewsArticle.external_url == url)
    )

    if existing:
        return {"created": False, "mentions": 0}

    # Create article
    news_article = NewsArticle(
        source=f"newsapi:{source_name[:40]}" if source_name != "newsapi" else "newsapi",
        external_url=url[:500],
        external_id=article.get("uri", "")[:255] if article.get("uri") else None,
        title=title[:500] if title else "Untitled",
        summary=summary[:2000] if summary else None,
        author=author[:100] if author else None,
        published_at=published_at,
        category=category[:100] if category else None,
        tags=tags,
    )
    db.add(news_article)
    await db.flush()  # Get the article ID

    # Extract and create card mentions
    mentions_created = await _extract_card_mentions(db, news_article, card_names)

    return {"created": True, "mentions": mentions_created}


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
    category = None
    tags = None
    if entry.get("tags"):
        tag_list = [t.get("term", "") for t in entry.tags if t.get("term")]
        if tag_list:
            category = tag_list[0][:100] if tag_list else None
            tags = ",".join(tag_list)

    # Check if article already exists
    existing = await db.scalar(
        select(NewsArticle).where(NewsArticle.external_url == url)
    )

    if existing:
        return {"created": False, "mentions": 0}

    # Create article
    article = NewsArticle(
        source=source,
        external_url=url,
        title=title[:500] if title else "Untitled",
        summary=summary[:2000] if summary else None,
        author=author[:100] if author else None,
        published_at=published_at,
        category=category,
        tags=tags,
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
                context=context[:500],
                mention_count=1,
            )
            db.add(mention)
            mentioned_cards.add(card_id)
            mentions_created += 1

    return mentions_created
