"""
Cardmarket (MKM) marketplace adapter.

Primary marketplace for European MTG market.
"""
import asyncio
from datetime import datetime
from typing import Any

import httpx
import structlog

from app.core.config import settings
from app.services.ingestion.base import (
    AdapterConfig,
    CardListing,
    CardPrice,
    MarketplaceAdapter,
)

logger = structlog.get_logger()


class CardMarketAdapter(MarketplaceAdapter):
    """
    Adapter for Cardmarket (MKM) marketplace.
    
    Uses Cardmarket's API when credentials are available.
    Primary source for European market prices.
    """
    
    def __init__(self, config: AdapterConfig | None = None):
        if config is None:
            config = AdapterConfig(
                base_url="https://www.cardmarket.com",
                api_url="https://api.cardmarket.com/ws/v2.0",
                rate_limit_seconds=settings.scraper_rate_limit_seconds,
                extra={
                    "app_token": settings.cardmarket_app_token,
                    "app_secret": settings.cardmarket_app_secret,
                    "access_token": settings.cardmarket_access_token,
                    "access_secret": settings.cardmarket_access_secret,
                },
            )
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
    
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
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                headers={"User-Agent": self.config.user_agent},
            )
        return self._client
    
    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        if self._last_request_time is not None:
            elapsed = (datetime.utcnow() - self._last_request_time).total_seconds()
            if elapsed < self.config.rate_limit_seconds:
                await asyncio.sleep(self.config.rate_limit_seconds - elapsed)
        self._last_request_time = datetime.utcnow()
    
    def _has_api_credentials(self) -> bool:
        """Check if API credentials are configured."""
        extra = self.config.extra
        return bool(
            extra.get("app_token") and
            extra.get("app_secret") and
            extra.get("access_token") and
            extra.get("access_secret")
        )
    
    async def fetch_listings(
        self,
        card_name: str | None = None,
        set_code: str | None = None,
        scryfall_id: str | None = None,
        limit: int = 100,
    ) -> list[CardListing]:
        """
        Fetch listings from Cardmarket.
        
        Requires API credentials for full access.
        """
        await self._rate_limit()
        
        if not card_name:
            return []
        
        if not self._has_api_credentials():
            logger.warning("Cardmarket API credentials not configured")
            return []
        
        # Would implement using Cardmarket API
        # GET /products/find?search=<card_name>&idGame=1
        # GET /articles/<productId>
        logger.info("Cardmarket listing fetch", card_name=card_name, set_code=set_code)
        return []
    
    async def fetch_price(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
    ) -> CardPrice | None:
        """
        Fetch price data from Cardmarket.
        
        Uses Scryfall's price data which includes Cardmarket prices.
        """
        # Cardmarket prices are included in Scryfall data
        logger.info("Cardmarket price fetch - using Scryfall data", card_name=card_name)
        return None
    
    async def search_cards(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search for cards on Cardmarket."""
        await self._rate_limit()
        
        # Would implement search using Cardmarket API
        logger.info("Cardmarket search", query=query)
        return []
    
    async def health_check(self) -> bool:
        """Check if Cardmarket is reachable."""
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

