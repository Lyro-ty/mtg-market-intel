"""
Manapool API adapter for marketplace price data.

Manapool provides marketplace data and listings for MTG cards.
API Documentation: https://manapool.com/api (to be verified)
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


class ManapoolAdapter(MarketplaceAdapter):
    """
    Adapter for Manapool marketplace API.
    
    Provides current marketplace prices and listings.
    Rate limit: TBD (to be configured based on API documentation)
    """
    
    BASE_URL = "https://api.manapool.com"  # To be verified
    RATE_LIMIT_REQUESTS = 10
    RATE_LIMIT_WINDOW = 1  # seconds
    
    def __init__(self, config: AdapterConfig | None = None):
        # Get API token from settings
        api_token = getattr(settings, 'manapool_api_token', None) or ""
        
        if config is None:
            config = AdapterConfig(
                base_url=self.BASE_URL,
                api_url=self.BASE_URL,
                api_key=api_token,
                rate_limit_seconds=self.RATE_LIMIT_WINDOW / self.RATE_LIMIT_REQUESTS,
                timeout_seconds=30.0,
            )
        super().__init__(config)
        
        # Ensure token is set
        if not self.config.api_key:
            logger.warning("Manapool API token not configured - adapter will not be able to fetch data")
        self._client: httpx.AsyncClient | None = None
        self._request_count = 0
        self._window_start = datetime.utcnow()
    
    @property
    def marketplace_name(self) -> str:
        return "Manapool"
    
    @property
    def marketplace_slug(self) -> str:
        return "manapool"
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {"User-Agent": self.config.user_agent}
            if self.config.api_key:
                # Manapool API authentication format (to be verified)
                headers["Authorization"] = f"Bearer {self.config.api_key}"
                # Alternative: headers["X-API-Key"] = self.config.api_key
            
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=httpx.Timeout(self.config.timeout_seconds),
                headers=headers,
                follow_redirects=True,
            )
        return self._client
    
    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        now = datetime.utcnow()
        elapsed = (now - self._window_start).total_seconds()
        
        # Reset window if 1 second has passed
        if elapsed >= self.RATE_LIMIT_WINDOW:
            self._request_count = 0
            self._window_start = now
            elapsed = 0
        
        # If we've hit the limit, wait until window resets
        if self._request_count >= self.RATE_LIMIT_REQUESTS:
            wait_time = self.RATE_LIMIT_WINDOW - elapsed
            if wait_time > 0:
                logger.debug("Manapool rate limit reached, waiting", wait_seconds=wait_time)
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
    
    async def fetch_listings(
        self,
        card_name: str | None = None,
        set_code: str | None = None,
        scryfall_id: str | None = None,
        limit: int = 100,
    ) -> list[CardListing]:
        """
        Fetch current listings from Manapool marketplace.
        
        Args:
            card_name: Card name (required)
            set_code: Set code (required)
            scryfall_id: Scryfall ID (optional, for matching)
            limit: Maximum number of listings to return (default: 100)
            
        Returns:
            List of CardListing objects
        """
        if not card_name or not set_code:
            logger.warning("Manapool fetch_listings requires card_name and set_code")
            return []
        
        await self._rate_limit()
        client = await self._get_client()
        
        try:
            # TODO: Implement actual Manapool API call once API documentation is available
            # This is a placeholder structure
            # Example endpoint: GET /listings?card_name={name}&set={set_code}
            
            params = {
                "card_name": card_name,
                "set": set_code,
                "limit": limit,
            }
            
            response = await client.get("/listings", params=params)
            response.raise_for_status()
            data = response.json()
            
            # Parse response (structure to be determined from API docs)
            listings = []
            # Handle different response formats
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict) and "data" in data:
                items = data["data"]
            elif isinstance(data, dict) and "listings" in data:
                items = data["listings"]
            else:
                items = []
            
            for item in items[:limit]:
                try:
                    # Extract price
                    price = float(item.get("price", 0))
                    if price <= 0:
                        continue
                    
                    # Extract condition
                    condition = self.normalize_condition(item.get("condition", "NM"))
                    
                    # Extract language
                    language = self.normalize_language(item.get("language", "English"))
                    
                    # Extract foil status
                    is_foil = item.get("foil", False) or item.get("is_foil", False)
                    
                    # Extract quantity
                    quantity = item.get("quantity", 1)
                    if not isinstance(quantity, int):
                        try:
                            quantity = int(quantity)
                        except (ValueError, TypeError):
                            quantity = 1
                    
                    # Extract seller info
                    seller_name = item.get("seller") or item.get("seller_name")
                    seller_rating = item.get("seller_rating") or item.get("rating")
                    
                    # Extract external ID and URL
                    external_id = str(item.get("id", ""))
                    listing_url = item.get("url") or item.get("listing_url")
                    if not listing_url and external_id:
                        listing_url = f"https://manapool.com/listings/{external_id}"
                    
                    listing = CardListing(
                        card_name=card_name,
                        set_code=set_code,
                        collector_number=str(item.get("collector_number", "")),
                        price=price,
                        currency=item.get("currency", "USD"),
                        quantity=quantity,
                        condition=condition,
                        language=language,
                        is_foil=is_foil,
                        seller_name=seller_name,
                        seller_rating=seller_rating,
                        external_id=external_id,
                        listing_url=listing_url,
                        scryfall_id=scryfall_id,
                        raw_data=item,
                    )
                    listings.append(listing)
                    
                except Exception as e:
                    logger.warning(
                        "Error converting Manapool listing",
                        listing_id=item.get("id"),
                        error=str(e)
                    )
                    continue
            
            logger.debug(
                "Manapool listings fetched",
                card_name=card_name,
                set_code=set_code,
                listings_count=len(listings)
            )
            
            return listings
            
        except httpx.HTTPStatusError as e:
            logger.warning(
                "Manapool API error",
                status=e.response.status_code,
                card_name=card_name,
                set_code=set_code
            )
            return []
        except Exception as e:
            logger.error("Manapool API error", card_name=card_name, error=str(e))
            return []
    
    async def fetch_price(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
    ) -> CardPrice | None:
        """
        Fetch current marketplace prices from Manapool.
        
        Args:
            card_name: Card name
            set_code: Set code
            collector_number: Collector number
            scryfall_id: Scryfall ID (optional, for matching)
            
        Returns:
            CardPrice object or None if not found
        """
        await self._rate_limit()
        client = await self._get_client()
        
        try:
            # TODO: Implement actual Manapool API call once API documentation is available
            # Example endpoint: GET /prices?card_name={name}&set={set_code}
            
            params = {
                "card_name": card_name,
                "set": set_code,
            }
            if collector_number:
                params["collector_number"] = collector_number
            
            response = await client.get("/prices", params=params)
            response.raise_for_status()
            data = response.json()
            
            # Parse response (structure to be determined from API docs)
            # Expected format might be:
            # {
            #   "price": 10.50,
            #   "price_low": 9.00,
            #   "price_high": 12.00,
            #   "price_foil": 15.00,
            #   "num_listings": 25,
            #   "currency": "USD"
            # }
            
            price = float(data.get("price", 0))
            if price <= 0:
                return None
            
            return CardPrice(
                card_name=card_name,
                set_code=set_code,
                collector_number=collector_number or "",
                scryfall_id=scryfall_id,
                price=price,
                currency=data.get("currency", "USD"),
                price_low=data.get("price_low"),
                price_high=data.get("price_high"),
                price_foil=data.get("price_foil"),
                num_listings=data.get("num_listings"),
                snapshot_time=datetime.utcnow(),
            )
            
        except httpx.HTTPStatusError as e:
            logger.warning(
                "Manapool API error",
                status=e.response.status_code,
                card_name=card_name,
                set_code=set_code
            )
            return None
        except Exception as e:
            logger.error("Manapool API error", card_name=card_name, error=str(e))
            return None
    
    async def search_cards(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Search for cards by name/query.
        
        Args:
            query: Search query string
            limit: Maximum results to return
            
        Returns:
            List of card info dictionaries
        """
        await self._rate_limit()
        client = await self._get_client()
        
        try:
            # TODO: Implement actual Manapool search API call
            params = {"q": query, "limit": limit}
            response = await client.get("/search", params=params)
            response.raise_for_status()
            data = response.json()
            
            # Parse response
            if isinstance(data, list):
                return data[:limit]
            elif isinstance(data, dict) and "results" in data:
                return data["results"][:limit]
            elif isinstance(data, dict) and "data" in data:
                return data["data"][:limit]
            else:
                return []
                
        except Exception as e:
            logger.error("Manapool search error", query=query, error=str(e))
            return []
    
    async def close(self) -> None:
        """Cleanup HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

