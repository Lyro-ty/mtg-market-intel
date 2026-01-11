"""
Utility functions for web scraping marketplace listings.
"""
import re
from typing import Any
from urllib.parse import quote, urlencode

import httpx
import structlog
from selectolax.parser import HTMLParser

from app.core.config import settings

logger = structlog.get_logger()


def clean_price(price_str: str) -> float | None:
    """
    Extract numeric price from string.
    
    Examples:
        "$12.50" -> 12.50
        "€15,99" -> 15.99
        "12.50 USD" -> 12.50
    """
    if not price_str:
        return None
    
    # Remove currency symbols and text
    price_str = re.sub(r'[^\d.,]', '', price_str)
    
    # Handle European format (comma as decimal)
    if ',' in price_str and '.' in price_str:
        # Determine which is decimal separator
        if price_str.rindex(',') > price_str.rindex('.'):
            # Comma is decimal (e.g., "1.234,56")
            price_str = price_str.replace('.', '').replace(',', '.')
        else:
            # Dot is decimal (e.g., "1,234.56")
            price_str = price_str.replace(',', '')
    elif ',' in price_str:
        # Might be European format
        if price_str.count(',') == 1:
            # Single comma, likely decimal separator
            price_str = price_str.replace(',', '.')
        else:
            # Multiple commas, likely thousands separator
            price_str = price_str.replace(',', '')
    
    try:
        return float(price_str)
    except (ValueError, AttributeError):
        logger.debug("Failed to parse price", price_str=price_str)
        return None


def extract_text(element: Any, selector: str = None, default: str = "") -> str:
    """Extract text from HTML element."""
    if element is None:
        return default
    
    if selector:
        found = element.css_first(selector)
        if found:
            return found.text(strip=True)
        return default
    
    return element.text(strip=True) if hasattr(element, 'text') else default


def extract_attr(element: Any, attr: str, selector: str = None, default: str = "") -> str:
    """Extract attribute from HTML element."""
    if element is None:
        return default
    
    if selector:
        found = element.css_first(selector)
        if found:
            return found.attributes.get(attr, default)
        return default
    
    if hasattr(element, 'attributes'):
        return element.attributes.get(attr, default)
    
    return default


def build_search_url(
    base_url: str,
    card_name: str,
    set_code: str | None = None,
    params: dict[str, Any] | None = None,
) -> str:
    """Build a search URL for a marketplace."""
    # Note: card_name could be used for building search URLs
    # Currently the base_url is expected to contain the search parameter
    _ = quote(card_name)  # Reserved for future URL building

    # Build query parameters
    query_params = {}
    if params:
        query_params.update(params)
    
    # Construct URL
    if query_params:
        return f"{base_url}?{urlencode(query_params)}"
    return base_url


async def fetch_page(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> HTMLParser | None:
    """
    Fetch and parse an HTML page.

    Returns:
        HTMLParser instance or None if failed.
    """
    # Use centralized timeout setting if not explicitly provided
    if timeout is None:
        timeout = float(settings.external_api_timeout)

    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    if headers:
        default_headers.update(headers)

    try:
        response = await client.get(url, headers=default_headers, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        
        # Parse HTML
        return HTMLParser(response.text)
    except httpx.HTTPStatusError as e:
        logger.warning("HTTP error fetching page", url=url, status=e.response.status_code)
        return None
    except Exception as e:
        logger.error("Failed to fetch page", url=url, error=str(e))
        return None


def find_next_page_url(
    tree: HTMLParser,
    current_url: str,
    next_selectors: list[str] | None = None,
) -> str | None:
    """
    Find the next page URL from pagination elements.
    
    Args:
        tree: Parsed HTML tree.
        current_url: Current page URL.
        next_selectors: List of CSS selectors to try for next page link.
        
    Returns:
        Next page URL or None if not found.
    """
    if next_selectors is None:
        next_selectors = [
            "a[rel='next']",
            ".pagination .next a",
            ".pagination-next",
            "a.next",
            ".next-page",
            "[data-next-page]",
        ]
    
    for selector in next_selectors:
        next_link = tree.css_first(selector)
        if next_link:
            href = next_link.attributes.get("href")
            if href:
                if href.startswith("http"):
                    return href
                # Relative URL
                from urllib.parse import urljoin
                return urljoin(current_url, href)
    
    return None


async def fetch_paginated_listings(
    client: httpx.AsyncClient,
    base_url: str,
    parse_listings_func,
    rate_limit_func,
    limit: int = 100,
    max_pages: int = 10,
    next_selectors: list[str] | None = None,
) -> list:
    """
    Fetch listings from multiple pages with pagination support.
    
    Args:
        client: HTTP client.
        base_url: First page URL.
        parse_listings_func: Function that takes (tree, url) and returns list of listings.
        rate_limit_func: Async function to call for rate limiting.
        limit: Maximum total listings to fetch.
        max_pages: Maximum number of pages to fetch.
        next_selectors: CSS selectors for next page link.
        
    Returns:
        List of all listings from all pages.
    """
    all_listings = []
    current_url = base_url
    pages_fetched = 0
    
    while pages_fetched < max_pages and len(all_listings) < limit:
        await rate_limit_func()
        
        tree = await fetch_page(client, current_url)
        if not tree:
            logger.warning("Failed to fetch page", url=current_url)
            break
        
        # Parse listings from current page
        page_listings = parse_listings_func(tree, current_url)
        all_listings.extend(page_listings)
        
        logger.debug("Fetched page", url=current_url, listings=len(page_listings), total=len(all_listings))
        
        # Check if we have enough listings
        if len(all_listings) >= limit:
            break
        
        # Find next page
        next_url = find_next_page_url(tree, current_url, next_selectors)
        if not next_url or next_url == current_url:
            # No more pages
            break
        
        current_url = next_url
        pages_fetched += 1
    
    return all_listings[:limit]

