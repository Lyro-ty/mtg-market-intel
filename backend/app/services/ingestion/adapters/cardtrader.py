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
        
        Process:
        1. Query CardTrader expansions API to find the set
        2. Search for the card within that expansion's blueprints
        3. Match by name and collector_number
        4. Return the blueprint_id
        """
        await self._rate_limit()
        client = await self._get_client()
        
        try:
            # Step 1: Find expansion by set code
            # CardTrader uses different set codes, try exact match first, then partial
            response = await client.get("/expansions")
            response.raise_for_status()
            expansions_data = response.json()
            
            # Handle different response formats
            if isinstance(expansions_data, dict) and "data" in expansions_data:
                expansions = expansions_data["data"]
            elif isinstance(expansions_data, list):
                expansions = expansions_data
            else:
                expansions = []
            
            # Find matching expansion
            expansion_id = None
            set_code_upper = set_code.upper()
            
            for expansion in expansions:
                # Check various fields that might contain set code
                exp_code = None
                if isinstance(expansion, dict):
                    exp_code = expansion.get("code") or expansion.get("code_short") or expansion.get("set_code")
                    if not exp_code and "name" in expansion:
                        # Sometimes set code is in the name
                        name = expansion.get("name", "").upper()
                        if set_code_upper in name:
                            expansion_id = expansion.get("id")
                            break
                
                if exp_code and exp_code.upper() == set_code_upper:
                    expansion_id = expansion.get("id")
                    break
            
            if not expansion_id:
                logger.debug(
                    "Expansion not found in CardTrader",
                    set_code=set_code,
                    card_name=card_name,
                    expansions_checked=len(expansions)
                )
                return None
            
            # Step 2: Get blueprints for this expansion (with pagination support)
            blueprints = []
            page = 1
            limit = 1000
            max_pages = 10  # Safety limit to avoid infinite loops
            
            while page <= max_pages:
                await self._rate_limit()
                response = await client.get(
                    "/blueprints",
                    params={"expansion_id": expansion_id, "limit": limit, "page": page}
                )
                response.raise_for_status()
                blueprints_data = response.json()
                
                # Handle different response formats
                page_blueprints = []
                if isinstance(blueprints_data, dict):
                    if "data" in blueprints_data:
                        page_blueprints = blueprints_data["data"]
                    elif "blueprints" in blueprints_data:
                        page_blueprints = blueprints_data["blueprints"]
                elif isinstance(blueprints_data, list):
                    page_blueprints = blueprints_data
                
                if not page_blueprints:
                    break  # No more results
                
                blueprints.extend(page_blueprints)
                
                # Check if there are more pages
                if isinstance(blueprints_data, dict):
                    has_more = blueprints_data.get("has_more", False)
                    total = blueprints_data.get("total")
                    if not has_more or (total and len(blueprints) >= total):
                        break
                
                # If we got fewer than limit, we're on the last page
                if len(page_blueprints) < limit:
                    break
                
                page += 1
            
            # Step 3: Match card by name and collector number
            card_name_normalized = card_name.upper().strip()
            
            for blueprint in blueprints:
                if not isinstance(blueprint, dict):
                    continue
                
                # Match by name
                blueprint_name = blueprint.get("name") or blueprint.get("card_name")
                if not blueprint_name:
                    continue
                
                blueprint_name_normalized = blueprint_name.upper().strip()
                
                # Exact name match
                if blueprint_name_normalized == card_name_normalized:
                    # If collector number provided, try to match it
                    if collector_number:
                        blueprint_collector = str(blueprint.get("number") or blueprint.get("collector_number") or "")
                        if blueprint_collector and blueprint_collector != str(collector_number):
                            continue  # Name matches but collector number doesn't
                    
                    blueprint_id = blueprint.get("id")
                    if blueprint_id:
                        logger.debug(
                            "Found CardTrader blueprint",
                            blueprint_id=blueprint_id,
                            card_name=card_name,
                            set_code=set_code
                        )
                        return int(blueprint_id)
                
                # Partial name match (in case of slight variations)
                elif card_name_normalized in blueprint_name_normalized or blueprint_name_normalized in card_name_normalized:
                    # Only use partial match if collector number matches
                    if collector_number:
                        blueprint_collector = str(blueprint.get("number") or blueprint.get("collector_number") or "")
                        if blueprint_collector == str(collector_number):
                            blueprint_id = blueprint.get("id")
                            if blueprint_id:
                                logger.debug(
                                    "Found CardTrader blueprint (partial name match)",
                                    blueprint_id=blueprint_id,
                                    card_name=card_name,
                                    set_code=set_code
                                )
                                return int(blueprint_id)
            
            logger.debug(
                "Blueprint not found",
                card_name=card_name,
                set_code=set_code,
                collector_number=collector_number,
                expansion_id=expansion_id,
                blueprints_checked=len(blueprints)
            )
            return None
            
        except httpx.HTTPStatusError as e:
            logger.warning(
                "CardTrader API error in blueprint lookup",
                status=e.response.status_code,
                card_name=card_name,
                set_code=set_code
            )
            return None
        except Exception as e:
            logger.error(
                "Error finding CardTrader blueprint",
                card_name=card_name,
                set_code=set_code,
                error=str(e)
            )
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

