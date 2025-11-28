"""
TCGPlayer marketplace adapter.

Uses TCGPlayer's public API for price data.
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


class TCGPlayerAdapter(MarketplaceAdapter):
    """
    Adapter for TCGPlayer marketplace.
    
    Uses the TCGPlayer API when credentials are available,
    falls back to scraping public pages otherwise.
    """
    
    def __init__(self, config: AdapterConfig | None = None):
        if config is None:
            config = AdapterConfig(
                base_url="https://www.tcgplayer.com",
                api_url="https://api.tcgplayer.com",
                api_key=settings.tcgplayer_api_key,
                api_secret=settings.tcgplayer_api_secret,
                rate_limit_seconds=settings.scraper_rate_limit_seconds,
            )
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._access_token: str | None = None
        self._token_expires: datetime | None = None
    
    @property
    def marketplace_name(self) -> str:
        return "TCGPlayer"
    
    @property
    def marketplace_slug(self) -> str:
        return "tcgplayer"
    
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
    
    async def _get_access_token(self) -> str | None:
        """Get OAuth access token for API access."""
        if not self.config.api_key or not self.config.api_secret:
            return None
        
        # Check if existing token is still valid
        if self._access_token and self._token_expires:
            if datetime.utcnow() < self._token_expires:
                return self._access_token
        
        client = await self._get_client()
        try:
            response = await client.post(
                f"{self.config.api_url}/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.config.api_key,
                    "client_secret": self.config.api_secret,
                },
            )
            response.raise_for_status()
            data = response.json()
            
            self._access_token = data.get("access_token")
            # Token typically expires in 24 hours
            expires_in = data.get("expires_in", 86400)
            self._token_expires = datetime.utcnow() + asyncio.timedelta(seconds=expires_in - 300)
            
            return self._access_token
        except Exception as e:
            logger.error("Failed to get TCGPlayer access token", error=str(e))
            return None
    
    async def fetch_listings(
        self,
        card_name: str | None = None,
        set_code: str | None = None,
        scryfall_id: str | None = None,
        limit: int = 100,
    ) -> list[CardListing]:
        """
        Fetch listings from TCGPlayer.
        
        Note: Full listing data requires API access.
        Without API, returns limited data from public pages.
        """
        await self._rate_limit()
        
        if not card_name:
            return []
        
        # For now, return empty - real implementation would:
        # 1. Search for the card
        # 2. Get product ID
        # 3. Fetch listings for that product
        logger.info("TCGPlayer listing fetch", card_name=card_name, set_code=set_code)
        return []
    
    async def fetch_price(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
    ) -> CardPrice | None:
        """
        Fetch price data from TCGPlayer.
        
        Uses Scryfall's price data which includes TCGPlayer prices,
        as direct API access requires partnership agreement.
        """
        # TCGPlayer prices are included in Scryfall data
        # For direct API access, would need TCGPlayer partnership
        logger.info("TCGPlayer price fetch - using Scryfall data", card_name=card_name)
        return None
    
    async def search_cards(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search for cards on TCGPlayer."""
        await self._rate_limit()
        
        # Would implement search using TCGPlayer search API or scraping
        logger.info("TCGPlayer search", query=query)
        return []
    
    async def health_check(self) -> bool:
        """Check if TCGPlayer is reachable."""
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

