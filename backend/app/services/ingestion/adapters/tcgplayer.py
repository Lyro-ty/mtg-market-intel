"""
TCGPlayer API adapter for marketplace price data and listings.

TCGPlayer provides comprehensive marketplace data via their Partner API.
API Documentation: https://docs.tcgplayer.com/
Authentication: OAuth 2.0 with client credentials flow
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import structlog

from app.core.config import settings
from app.core.circuit_breaker import CircuitOpenError, get_circuit_breaker
from app.services.ingestion.base import (
    AdapterConfig,
    CardListing,
    CardPrice,
    MarketplaceAdapter,
)

logger = structlog.get_logger()


class TCGPlayerAdapter(MarketplaceAdapter):
    """
    Adapter for TCGPlayer Partner API.
    
    Provides current marketplace prices and listings.
    Rate limit: Varies by endpoint (typically 100 requests per minute)
    Authentication: OAuth 2.0 client credentials
    """
    
    BASE_URL = "https://api.tcgplayer.com"
    AUTH_URL = "https://api.tcgplayer.com/token"
    RATE_LIMIT_REQUESTS = 100
    RATE_LIMIT_WINDOW = 60  # seconds (100 requests per minute)
    
    def __init__(self, config: AdapterConfig | None = None):
        # Get API credentials from settings
        api_key = settings.tcgplayer_api_key
        api_secret = settings.tcgplayer_api_secret

        if config is None:
            config = AdapterConfig(
                base_url=self.BASE_URL,
                api_url=self.BASE_URL,
                api_key=api_key,
                api_secret=api_secret,
                rate_limit_seconds=self.RATE_LIMIT_WINDOW / self.RATE_LIMIT_REQUESTS,
                # timeout_seconds uses the default from AdapterConfig (settings.external_api_timeout)
            )
        super().__init__(config)

        # Ensure credentials are set
        if not self.config.api_key or not self.config.api_secret:
            logger.warning("TCGPlayer API credentials not configured - adapter will not be able to fetch data")

        self._client: httpx.AsyncClient | None = None
        self._auth_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._request_count = 0
        self._window_start = datetime.now(timezone.utc)

        # Circuit breaker for external API resilience
        self._circuit = get_circuit_breaker(
            "tcgplayer",
            failure_threshold=5,
            recovery_timeout=60.0,  # 1 minute before retry
            half_open_requests=2,
        )
    
    @property
    def marketplace_name(self) -> str:
        return "TCGPlayer"
    
    @property
    def marketplace_slug(self) -> str:
        return "tcgplayer"
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {
                "User-Agent": self.config.user_agent,
                "Accept": "application/json",
            }
            
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=httpx.Timeout(self.config.timeout_seconds),
                headers=headers,
                follow_redirects=True,
            )
        return self._client
    
    async def _get_auth_token(self) -> str | None:
        """
        Get OAuth 2.0 access token using client credentials flow.
        
        Returns:
            Access token or None if authentication fails
        """
        # Check if we have a valid token
        if self._auth_token and self._token_expires_at:
            if datetime.now(timezone.utc) < self._token_expires_at - timedelta(minutes=5):
                return self._auth_token
        
        # Get new token
        if not self.config.api_key or not self.config.api_secret:
            logger.error("TCGPlayer API credentials not configured")
            return None
        
        client = await self._get_client()
        
        try:
            # TCGPlayer OAuth2 expects credentials in the request body
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
            }

            data = {
                "grant_type": "client_credentials",
                "client_id": self.config.api_key,
                "client_secret": self.config.api_secret,
            }

            response = await client.post(
                self.AUTH_URL,
                headers=headers,
                data=data,
            )
            response.raise_for_status()
            token_data = response.json()
            
            self._auth_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
            self._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            logger.debug("TCGPlayer authentication successful", expires_in=expires_in)
            return self._auth_token
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "TCGPlayer authentication failed",
                status=e.response.status_code,
                error=e.response.text
            )
            return None
        except Exception as e:
            logger.error("TCGPlayer authentication error", error=str(e))
            return None
    
    async def _rate_limit(self) -> None:
        """Enforce rate limiting (100 requests per minute)."""
        now = datetime.now(timezone.utc)
        elapsed = (now - self._window_start).total_seconds()

        # Reset window if 60 seconds has passed
        if elapsed >= self.RATE_LIMIT_WINDOW:
            self._request_count = 0
            self._window_start = now
            elapsed = 0

        # If we've hit the limit, wait until window resets
        if self._request_count >= self.RATE_LIMIT_REQUESTS:
            wait_time = self.RATE_LIMIT_WINDOW - elapsed
            if wait_time > 0:
                logger.debug("TCGPlayer rate limit reached, waiting", wait_seconds=wait_time)
                await asyncio.sleep(wait_time)
                self._request_count = 0
                self._window_start = datetime.now(timezone.utc)

        self._request_count += 1

        # Also enforce per-request rate limit
        if self._last_request_time is not None:
            elapsed_since_last = (now - self._last_request_time).total_seconds()
            if elapsed_since_last < self.config.rate_limit_seconds:
                await asyncio.sleep(self.config.rate_limit_seconds - elapsed_since_last)

        self._last_request_time = datetime.now(timezone.utc)
    
    async def _make_authenticated_request(
        self,
        method: str,
        endpoint: str,
        max_retries: int = 3,
        **kwargs
    ) -> httpx.Response:
        """
        Make an authenticated request to TCGPlayer API.

        Automatically handles token refresh, circuit breaker, and retries
        for transient failures.

        Raises:
            CircuitOpenError: When circuit breaker is open
            ValueError: When authentication fails
            httpx.HTTPError: On request failures after retries
        """
        # Check circuit breaker before making request
        async with self._circuit:
            token = await self._get_auth_token()
            if not token:
                raise ValueError("Failed to obtain TCGPlayer authentication token")

            await self._rate_limit()
            client = await self._get_client()

            headers = kwargs.get("headers", {})
            headers["Authorization"] = f"Bearer {token}"
            kwargs["headers"] = headers

            last_exception = None

            for attempt in range(max_retries):
                try:
                    response = await client.request(method, endpoint, **kwargs)

                    # If token expired, refresh and retry once
                    if response.status_code == 401:
                        logger.debug("TCGPlayer token expired, refreshing")
                        self._auth_token = None
                        self._token_expires_at = None
                        token = await self._get_auth_token()
                        if token:
                            headers["Authorization"] = f"Bearer {token}"
                            kwargs["headers"] = headers
                            response = await client.request(method, endpoint, **kwargs)

                    # Retry on 5xx errors (server errors)
                    if response.status_code >= 500 and attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        logger.warning(
                            "TCGPlayer server error, retrying",
                            status=response.status_code,
                            attempt=attempt + 1,
                            wait_seconds=wait_time
                        )
                        await asyncio.sleep(wait_time)
                        continue

                    return response

                except (httpx.NetworkError, httpx.TimeoutException) as e:
                    # Retry on network errors
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(
                            "TCGPlayer network error, retrying",
                            error=str(e),
                            attempt=attempt + 1,
                            wait_seconds=wait_time
                        )
                        await asyncio.sleep(wait_time)
                        last_exception = e
                        continue
                    else:
                        raise

            # If we exhausted retries, raise the last exception
            if last_exception:
                raise last_exception

            # Should not reach here, but just in case
            raise httpx.HTTPError("Failed to make request after retries")
    
    async def _find_product_id(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
    ) -> int | None:
        """
        Find TCGPlayer product ID for a card.
        
        TCGPlayer uses product IDs to identify cards. We need to search
        for the card and match it to get the product ID.
        
        Returns:
            Product ID or None if not found
        """
        try:
            # Search for the card
            # TCGPlayer search endpoint: GET /catalog/products
            params = {
                "productName": card_name,
                "limit": 100,
            }
            
            response = await self._make_authenticated_request(
                "GET",
                "/catalog/products",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            # Parse results
            results = data.get("results", [])
            if not results:
                return None
            
            # Try to match by name, collector number, and set
            # Note: TCGPlayer uses groupId (numeric) for sets, not set codes
            # We can't directly match set_code to groupId, so we prioritize name + collector number
            card_name_upper = card_name.upper()
            best_match = None
            best_score = 0
            
            for product in results:
                product_name = product.get("name", "").upper()
                product_id = product.get("productId")
                product_number = str(product.get("number", ""))
                
                if not product_id:
                    continue
                
                # Score matches (higher is better)
                score = 0
                
                # Exact name match gets highest score
                if product_name == card_name_upper:
                    score = 100
                # Partial match (name contains card name or vice versa)
                elif card_name_upper in product_name or product_name in card_name_upper:
                    score = 50
                else:
                    continue  # Skip if name doesn't match at all
                
                # Collector number match significantly boosts score
                if collector_number:
                    if product_number == str(collector_number):
                        score += 50  # Exact collector match
                    elif product_number and score > 0:
                        # Name matches but collector doesn't - reduce score
                        score = max(0, score - 30)
                
                # If we have an exact name + collector match, return immediately
                if score >= 150:
                    logger.debug(
                        "TCGPlayer product found (exact match)",
                        product_id=product_id,
                        card_name=card_name,
                        set_code=set_code
                    )
                    return product_id
                
                # Track best match
                if score > best_score:
                    best_score = score
                    best_match = product
            
            # Return best match if score is good enough (at least partial name match)
            if best_match and best_score >= 50:
                product_id = best_match.get("productId")
                logger.debug(
                    "TCGPlayer product found (best match)",
                    product_id=product_id,
                    card_name=card_name,
                    set_code=set_code,
                    match_score=best_score
                )
                return product_id
            
            # No good match found
            logger.debug(
                "TCGPlayer product not found",
                card_name=card_name,
                set_code=set_code,
                results_count=len(results)
            )
            return None
            
        except Exception as e:
            logger.warning(
                "Error finding TCGPlayer product ID",
                card_name=card_name,
                set_code=set_code,
                error=str(e)
            )
            return None
    
    async def fetch_listings(
        self,
        card_name: str | None = None,
        set_code: str | None = None,
        scryfall_id: str | None = None,
        limit: int = 100,
    ) -> list[CardListing]:
        """
        Fetch current listings from TCGPlayer marketplace.
        
        Args:
            card_name: Card name (required)
            set_code: Set code (required)
            scryfall_id: Scryfall ID (optional, for matching)
            limit: Maximum number of listings to return (default: 100)
            
        Returns:
            List of CardListing objects
        """
        if not card_name or not set_code:
            logger.warning("TCGPlayer fetch_listings requires card_name and set_code")
            return []
        
        try:
            # Find product ID
            product_id = await self._find_product_id(card_name, set_code)
            if not product_id:
                logger.debug(
                    "TCGPlayer product not found",
                    card_name=card_name,
                    set_code=set_code
                )
                return []
            
            # Get marketplace listings for this product
            # TCGPlayer endpoint: GET /pricing/product/{productId}
            response = await self._make_authenticated_request(
                "GET",
                f"/pricing/product/{product_id}",
            )
            response.raise_for_status()
            data = response.json()
            
            # Parse listings
            listings = []
            results = data.get("results", [])
            
            for item in results[:limit]:
                try:
                    # TCGPlayer pricing structure
                    # Each item represents a condition/printing variant
                    price = float(item.get("lowPrice") or 0)
                    if price <= 0:
                        continue
                    
                    # Extract condition
                    condition_str = item.get("subTypeName", "Near Mint")
                    condition = self.normalize_condition(condition_str)
                    
                    # Extract foil status
                    is_foil = "foil" in condition_str.lower() or item.get("isFoil", False)
                    
                    # Extract quantity (TCGPlayer provides market data, not individual listings)
                    quantity = item.get("quantity", 1)
                    
                    listing = CardListing(
                        card_name=card_name,
                        set_code=set_code,
                        collector_number="",  # TCGPlayer doesn't provide this in pricing endpoint
                        price=price,
                        currency="USD",
                        quantity=quantity,
                        condition=condition,
                        language="English",  # TCGPlayer primarily deals in English
                        is_foil=is_foil,
                        external_id=str(product_id),
                        listing_url=f"https://www.tcgplayer.com/product/{product_id}",
                        scryfall_id=scryfall_id,
                        raw_data=item,
                    )
                    listings.append(listing)
                    
                except Exception as e:
                    logger.warning(
                        "Error converting TCGPlayer listing",
                        product_id=product_id,
                        error=str(e)
                    )
                    continue
            
            logger.debug(
                "TCGPlayer listings fetched",
                card_name=card_name,
                product_id=product_id,
                listings_count=len(listings)
            )
            
            return listings
            
        except CircuitOpenError:
            # Circuit breaker is open - fail fast without logging error
            # (already logged by circuit breaker)
            return []
        except httpx.HTTPStatusError as e:
            logger.warning(
                "TCGPlayer API error",
                status=e.response.status_code,
                card_name=card_name,
                error=e.response.text[:200]
            )
            return []
        except Exception as e:
            logger.error("TCGPlayer API error", card_name=card_name, error=str(e))
            return []

    async def fetch_price(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
    ) -> CardPrice | None:
        """
        Fetch current marketplace prices from TCGPlayer.
        
        Args:
            card_name: Card name
            set_code: Set code
            collector_number: Collector number
            scryfall_id: Scryfall ID (optional, for matching)
            
        Returns:
            CardPrice object or None if not found
        """
        try:
            # Find product ID
            product_id = await self._find_product_id(card_name, set_code, collector_number)
            if not product_id:
                return None
            
            # Get pricing data
            # TCGPlayer endpoint: GET /pricing/product/{productId}
            response = await self._make_authenticated_request(
                "GET",
                f"/pricing/product/{product_id}",
            )
            response.raise_for_status()
            data = response.json()
            
            # Parse pricing data
            results = data.get("results", [])
            if not results:
                return None
            
            # Aggregate prices from all conditions/printings
            prices = []
            foil_prices = []
            for item in results:
                price = float(item.get("lowPrice") or 0)
                if price > 0:
                    is_foil = item.get("isFoil", False) or "foil" in item.get("subTypeName", "").lower()
                    if is_foil:
                        foil_prices.append(price)
                    else:
                        prices.append(price)
            
            if not prices:
                return None
            
            # Calculate aggregate prices
            avg_price = sum(prices) / len(prices)
            min_price = min(prices)
            max_price = max(prices)
            price_foil = sum(foil_prices) / len(foil_prices) if foil_prices else None
            
            return CardPrice(
                card_name=card_name,
                set_code=set_code,
                collector_number=collector_number or "",
                scryfall_id=scryfall_id,
                price=avg_price,
                currency="USD",
                price_low=min_price,
                price_high=max_price,
                price_foil=price_foil,
                num_listings=len(results),
                snapshot_time=datetime.now(timezone.utc),
            )
            
        except CircuitOpenError:
            # Circuit breaker is open - fail fast without logging error
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(
                "TCGPlayer API error",
                status=e.response.status_code,
                card_name=card_name,
                error=e.response.text[:200]
            )
            return None
        except Exception as e:
            logger.error("TCGPlayer API error", card_name=card_name, error=str(e))
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
        try:
            params = {
                "productName": query,
                "limit": limit,
            }
            
            response = await self._make_authenticated_request(
                "GET",
                "/catalog/products",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            return data.get("results", [])[:limit]

        except CircuitOpenError:
            # Circuit breaker is open - fail fast without logging error
            return []
        except Exception as e:
            logger.error("TCGPlayer search error", query=query, error=str(e))
            return []

    async def close(self) -> None:
        """Cleanup HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        self._auth_token = None
        self._token_expires_at = None

