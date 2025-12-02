"""
Cardmarket (MKM) marketplace adapter.

Uses Scryfall's aggregated Cardmarket price data and web scraping for listings.
Primary marketplace for European MTG market.
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


class CardMarketAdapter(MarketplaceAdapter):
    """
    Adapter for Cardmarket (MKM) marketplace.
    
    Uses Scryfall's aggregated price data and web scraping for individual listings.
    Primary source for European market prices.
    """
    
    def __init__(self, config: AdapterConfig | None = None):
        if config is None:
            config = AdapterConfig(
                base_url="https://www.cardmarket.com",
                api_url="https://api.scryfall.com",
                rate_limit_seconds=max(settings.scryfall_rate_limit_ms / 1000, 2.0),
            )
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._scryfall_client: httpx.AsyncClient | None = None
    
    @property
    def marketplace_name(self) -> str:
        return "Cardmarket"
    
    @property
    def marketplace_slug(self) -> str:
        return "cardmarket"
    
    @property
    def default_currency(self) -> str:
        return "EUR"
    
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
        Fetch individual listings from Cardmarket by scraping the website.
        """
        if not card_name:
            return []
        
        listings = []
        client = await self._get_client()
        
        try:
            # Build search URL - Cardmarket search format
            search_query = card_name
            if set_code:
                search_query += f" {set_code}"
            
            # Cardmarket search URL
            search_url = f"{self.config.base_url}/en/Magic/Products/Search"
            params = {
                "searchString": search_query,
            }
            url = f"{search_url}?{urlencode(params)}"
            
            await self._rate_limit()
            tree = await fetch_page(client, url, timeout=self.config.timeout_seconds)
            
            if not tree:
                logger.warning("Failed to fetch Cardmarket search page", card_name=card_name)
                return []
            
            # Cardmarket uses specific class names for listings
            listing_selectors = [
                ".article-row",
                ".product-row",
                "[data-product-id]",
                ".article-item",
                ".listing-item",
            ]
            
            listing_elements = []
            for selector in listing_selectors:
                elements = tree.css(selector)
                if elements:
                    listing_elements = elements
                    logger.debug("Found listings with selector", selector=selector, count=len(elements))
                    break
            
            # If no specific listing container found, try price elements
            if not listing_elements:
                price_elements = tree.css(".price, .product-price, [data-price]")
                if price_elements:
                    listing_elements = price_elements[:limit]
            
            # If still no listings found, try more generic/alternative selectors
            if not listing_elements:
                generic_selectors = [
                    "[data-product-id]",
                    "[data-product]",
                    ".product",
                    ".search-result-item",
                    ".product-tile",
                    "article[class*='product']",
                    "[class*='ProductCard']",
                    "[class*='product-card']",
                    "div[class*='product']",
                    "[class*='Article']",  # Cardmarket uses Article elements
                ]
                for selector in generic_selectors:
                    elements = tree.css(selector)
                    if elements and len(elements) > 0:
                        listing_elements = elements[:limit]
                        logger.debug("Found elements with generic selector", selector=selector, count=len(elements))
                        break
            
            # Log diagnostic info if no listings found
            if not listing_elements:
                sample_classes = set()
                for el in tree.css("[class]")[:50]:
                    if el.attributes and "class" in el.attributes:
                        classes = el.attributes["class"].split()
                        sample_classes.update(classes[:5])
                
                logger.warning(
                    "No listing elements found on Cardmarket page - selectors may need updating",
                    card_name=card_name,
                    url=url,
                    sample_classes=list(sample_classes)[:20],
                    page_title=tree.css_first("title").text() if tree.css_first("title") else "N/A",
                )
            
            for i, element in enumerate(listing_elements[:limit]):
                try:
                    # Extract price (Cardmarket uses EUR)
                    price_text = (
                        extract_text(element, ".price") or
                        extract_text(element, ".product-price") or
                        extract_text(element, "[data-price]") or
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
                    
                    # Extract language
                    language_text = (
                        extract_text(element, ".language") or
                        extract_text(element, "[data-language]") or
                        "English"
                    )
                    language = self.normalize_language(language_text) if language_text else "English"
                    
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
                    external_id = (
                        extract_attr(element, "data-product-id") or
                        extract_attr(element, "data-id") or
                        f"mkm-{hash(f'{card_name}-{i}')}"
                    )
                    
                    listing = CardListing(
                        card_name=card_name,
                        set_code=set_code or "",
                        collector_number="",
                        price=price,
                        currency="EUR",
                        quantity=quantity,
                        condition=condition,
                        language=language,
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
            
            logger.info("Scraped Cardmarket listings", card_name=card_name, count=len(listings))
            
        except Exception as e:
            logger.error("Error scraping Cardmarket listings", card_name=card_name, error=str(e))
        
        return listings[:limit]
    
    async def fetch_price(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
    ) -> CardPrice | None:
        """
        Fetch Cardmarket price data via Scryfall.
        
        Scryfall aggregates Cardmarket prices (eur, eur_foil fields).
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
        price_eur = prices.get("eur")
        price_foil = prices.get("eur_foil")
        
        # Skip if no EUR price
        if not price_eur:
            logger.debug("No Cardmarket price", card_name=card_name, set_code=set_code)
            return None
        
        return CardPrice(
            card_name=data.get("name", card_name),
            set_code=data.get("set", set_code).upper() if data.get("set") else set_code,
            collector_number=data.get("collector_number", collector_number),
            scryfall_id=data.get("id", scryfall_id),
            price=float(price_eur),
            currency="EUR",
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
