"""
CardTrader API adapter for marketplace price data.

CardTrader provides marketplace data in multiple currencies (USD, EUR) with marketplace listings.
API Documentation: https://www.cardtrader.com/docs/api/full/reference
"""
import asyncio
from datetime import datetime, timezone
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
    
    Provides current marketplace prices and listings for USD and EUR markets.
    Rate limit: 200 requests per 10 seconds (per API documentation).
    """
    
    BASE_URL = "https://api.cardtrader.com/api/v2"
    RATE_LIMIT_REQUESTS = 200
    RATE_LIMIT_WINDOW = 10  # seconds (200 requests per 10 seconds per documentation)
    
    def __init__(self, config: AdapterConfig | None = None):
        # Get API token from settings (JWT token for Full API access)
        api_token = settings.cardtrader_api_token
        
        if config is None:
            config = AdapterConfig(
                base_url=self.BASE_URL,
                api_url=self.BASE_URL,
                api_key=api_token,
                rate_limit_seconds=self.RATE_LIMIT_WINDOW / self.RATE_LIMIT_REQUESTS,  # 0.05s between requests (200 req/10s)
                timeout_seconds=30.0,
            )
        super().__init__(config)
        
        # Ensure token is set
        if not self.config.api_key:
            logger.warning("CardTrader API token not configured - adapter will not be able to fetch data")
        self._client: httpx.AsyncClient | None = None
        self._request_count = 0
        self._window_start = datetime.now(timezone.utc)
        # Cache expansions to avoid fetching on every card lookup
        self._expansions_cache: dict[str, int] | None = None
        self._expansions_cache_time: datetime | None = None
    
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
        """Enforce rate limiting (200 requests per 10 seconds per API documentation)."""
        now = datetime.now(timezone.utc)
        elapsed = (now - self._window_start).total_seconds()

        # Reset window if 10 seconds has passed
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
                self._window_start = datetime.now(timezone.utc)
        
        self._request_count += 1
        
        # Also enforce per-request rate limit (200/10 = 0.05s between requests)
        if self._last_request_time is not None:
            elapsed_since_last = (now - self._last_request_time).total_seconds()
            if elapsed_since_last < self.config.rate_limit_seconds:
                await asyncio.sleep(self.config.rate_limit_seconds - elapsed_since_last)
        
        self._last_request_time = datetime.now(timezone.utc)
    
    async def _get_expansions_cached(self) -> list[dict[str, Any]]:
        """
        Get expansions list with caching.
        
        Cache expires after 1 hour to avoid excessive API calls.
        Per CardTrader API documentation: GET /expansions returns array of Expansion objects.
        """
        now = datetime.now(timezone.utc)

        # Check if cache is valid (1 hour expiry)
        # Note: We cache the mapping (code -> id) but need to return the full list
        # For now, we'll always fetch but use cache for quick lookups in _find_blueprint
        # In the future, we could cache the full list too
        
        # Fetch fresh expansions
        await self._rate_limit()
        client = await self._get_client()
        
        try:
            response = await client.get("/expansions")
            response.raise_for_status()
            expansions_data = response.json()
            
            # Per documentation, API returns array directly
            if isinstance(expansions_data, list):
                expansions = expansions_data
            elif isinstance(expansions_data, dict) and "data" in expansions_data:
                expansions = expansions_data["data"]
            else:
                expansions = []
            
            # Build cache mapping set code to expansion ID
            self._expansions_cache = {}
            for expansion in expansions:
                if isinstance(expansion, dict):
                    exp_code = expansion.get("code")
                    exp_id = expansion.get("id")
                    if exp_code and exp_id:
                        self._expansions_cache[exp_code.upper()] = exp_id
            
            self._expansions_cache_time = now
            logger.debug("CardTrader expansions cached", count=len(expansions))
            
            return expansions
            
        except Exception as e:
            logger.warning("Failed to fetch CardTrader expansions", error=str(e))
            return []
    
    async def _find_blueprint(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
    ) -> int | None:
        """
        Find CardTrader blueprint ID for a card.
        
        Process:
        1. Query CardTrader expansions API to find the set (cached)
        2. Search for the card within that expansion's blueprints using /blueprints/export
        3. Match by name and collector_number
        4. Return the blueprint_id
        
        Per CardTrader API documentation: https://www.cardtrader.com/docs/api/full/reference
        """
        await self._rate_limit()
        client = await self._get_client()
        
        try:
            # Step 1: Find expansion by set code (cached)
            expansions = await self._get_expansions_cached()
            expansion_id = None
            set_code_upper = set_code.upper()
            
            # First try exact match from cache
            if self._expansions_cache:
                expansion_id = self._expansions_cache.get(set_code_upper)
            
            # If not in cache, search expansions list
            if not expansion_id:
                for expansion in expansions:
                    if not isinstance(expansion, dict):
                        continue
                    
                    # Per documentation, Expansion object has: id, game_id, code, name
                    exp_code = expansion.get("code")
                    if exp_code and exp_code.upper() == set_code_upper:
                        expansion_id = expansion.get("id")
                        break
                    
                    # Fallback: check if set code is in expansion name
                    if not expansion_id:
                        name = expansion.get("name", "").upper()
                        if set_code_upper in name:
                            expansion_id = expansion.get("id")
                            # Update cache
                            if self._expansions_cache is not None:
                                self._expansions_cache[set_code_upper] = expansion_id
                            break
            
            if not expansion_id:
                logger.debug(
                    "Expansion not found in CardTrader",
                    set_code=set_code,
                    card_name=card_name,
                    expansions_checked=len(expansions)
                )
                return None
            
            # Step 2: Get blueprints for this expansion
            # Per documentation: GET /blueprints/export?expansion_id={id}
            await self._rate_limit()
            response = await client.get(
                "/blueprints/export",
                params={"expansion_id": expansion_id}
            )
            response.raise_for_status()
            blueprints_data = response.json()
            
            # Per documentation, API returns array of blueprints
            blueprints = []
            if isinstance(blueprints_data, list):
                blueprints = blueprints_data
            elif isinstance(blueprints_data, dict):
                # Handle paginated response if API returns it
                if "data" in blueprints_data:
                    blueprints = blueprints_data["data"]
                elif "blueprints" in blueprints_data:
                    blueprints = blueprints_data["blueprints"]
            
            # Step 3: Match card by name and collector number
            card_name_normalized = card_name.upper().strip()
            # Remove common suffixes that might differ between sources
            card_name_clean = card_name_normalized.replace(" // ", " ").replace(" / ", " ")
            
            # Track best matches for scoring
            best_match = None
            best_score = 0
            
            for blueprint in blueprints:
                if not isinstance(blueprint, dict):
                    continue
                
                # Match by name (per documentation, blueprint has name field)
                blueprint_name = blueprint.get("name") or blueprint.get("card_name")
                if not blueprint_name:
                    continue
                
                blueprint_name_normalized = blueprint_name.upper().strip()
                blueprint_name_clean = blueprint_name_normalized.replace(" // ", " ").replace(" / ", " ")
                
                # Score matches (exact > partial)
                score = 0
                if blueprint_name_clean == card_name_clean:
                    score = 100  # Exact match
                elif blueprint_name_normalized == card_name_normalized:
                    score = 90  # Exact match (original)
                elif card_name_clean in blueprint_name_clean or blueprint_name_clean in card_name_clean:
                    score = 50  # Partial match
                
                # Boost score if collector number matches
                if collector_number:
                    blueprint_collector = str(blueprint.get("number") or blueprint.get("collector_number") or "")
                    if blueprint_collector == str(collector_number):
                        score += 30  # Collector number match bonus
                    elif blueprint_collector and score > 0:
                        # Name matches but collector doesn't - reduce score
                        score = max(0, score - 20)
                
                # If exact match with collector number, return immediately
                if score >= 130:  # Exact name + collector match
                    blueprint_id = blueprint.get("id")
                    if blueprint_id:
                        logger.debug(
                            "Found CardTrader blueprint (exact match)",
                            blueprint_id=blueprint_id,
                            card_name=card_name,
                            set_code=set_code
                        )
                        return int(blueprint_id)
                
                # Track best match
                if score > best_score:
                    best_score = score
                    best_match = blueprint
            
            # Return best match if score is good enough
            if best_match and best_score >= 50:
                blueprint_id = best_match.get("id")
                if blueprint_id:
                    logger.debug(
                        "Found CardTrader blueprint (best match)",
                        blueprint_id=blueprint_id,
                        card_name=card_name,
                        set_code=set_code,
                        match_score=best_score
                    )
                    return int(blueprint_id)
            
            # This is expected behavior - not all cards have CardTrader blueprints
            # Log at debug level only (not warning) since this is normal
            logger.debug(
                "CardTrader blueprint not found (expected for some cards)",
                card_name=card_name,
                set_code=set_code,
                collector_number=collector_number,
                expansion_id=expansion_id,
                blueprints_checked=len(blueprints),
                expansion_found=expansion_id is not None
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
    
    async def _get_marketplace_products(
        self, 
        blueprint_id: int,
        language: str = "en",
        currency: str = "USD",
    ) -> list[dict[str, Any]]:
        """
        Get marketplace products for a blueprint.
        
        Args:
            blueprint_id: CardTrader blueprint ID
            language: Language filter (2-letter code, e.g., "en" for English). Default: "en"
            currency: Currency filter (e.g., "USD", "EUR"). Default: "USD"
        """
        await self._rate_limit()
        client = await self._get_client()
        
        try:
            # Build params - language filter is supported by API
            params = {
                "blueprint_id": blueprint_id,
                "limit": 100,
                "language": language,  # Filter by English language
            }
            
            response = await client.get(
                "/marketplace/products",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            # CardTrader API returns data in different formats
            # Check if it's a list or dict with 'data' key
            products = []
            if isinstance(data, list):
                products = data
            elif isinstance(data, dict) and "data" in data:
                products = data["data"]
            elif isinstance(data, dict) and "products" in data:
                products = data["products"]
            
            # Store original count for logging
            original_count = len(products)
            
            # Filter by currency (API doesn't support currency filter directly, so we filter results)
            if products:
                filtered_products = []
                for product in products:
                    # Check seller_price currency
                    if "seller_price" in product and product["seller_price"]:
                        price_info = product["seller_price"]
                        if isinstance(price_info, dict):
                            product_currency = price_info.get("currency", "EUR")
                            if product_currency.upper() == currency.upper():
                                filtered_products.append(product)
                    # Also check direct currency field
                    elif "currency" in product:
                        if product["currency"].upper() == currency.upper():
                            filtered_products.append(product)
                    # If no currency info, skip (can't verify)
                
                products = filtered_products
                if filtered_products:
                    logger.debug(
                        "Filtered CardTrader products by currency",
                        blueprint_id=blueprint_id,
                        currency=currency,
                        total_before=original_count,
                        total_after=len(filtered_products)
                    )
                elif original_count > 0:
                    logger.debug(
                        "No CardTrader products found matching currency filter",
                        blueprint_id=blueprint_id,
                        currency=currency,
                        total_products=original_count
                    )
            
            return products
                
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
        Fetch current listings from CardTrader marketplace in USD.
        
        Args:
            card_name: Card name (required)
            set_code: Set code (required)
            scryfall_id: Scryfall ID (optional, for matching)
            limit: Maximum number of listings to return (default: 100)
            
        Returns:
            List of CardListing objects filtered to USD currency
        """
        if not card_name or not set_code:
            logger.warning("CardTrader fetch_listings requires card_name and set_code")
            return []
        
        # Find blueprint ID for the card
        collector_number = None
        if scryfall_id:
            # Try to extract collector number from scryfall_id if possible
            # For now, we'll rely on the blueprint lookup by name and set
            pass
        
        blueprint_id = await self._find_blueprint(card_name, set_code, collector_number)
        if not blueprint_id:
            logger.debug(
                "CardTrader blueprint not found for listings",
                card_name=card_name,
                set_code=set_code
            )
            return []
        
        # Get marketplace products filtered to USD
        products = await self._get_marketplace_products(
            blueprint_id,
            language="en",  # English language
            currency="USD"  # USD currency filter
        )
        
        if not products:
            logger.debug(
                "No USD listings found for CardTrader card",
                card_name=card_name,
                set_code=set_code,
                blueprint_id=blueprint_id
            )
            return []
        
        # Convert products to CardListing objects
        listings = []
        for product in products[:limit]:  # Respect limit
            try:
                # Extract price information
                price = None
                currency = "USD"
                
                if "seller_price" in product and product["seller_price"]:
                    price_info = product["seller_price"]
                    if isinstance(price_info, dict):
                        price_cents = price_info.get("cents", 0)
                        price = price_cents / 100.0
                        currency = price_info.get("currency", "USD").upper()
                elif "price" in product:
                    price_val = product["price"]
                    if isinstance(price_val, (int, float)):
                        price = float(price_val)
                    elif isinstance(price_val, dict) and "cents" in price_val:
                        price = price_val["cents"] / 100.0
                
                if price is None or price <= 0:
                    continue  # Skip products without valid price
                
                # Extract condition
                condition = None
                if "condition" in product:
                    condition_str = str(product["condition"]).upper()
                    condition = self.normalize_condition(condition_str)
                elif "mtg_condition" in product:
                    condition_str = str(product["mtg_condition"]).upper()
                    condition = self.normalize_condition(condition_str)
                
                # Extract language
                language = "English"
                if "language" in product:
                    lang_code = product["language"]
                    if isinstance(lang_code, str):
                        language = self.normalize_language(lang_code)
                
                # Extract foil status
                is_foil = product.get("mtg_foil", False) or product.get("foil", False)
                
                # Extract quantity
                quantity = product.get("quantity", 1)
                if not isinstance(quantity, int):
                    try:
                        quantity = int(quantity)
                    except (ValueError, TypeError):
                        quantity = 1
                
                # Extract seller info
                seller_name = None
                seller_rating = None
                if "seller" in product and isinstance(product["seller"], dict):
                    seller = product["seller"]
                    seller_name = seller.get("username") or seller.get("name")
                    seller_rating = seller.get("rating")
                elif "seller_name" in product:
                    seller_name = product["seller_name"]
                
                # Extract external ID and URL
                external_id = str(product.get("id", ""))
                listing_url = None
                if "url" in product:
                    listing_url = product["url"]
                elif "product_url" in product:
                    listing_url = product["product_url"]
                elif external_id:
                    # Construct URL from base URL and product ID
                    listing_url = f"https://www.cardtrader.com/products/{external_id}"
                
                # Extract collector number if available
                collector_number_str = str(collector_number) if collector_number else ""
                if "number" in product:
                    collector_number_str = str(product["number"])
                elif "collector_number" in product:
                    collector_number_str = str(product["collector_number"])
                
                listing = CardListing(
                    card_name=card_name,
                    set_code=set_code,
                    collector_number=collector_number_str,
                    price=price,
                    currency=currency,
                    quantity=quantity,
                    condition=condition,
                    language=language,
                    is_foil=is_foil,
                    seller_name=seller_name,
                    seller_rating=seller_rating,
                    external_id=external_id,
                    listing_url=listing_url,
                    scryfall_id=scryfall_id,
                    raw_data=product,  # Store raw data for debugging
                )
                listings.append(listing)
                
            except Exception as e:
                logger.warning(
                    "Error converting CardTrader product to listing",
                    product_id=product.get("id"),
                    error=str(e)
                )
                continue
        
        logger.debug(
            "CardTrader listings fetched",
            card_name=card_name,
            set_code=set_code,
            listings_count=len(listings),
            blueprint_id=blueprint_id
        )
        
        return listings
    
    async def fetch_price(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
        language: str = "en",
        currency: str = "USD",
    ) -> CardPrice | None:
        """
        Fetch current marketplace prices from CardTrader.
        
        Args:
            card_name: Card name
            set_code: Set code
            collector_number: Collector number
            scryfall_id: Scryfall ID (optional, for matching)
            language: Language filter (2-letter code, e.g., "en" for English). Default: "en"
            currency: Currency filter (e.g., "USD", "EUR"). Default: "USD"
            
        Returns:
            CardPrice object or None if not found
        """
        # Find blueprint ID
        blueprint_id = await self._find_blueprint(card_name, set_code, collector_number)
        if not blueprint_id:
            return None
        
        # Get marketplace products (filtered by language and currency)
        products = await self._get_marketplace_products(
            blueprint_id,
            language=language,
            currency=currency  # Filter by currency (defaults to USD)
        )
        if not products:
            return None
        
        # Calculate prices from listings
        # Note: Products are already filtered by currency if currency parameter was provided
        prices = []
        for product in products:
            # CardTrader product structure varies, check common fields
            price_data = None
            
            # Check for seller_price (most common)
            if "seller_price" in product and product["seller_price"]:
                price_info = product["seller_price"]
                if isinstance(price_info, dict):
                    price_cents = price_info.get("cents", 0)
                    product_currency = price_info.get("currency", "EUR")
                    price = price_cents / 100.0
                    prices.append({"price": price, "currency": product_currency})
            
            # Alternative: check for price field directly
            elif "price" in product:
                price_val = product["price"]
                if isinstance(price_val, (int, float)):
                    product_currency = product.get("currency", "EUR")
                    prices.append({"price": float(price_val), "currency": product_currency})
        
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
        
        # Use the currency from prices (should match currency parameter if filtering was applied)
        result_currency = prices[0]["currency"] if prices else currency
        
        return CardPrice(
            card_name=card_name,
            set_code=set_code,
            collector_number=collector_number or "",
            scryfall_id=scryfall_id,
            price=avg_price,
            currency=result_currency,
            price_low=min_price,
            price_high=max_price,
            price_foil=price_foil,
            num_listings=len(products),
            snapshot_time=datetime.now(timezone.utc),
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
        # Clear cache on close
        self._expansions_cache = None
        self._expansions_cache_time = None

