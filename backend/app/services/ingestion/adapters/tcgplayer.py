"""
TCGPlayer marketplace adapter.

Uses Scryfall's aggregated TCGPlayer price data and web scraping for listings.
"""
import asyncio
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode

import httpx
import structlog
from selectolax.parser import HTMLParser

from app.core.config import settings
from app.services.ingestion.base import (
    AdapterConfig,
    CardListing,
    CardPrice,
    MarketplaceAdapter,
)
from app.services.ingestion.scraper_utils import (
    clean_price,
    extract_text,
    extract_attr,
    fetch_page,
)

logger = structlog.get_logger()


class TCGPlayerAdapter(MarketplaceAdapter):
    """
    Adapter for TCGPlayer marketplace.
    
    Uses Scryfall's aggregated price data and web scraping for individual listings.
    """
    
    def __init__(self, config: AdapterConfig | None = None):
        if config is None:
            config = AdapterConfig(
                base_url="https://www.tcgplayer.com",
                api_url="https://api.scryfall.com",
                rate_limit_seconds=max(settings.scryfall_rate_limit_ms / 1000, 2.0),  # Be respectful
            )
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._scryfall_client: httpx.AsyncClient | None = None
    
    @property
    def marketplace_name(self) -> str:
        return "TCGPlayer"
    
    @property
    def marketplace_slug(self) -> str:
        return "tcgplayer"
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for web scraping."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                follow_redirects=True,
            )
        return self._client
    
    async def _get_scryfall_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for Scryfall API."""
        if self._scryfall_client is None or self._scryfall_client.is_closed:
            self._scryfall_client = httpx.AsyncClient(
                base_url=self.config.api_url or "https://api.scryfall.com",
                timeout=self.config.timeout_seconds,
                headers={"User-Agent": self.config.user_agent},
            )
        return self._scryfall_client
    
    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        if self._last_request_time is not None:
            elapsed = (datetime.utcnow() - self._last_request_time).total_seconds()
            if elapsed < self.config.rate_limit_seconds:
                await asyncio.sleep(self.config.rate_limit_seconds - elapsed)
        self._last_request_time = datetime.utcnow()
    
    async def _request_scryfall(self, endpoint: str, params: dict | None = None) -> dict | None:
        """Make a rate-limited request to Scryfall."""
        await self._rate_limit()
        client = await self._get_scryfall_client()
        
        try:
            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error("Scryfall API error", endpoint=endpoint, status=e.response.status_code)
            return None
        except Exception as e:
            logger.error("Scryfall request failed", endpoint=endpoint, error=str(e))
            return None
    
    async def fetch_listings(
        self,
        card_name: str | None = None,
        set_code: str | None = None,
        scryfall_id: str | None = None,
        limit: int = 100,
    ) -> list[CardListing]:
        """
        Fetch individual listings from TCGPlayer by scraping the website.
        
        TCGPlayer's website structure may change, so this uses flexible selectors.
        """
        if not card_name:
            return []
        
        listings = []
        client = await self._get_client()
        
        try:
            # Build search URL - TCGPlayer search format
            search_query = card_name
            if set_code:
                search_query += f" {set_code}"
            
            # TCGPlayer search URL
            search_url = f"{self.config.base_url}/search/magic/product"
            params = {
                "q": search_query,
                "view": "grid",
            }
            url = f"{search_url}?{urlencode(params)}"
            
            await self._rate_limit()
            tree = await fetch_page(client, url, timeout=self.config.timeout_seconds)
            
            if not tree:
                logger.warning("Failed to fetch TCGPlayer search page", card_name=card_name)
                return []
            
            # Try multiple selector strategies for TCGPlayer's structure
            # TCGPlayer uses various class names, so we'll try common patterns
            listing_selectors = [
                ".product-listing",
                ".listing-item",
                "[data-testid='product-listing']",
                ".product-card",
                ".search-result",
            ]
            
            listing_elements = []
            for selector in listing_selectors:
                elements = tree.css(selector)
                if elements:
                    listing_elements = elements
                    logger.debug("Found listings with selector", selector=selector, count=len(elements))
                    break
            
            # If no specific listing container found, try to find price elements
            if not listing_elements:
                # Look for price elements which are more consistent
                price_elements = tree.css(".price, .product-price, [data-price], .listing-price")
                if price_elements:
                    # Group nearby elements as listings
                    listing_elements = price_elements[:limit]
            
            # If still no listings found, try more generic/alternative selectors
            if not listing_elements:
                # TCGPlayer might use different structures - try common product card patterns
                generic_selectors = [
                    "[data-product-id]",
                    "[data-product]",
                    ".product",
                    ".search-result-item",
                    ".product-tile",
                    "article[class*='product']",
                    "[class*='ProductCard']",
                    "[class*='product-card']",
                    "[class*='listing']",
                    "div[class*='product']",
                ]
                for selector in generic_selectors:
                    elements = tree.css(selector)
                    if elements and len(elements) > 0:
                        listing_elements = elements[:limit]
                        logger.debug("Found elements with generic selector", selector=selector, count=len(elements))
                        break
            
            # Log diagnostic info if no listings found
            if not listing_elements:
                # Get a sample of class names from the page for debugging
                sample_classes = set()
                for el in tree.css("[class]")[:50]:
                    if el.attributes and "class" in el.attributes:
                        classes = el.attributes["class"].split()
                        sample_classes.update(classes[:5])  # Limit to avoid huge logs
                
                logger.warning(
                    "No listing elements found on TCGPlayer page - selectors may need updating",
                    card_name=card_name,
                    url=url,
                    sample_classes=list(sample_classes)[:20],  # First 20 unique classes
                    page_title=tree.css_first("title").text() if tree.css_first("title") else "N/A",
                )
            
            # If still no listings found, try more generic selectors
            if not listing_elements:
                # TCGPlayer might use different structures - try common product card patterns
                generic_selectors = [
                    "[data-product-id]",
                    ".product",
                    ".search-result-item",
                    ".product-tile",
                    "article",
                    "[class*='product']",
                    "[class*='listing']",
                    "[class*='card']",
                ]
                for selector in generic_selectors:
                    elements = tree.css(selector)
                    if elements and len(elements) > 0:
                        listing_elements = elements[:limit]
                        logger.debug("Found elements with generic selector", selector=selector, count=len(elements))
                        break
            
            # Log if no listings found at all
            if not listing_elements:
                # Save a sample of the HTML for debugging (first 2000 chars)
                page_text = tree.text()[:2000] if tree else "No tree"
                logger.warning(
                    "No listing elements found on TCGPlayer page",
                    card_name=card_name,
                    url=url,
                    page_preview=page_text,
                    all_classes=", ".join(set([cls for el in tree.css("[class]")[:20] for cls in (el.attributes.get("class", "").split() if el.attributes else [])])))[:20] if tree else "N/A"
                )
            
            for i, element in enumerate(listing_elements[:limit]):
                try:
                    # Extract price
                    price_text = (
                        extract_text(element, ".price") or
                        extract_text(element, ".product-price") or
                        extract_text(element, "[data-price]") or
                        extract_text(element, ".listing-price") or
                        extract_attr(element, "data-price")
                    )
                    price = clean_price(price_text)
                    
                    if not price or price <= 0:
                        continue
                    
                    # Extract condition
                    condition_text = (
                        extract_text(element, ".condition") or
                        extract_text(element, ".card-condition") or
                        extract_text(element, "[data-condition]") or
                        ""
                    )
                    condition = self.normalize_condition(condition_text) if condition_text else None
                    
                    # Extract quantity
                    qty_text = (
                        extract_text(element, ".quantity") or
                        extract_text(element, "[data-quantity]") or
                        "1"
                    )
                    try:
                        quantity = int(re.sub(r'[^\d]', '', qty_text) or "1")
                    except (ValueError, AttributeError):
                        quantity = 1
                    
                    # Extract seller name
                    seller_name = (
                        extract_text(element, ".seller") or
                        extract_text(element, ".seller-name") or
                        extract_text(element, "[data-seller]") or
                        None
                    )
                    
                    # Extract seller rating
                    rating_text = (
                        extract_text(element, ".rating") or
                        extract_text(element, ".seller-rating") or
                        extract_attr(element, "data-rating") or
                        None
                    )
                    seller_rating = None
                    if rating_text:
                        try:
                            seller_rating = float(re.sub(r'[^\d.]', '', rating_text))
                        except (ValueError, AttributeError):
                            pass
                    
                    # Check for foil
                    is_foil = (
                        "foil" in extract_text(element, "").lower() or
                        element.css_first(".foil, [data-foil='true']") is not None
                    )
                    
                    # Extract listing URL
                    listing_url = (
                        extract_attr(element, "href", "a") or
                        extract_attr(element, "href") or
                        None
                    )
                    if listing_url and not listing_url.startswith("http"):
                        listing_url = f"{self.config.base_url}{listing_url}"
                    
                    # Generate external ID
                    external_id = extract_attr(element, "data-id") or extract_attr(element, "data-listing-id")
                    if not external_id:
                        external_id = f"tcgplayer-{hash(f'{card_name}-{i}')}"
                    
                    listing = CardListing(
                        card_name=card_name,
                        set_code=set_code or "",
                        collector_number="",
                        price=price,
                        currency="USD",
                        quantity=quantity,
                        condition=condition,
                        language="English",
                        is_foil=is_foil,
                        seller_name=seller_name,
                        seller_rating=seller_rating,
                        external_id=external_id,
                        listing_url=listing_url,
                        scraped_at=datetime.utcnow(),
                    )
                    
                    listings.append(listing)
                    
                except Exception as e:
                    logger.debug("Failed to parse listing element", error=str(e), index=i)
                    continue
            
            # Try to fetch additional pages if we haven't reached the limit
            if len(listings) < limit:
                try:
                    # Look for pagination
                    next_url = None
                    next_link = tree.css_first("a[rel='next'], .pagination .next a, a.next")
                    if next_link:
                        href = next_link.attributes.get("href")
                        if href:
                            if not href.startswith("http"):
                                from urllib.parse import urljoin
                                href = urljoin(url, href)
                            next_url = href
                    
                    # Fetch additional pages (up to 5 more pages)
                    pages_fetched = 1
                    max_pages = 5
                    current_url = next_url
                    
                    while current_url and pages_fetched < max_pages and len(listings) < limit:
                        await self._rate_limit()
                        next_tree = await fetch_page(client, current_url, timeout=self.config.timeout_seconds)
                        
                        if not next_tree:
                            break
                        
                        # Parse listings from this page
                        next_listing_elements = []
                        for selector in listing_selectors:
                            elements = next_tree.css(selector)
                            if elements:
                                next_listing_elements = elements
                                break
                        
                        if not next_listing_elements:
                            price_elements = next_tree.css(".price, .product-price, [data-price], .listing-price")
                            if price_elements:
                                next_listing_elements = price_elements[:limit - len(listings)]
                        
                        # Parse listings from this page (reuse parsing logic)
                        for i, element in enumerate(next_listing_elements[:limit - len(listings)]):
                            try:
                                price_text = (
                                    extract_text(element, ".price") or
                                    extract_text(element, ".product-price") or
                                    extract_text(element, "[data-price]") or
                                    extract_text(element, ".listing-price") or
                                    extract_attr(element, "data-price")
                                )
                                price = clean_price(price_text)
                                
                                if not price or price <= 0:
                                    continue
                                
                                condition_text = (
                                    extract_text(element, ".condition") or
                                    extract_text(element, ".card-condition") or
                                    extract_text(element, "[data-condition]") or
                                    ""
                                )
                                condition = self.normalize_condition(condition_text) if condition_text else None
                                
                                qty_text = (
                                    extract_text(element, ".quantity") or
                                    extract_text(element, "[data-quantity]") or
                                    "1"
                                )
                                try:
                                    quantity = int(re.sub(r'[^\d]', '', qty_text) or "1")
                                except (ValueError, AttributeError):
                                    quantity = 1
                                
                                seller_name = (
                                    extract_text(element, ".seller") or
                                    extract_text(element, ".seller-name") or
                                    extract_text(element, "[data-seller]") or
                                    None
                                )
                                
                                rating_text = (
                                    extract_text(element, ".rating") or
                                    extract_text(element, ".seller-rating") or
                                    extract_attr(element, "data-rating") or
                                    None
                                )
                                seller_rating = None
                                if rating_text:
                                    try:
                                        seller_rating = float(re.sub(r'[^\d.]', '', rating_text))
                                    except (ValueError, AttributeError):
                                        pass
                                
                                is_foil = (
                                    "foil" in extract_text(element, "").lower() or
                                    element.css_first(".foil, [data-foil='true']") is not None
                                )
                                
                                listing_url = (
                                    extract_attr(element, "href", "a") or
                                    extract_attr(element, "href") or
                                    None
                                )
                                if listing_url and not listing_url.startswith("http"):
                                    listing_url = f"{self.config.base_url}{listing_url}"
                                
                                external_id = extract_attr(element, "data-id") or extract_attr(element, "data-listing-id")
                                if not external_id:
                                    external_id = f"tcgplayer-{hash(f'{card_name}-{len(listings) + i}')}"
                                
                                listing = CardListing(
                                    card_name=card_name,
                                    set_code=set_code or "",
                                    collector_number="",
                                    price=price,
                                    currency="USD",
                                    quantity=quantity,
                                    condition=condition,
                                    language="English",
                                    is_foil=is_foil,
                                    seller_name=seller_name,
                                    seller_rating=seller_rating,
                                    external_id=external_id,
                                    listing_url=listing_url,
                                    scraped_at=datetime.utcnow(),
                                )
                                
                                listings.append(listing)
                                
                            except Exception as e:
                                logger.debug("Failed to parse listing element", error=str(e))
                                continue
                        
                        # Find next page
                        next_link = next_tree.css_first("a[rel='next'], .pagination .next a, a.next")
                        if next_link:
                            href = next_link.attributes.get("href")
                            if href:
                                if not href.startswith("http"):
                                    from urllib.parse import urljoin
                                    href = urljoin(current_url, href)
                                current_url = href
                            else:
                                current_url = None
                        else:
                            current_url = None
                        
                        pages_fetched += 1
                        
                except Exception as e:
                    logger.debug("Error fetching additional pages", error=str(e))
            
            logger.info("Scraped TCGPlayer listings", card_name=card_name, count=len(listings), pages=pages_fetched if 'pages_fetched' in locals() else 1)
            
        except Exception as e:
            logger.error("Error scraping TCGPlayer listings", card_name=card_name, error=str(e))
        
        return listings[:limit]
    
    async def fetch_price(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
    ) -> CardPrice | None:
        """
        Fetch TCGPlayer price data via Scryfall.
        
        Scryfall aggregates TCGPlayer prices (usd, usd_foil fields).
        """
        data = None
        
        # Try to fetch by Scryfall ID first (most reliable)
        if scryfall_id:
            data = await self._request_scryfall(f"/cards/{scryfall_id}")
        
        # Try by set and collector number
        if not data and set_code and collector_number:
            data = await self._request_scryfall(f"/cards/{set_code.lower()}/{collector_number}")
        
        # Search by name and set
        if not data:
            query = f'!"{card_name}"'
            if set_code:
                query += f" set:{set_code.lower()}"
            
            search_data = await self._request_scryfall("/cards/search", params={"q": query})
            if search_data and search_data.get("data"):
                data = search_data["data"][0]
        
        if not data:
            return None
        
        prices = data.get("prices", {})
        price_usd = prices.get("usd")
        price_foil = prices.get("usd_foil")
        
        # Skip if no USD price
        if not price_usd:
            logger.debug("No TCGPlayer price", card_name=card_name, set_code=set_code)
            return None
        
        return CardPrice(
            card_name=data.get("name", card_name),
            set_code=data.get("set", set_code).upper() if data.get("set") else set_code,
            collector_number=data.get("collector_number", collector_number),
            scryfall_id=data.get("id", scryfall_id),
            price=float(price_usd),
            currency="USD",
            price_foil=float(price_foil) if price_foil else None,
            snapshot_time=datetime.utcnow(),
        )
    
    async def search_cards(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search for cards via Scryfall."""
        data = await self._request_scryfall("/cards/search", params={"q": query})
        if not data or not data.get("data"):
            return []
        
        return data["data"][:limit]
    
    async def health_check(self) -> bool:
        """Check if Scryfall (data source) is reachable."""
        try:
            data = await self._request_scryfall("/cards/random")
            return data is not None
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close the HTTP clients."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        if self._scryfall_client and not self._scryfall_client.is_closed:
            await self._scryfall_client.aclose()
