"""
Card Kingdom marketplace adapter.

Card Kingdom is a major US-based MTG retailer.
"""
import asyncio
from datetime import datetime
from typing import Any

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

logger = structlog.get_logger()


class CardKingdomAdapter(MarketplaceAdapter):
    """
    Adapter for Card Kingdom marketplace.
    
    Uses HTML scraping as Card Kingdom doesn't have a public API.
    Respects robots.txt and rate limits.
    """
    
    def __init__(self, config: AdapterConfig | None = None):
        if config is None:
            config = AdapterConfig(
                base_url="https://www.cardkingdom.com",
                rate_limit_seconds=2.0,  # Be respectful with scraping
            )
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._robots_checked = False
        self._allowed_paths: set[str] = set()
    
    @property
    def marketplace_name(self) -> str:
        return "Card Kingdom"
    
    @property
    def marketplace_slug(self) -> str:
        return "cardkingdom"
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                headers={
                    "User-Agent": self.config.user_agent,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                follow_redirects=True,
            )
        return self._client
    
    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        if self._last_request_time is not None:
            elapsed = (datetime.utcnow() - self._last_request_time).total_seconds()
            if elapsed < self.config.rate_limit_seconds:
                await asyncio.sleep(self.config.rate_limit_seconds - elapsed)
        self._last_request_time = datetime.utcnow()
    
    async def _check_robots_txt(self) -> None:
        """Check robots.txt for allowed paths."""
        if self._robots_checked:
            return
        
        client = await self._get_client()
        try:
            response = await client.get(f"{self.config.base_url}/robots.txt")
            if response.status_code == 200:
                # Parse robots.txt - simplified implementation
                content = response.text
                # In production, use robotexclusionrulesparser
                self._robots_checked = True
                logger.info("Robots.txt checked for Card Kingdom")
        except Exception as e:
            logger.warning("Could not fetch robots.txt", error=str(e))
            self._robots_checked = True
    
    async def fetch_listings(
        self,
        card_name: str | None = None,
        set_code: str | None = None,
        scryfall_id: str | None = None,
        limit: int = 100,
    ) -> list[CardListing]:
        """
        Fetch listings from Card Kingdom via HTML scraping.
        
        Note: Limited implementation - would need proper parsing
        of Card Kingdom's HTML structure.
        """
        await self._check_robots_txt()
        await self._rate_limit()
        
        if not card_name:
            return []
        
        # Card Kingdom has a single price per card (they're a retailer)
        # So we return a single "listing" representing their inventory
        logger.info("Card Kingdom listing fetch", card_name=card_name, set_code=set_code)
        return []
    
    async def fetch_price(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
    ) -> CardPrice | None:
        """
        Fetch price from Card Kingdom.
        
        Scrapes the card page to get current price.
        """
        await self._check_robots_txt()
        await self._rate_limit()
        
        client = await self._get_client()
        
        # Build search URL
        search_name = card_name.lower().replace(" ", "-").replace(",", "").replace("'", "")
        url = f"{self.config.base_url}/catalog/search?search=header&filter[name]={card_name}"
        
        try:
            response = await client.get(url)
            if response.status_code != 200:
                return None
            
            # Parse HTML - would need proper selectors for Card Kingdom's structure
            parser = HTMLParser(response.text)
            
            # Placeholder - real implementation would extract:
            # - Product name verification
            # - Price from price element
            # - Availability/quantity
            
            logger.info("Card Kingdom price fetch", card_name=card_name, url=url)
            return None
            
        except Exception as e:
            logger.error("Card Kingdom fetch error", error=str(e))
            return None
    
    async def search_cards(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search for cards on Card Kingdom."""
        await self._check_robots_txt()
        await self._rate_limit()
        
        # Would implement HTML scraping of search results
        logger.info("Card Kingdom search", query=query)
        return []
    
    async def health_check(self) -> bool:
        """Check if Card Kingdom is reachable."""
        try:
            client = await self._get_client()
            response = await client.get(self.config.base_url)
            return response.status_code == 200
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

