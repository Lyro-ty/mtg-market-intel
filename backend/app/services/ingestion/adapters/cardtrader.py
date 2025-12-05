"""
CardTrader API adapter for marketplace price data.

CardTrader provides European market data (EUR) with marketplace listings.
API Documentation: https://www.cardtrader.com/docs/api/full/reference
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


class CardTraderAdapter(MarketplaceAdapter):
    """
    Adapter for CardTrader marketplace API.
    
    Provides current marketplace prices and listings for European market (EUR).
    Rate limit: 200 requests per 10 seconds.
    """
    
    BASE_URL = "https://api.cardtrader.com/api/v2"
    RATE_LIMIT_REQUESTS = 200
    RATE_LIMIT_WINDOW = 10  # seconds
    
    def __init__(self, config: AdapterConfig | None = None):
        # Get API token from settings (JWT token for Full API access)
        api_token = settings.cardtrader_api_token
        
        if config is None:
            config = AdapterConfig(
                base_url=self.BASE_URL,
                api_url=self.BASE_URL,
                api_key=api_token,
                rate_limit_seconds=self.RATE_LIMIT_WINDOW / self.RATE_LIMIT_REQUESTS,  # ~0.05s between requests
                timeout_seconds=30.0,
            )
        super().__init__(config)
        
        # Ensure token is set
        if not self.config.api_key:
            logger.warning("CardTrader API token not configured - adapter will not be able to fetch data")
        self._client: httpx.AsyncClient | None = None
        self._request_count = 0
        self._window_start = datetime.utcnow()
    
    @property
    def marketplace_name(self) -> str:
        return "CardTrader"
    
    @property
    def marketplace_slug(self) -> str:
        return "cardtrader"
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {"User-Agent": self.config.user_agent}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=httpx.Timeout(self.config.timeout_seconds),
                headers=headers,
                follow_redirects=True,
            )
        return self._client
    
    async def _rate_limit(self) -> None:
        """Enforce rate limiting (200 requests per 10 seconds)."""
        now = datetime.utcnow()
        elapsed = (now - self._window_start).total_seconds()
        
        # Reset window if 10 seconds have passed
        if elapsed >= self.RATE_LIMIT_WINDOW:
            self._request_count = 0
            self._window_start = now
            elapsed = 0
        
        # If we've hit the limit, wait until window resets
        if self._request_count >= self.RATE_LIMIT_REQUESTS:
            wait_time = self.RATE_LIMIT_WINDOW - elapsed
            if wait_time > 0:
                logger.debug("CardTrader rate limit reached, waiting", wait_seconds=wait_time)
                await asyncio.sleep(wait_time)
                self._request_count = 0
                self._window_start = datetime.utcnow()
        
        self._request_count += 1
        
        # Also enforce per-request rate limit
        if self._last_request_time is not None:
            elapsed_since_last = (now - self._last_request_time).total_seconds()
            if elapsed_since_last < self.config.rate_limit_seconds:
                await asyncio.sleep(self.config.rate_limit_seconds - elapsed_since_last)
        
        self._last_request_time = datetime.utcnow()
    
    async def _find_blueprint(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
    ) -> int | None:
        """
        Find CardTrader blueprint ID for a card.
        
        This is a simplified implementation. A full implementation would:
        1. Query CardTrader expansions API to find the set
        2. Search for the card within that expansion
        3. Return the blueprint_id
        
        For now, returns None - blueprint mapping should be done separately.
        
        TODO: Implement full blueprint mapping system:
        - Create CardTraderBlueprint model to cache mappings
        - Query /expansions to find expansion by set_code
        - Query /blueprints?expansion_id=X to find card
        - Match by name and collector_number
        - Cache results in database for faster lookups
        """
        logger.debug("Blueprint lookup not yet implemented", card_name=card_name, set_code=set_code)
        return None
    
    async def _get_marketplace_products(self, blueprint_id: int) -> list[dict[str, Any]]:
        """Get marketplace products for a blueprint."""
        await self._rate_limit()
        client = await self._get_client()
        
        try:
            response = await client.get(
                "/marketplace/products",
                params={"blueprint_id": blueprint_id, "limit": 100}
            )
            response.raise_for_status()
            data = response.json()
            
            # CardTrader API returns data in different formats
            # Check if it's a list or dict with 'data' key
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "data" in data:
                return data["data"]
            elif isinstance(data, dict) and "products" in data:
                return data["products"]
            else:
                return []
                
        except httpx.HTTPStatusError as e:
            logger.warning(
                "CardTrader API error",
                status=e.response.status_code,
                blueprint_id=blueprint_id
            )
            return []
        except Exception as e:
            logger.error("CardTrader API error", blueprint_id=blueprint_id, error=str(e))
            return []
    
    async def fetch_listings(
        self,
        card_name: str | None = None,
        set_code: str | None = None,
        scryfall_id: str | None = None,
        limit: int = 100,
    ) -> list[CardListing]:
        """
        Fetch current listings from CardTrader marketplace.
        
        Note: Requires blueprint_id lookup first, which is not yet fully implemented.
        """
        # For now, return empty list - requires blueprint mapping
        logger.debug("CardTrader listings fetch requires blueprint mapping", card_name=card_name)
        return []
    
    async def fetch_price(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
    ) -> CardPrice | None:
        """
        Fetch current marketplace prices from CardTrader.
        
        Args:
            card_name: Card name
            set_code: Set code
            collector_number: Collector number
            scryfall_id: Scryfall ID (optional, for matching)
            
        Returns:
            CardPrice object or None if not found
        """
        # Find blueprint ID
        blueprint_id = await self._find_blueprint(card_name, set_code, collector_number)
        if not blueprint_id:
            return None
        
        # Get marketplace products
        products = await self._get_marketplace_products(blueprint_id)
        if not products:
            return None
        
        # Calculate prices from listings
        prices = []
        for product in products:
            # CardTrader product structure varies, check common fields
            price_data = None
            
            # Check for seller_price (most common)
            if "seller_price" in product and product["seller_price"]:
                price_info = product["seller_price"]
                if isinstance(price_info, dict):
                    price_cents = price_info.get("cents", 0)
                    currency = price_info.get("currency", "EUR")
                    price = price_cents / 100.0
                    prices.append({"price": price, "currency": currency})
            
            # Alternative: check for price field directly
            elif "price" in product:
                price_val = product["price"]
                if isinstance(price_val, (int, float)):
                    currency = product.get("currency", "EUR")
                    prices.append({"price": float(price_val), "currency": currency})
        
        if not prices:
            return None
        
        # Calculate aggregate prices
        price_values = [p["price"] for p in prices]
        avg_price = sum(price_values) / len(price_values)
        min_price = min(price_values)
        max_price = max(price_values)
        
        # Get foil price if available
        foil_prices = []
        for product in products:
            if product.get("mtg_foil", False):
                if "seller_price" in product and product["seller_price"]:
                    price_info = product["seller_price"]
                    if isinstance(price_info, dict):
                        price_cents = price_info.get("cents", 0)
                        foil_prices.append(price_cents / 100.0)
        
        price_foil = sum(foil_prices) / len(foil_prices) if foil_prices else None
        
        return CardPrice(
            card_name=card_name,
            set_code=set_code,
            collector_number=collector_number or "",
            scryfall_id=scryfall_id,
            price=avg_price,
            currency=prices[0]["currency"],  # Usually EUR
            price_low=min_price,
            price_high=max_price,
            price_foil=price_foil,
            num_listings=len(products),
            snapshot_time=datetime.utcnow(),
        )
    
    async def search_cards(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Search for cards by name/query.
        
        Note: CardTrader API doesn't have a direct search endpoint.
        This would require blueprint lookup first.
        """
        logger.debug("CardTrader card search requires blueprint mapping", query=query)
        return []
    
    async def close(self) -> None:
        """Cleanup HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

