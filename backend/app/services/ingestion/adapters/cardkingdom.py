"""
Card Kingdom marketplace adapter.

Uses Scryfall's aggregated Card Kingdom price data and web scraping for listings.
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


class CardKingdomAdapter(MarketplaceAdapter):
    """
    Adapter for Card Kingdom marketplace.
    
    Uses Scryfall's aggregated price data and web scraping for individual listings.
    """
    
    def __init__(self, config: AdapterConfig | None = None):
        if config is None:
            config = AdapterConfig(
                base_url="https://www.cardkingdom.com",
                api_url="https://api.scryfall.com",
                rate_limit_seconds=max(settings.scryfall_rate_limit_ms / 1000, 2.0),
            )
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._scryfall_client: httpx.AsyncClient | None = None
        # Card Kingdom typically prices 10-20% higher than TCGPlayer market
        self._markup_factor = 1.15
    
    @property
    def marketplace_name(self) -> str:
        return "Card Kingdom"
    
    @property
    def marketplace_slug(self) -> str:
        return "cardkingdom"
    
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
        Fetch individual listings from Card Kingdom by scraping the website.
        """
        if not card_name:
            return []
        
        listings = []
        client = await self._get_client()
        
        try:
            # Build search URL - Card Kingdom search format
            search_query = card_name
            if set_code:
                search_query += f" {set_code}"
            
            # Card Kingdom search URL
            search_url = f"{self.config.base_url}/mtg/search"
            params = {
                "search": search_query,
            }
            url = f"{search_url}?{urlencode(params)}"
            
            await self._rate_limit()
            tree = await fetch_page(client, url, timeout=self.config.timeout_seconds)
            
            if not tree:
                logger.warning("Failed to fetch Card Kingdom search page", card_name=card_name)
                return []
            
            # Card Kingdom uses specific class names for listings
            listing_selectors = [
                ".productItemWrapper",
                ".product-item",
                ".listing-item",
                "[data-product-id]",
                ".product-card",
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
            
            for i, element in enumerate(listing_elements[:limit]):
                try:
                    # Extract price
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
                    
                    # Card Kingdom is a single seller, so seller name is consistent
                    seller_name = "Card Kingdom"
                    
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
                        f"ck-{hash(f'{card_name}-{i}')}"
                    )
                    
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
                        seller_rating=5.0,  # Card Kingdom is highly rated
                        external_id=external_id,
                        listing_url=listing_url,
                        scraped_at=datetime.utcnow(),
                    )
                    
                    listings.append(listing)
                    
                except Exception as e:
                    logger.debug("Failed to parse listing element", error=str(e), index=i)
                    continue
            
            logger.info("Scraped Card Kingdom listings", card_name=card_name, count=len(listings))
            
        except Exception as e:
            logger.error("Error scraping Card Kingdom listings", card_name=card_name, error=str(e))
        
        return listings[:limit]
    
    async def fetch_price(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
    ) -> CardPrice | None:
        """
        Fetch Card Kingdom price data via Scryfall.
        
        Scryfall doesn't directly provide CK prices, but we estimate
        based on TCGPlayer prices with typical CK markup.
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
            logger.debug("No base price for CK estimate", card_name=card_name, set_code=set_code)
            return None
        
        # Apply Card Kingdom markup estimate
        ck_price = float(price_usd) * self._markup_factor
        ck_foil = float(price_foil) * self._markup_factor if price_foil else None
        
        return CardPrice(
            card_name=data.get("name", card_name),
            set_code=data.get("set", set_code).upper() if data.get("set") else set_code,
            collector_number=data.get("collector_number", collector_number),
            scryfall_id=data.get("id", scryfall_id),
            price=round(ck_price, 2),
            currency="USD",
            price_foil=round(ck_foil, 2) if ck_foil else None,
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
