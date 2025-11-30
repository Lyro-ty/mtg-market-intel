"""
Cardmarket (MKM) marketplace adapter.

Uses Scryfall's aggregated Cardmarket price data.
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
    
    Uses Scryfall's aggregated price data which includes Cardmarket EUR prices.
    Primary source for European market prices.
    """
    
    def __init__(self, config: AdapterConfig | None = None):
        if config is None:
            config = AdapterConfig(
                base_url="https://api.scryfall.com",
                rate_limit_seconds=settings.scryfall_rate_limit_ms / 1000,
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
                base_url=self.config.base_url,
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
    
    async def _request(self, endpoint: str, params: dict | None = None) -> dict | None:
        """Make a rate-limited request to Scryfall."""
        await self._rate_limit()
        client = await self._get_client()
        
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
        Cardmarket individual listings require API partnership.
        Returns empty list.
        """
        return []
    
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
            data = await self._request(f"/cards/{scryfall_id}")
        
        # Try by set and collector number
        if not data and set_code and collector_number:
            data = await self._request(f"/cards/{set_code.lower()}/{collector_number}")
        
        # Search by name and set
        if not data:
            query = f'!"{card_name}"'
            if set_code:
                query += f" set:{set_code.lower()}"
            
            search_data = await self._request("/cards/search", params={"q": query})
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
        data = await self._request("/cards/search", params={"q": query})
        if not data or not data.get("data"):
            return []
        
        return data["data"][:limit]
    
    async def health_check(self) -> bool:
        """Check if Scryfall (data source) is reachable."""
        try:
            data = await self._request("/cards/random")
            return data is not None
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
