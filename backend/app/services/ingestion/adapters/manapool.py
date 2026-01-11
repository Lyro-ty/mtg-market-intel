"""
Manapool API adapter for marketplace price data and listings.

Manapool is a European MTG marketplace with a simple REST API.
API Documentation: https://manapool.com/api/docs/v1
Authentication: X-ManaPool-Access-Token header
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


class ManapoolAdapter(MarketplaceAdapter):
    """
    Adapter for Manapool API.

    Provides current marketplace prices and listings from Manapool.com.
    Rate limit: Be respectful (1 request per second by default)
    Authentication: API token in header
    """

    BASE_URL = "https://manapool.com/api/v1"
    RATE_LIMIT_REQUESTS = 60
    RATE_LIMIT_WINDOW = 60  # seconds (60 requests per minute assumed)

    def __init__(self, config: AdapterConfig | None = None):
        # Get API token from settings
        api_token = settings.manapool_api_token

        if config is None:
            config = AdapterConfig(
                base_url=self.BASE_URL,
                api_url=self.BASE_URL,
                api_key=api_token,
                rate_limit_seconds=self.RATE_LIMIT_WINDOW / self.RATE_LIMIT_REQUESTS,
                # timeout_seconds uses the default from AdapterConfig (settings.external_api_timeout)
            )
        super().__init__(config)

        # Ensure credentials are set
        if not self.config.api_key:
            logger.warning("Manapool API token not configured - adapter will not be able to fetch data")

        self._client: httpx.AsyncClient | None = None
        self._request_count = 0
        self._window_start = datetime.now(timezone.utc)

    @property
    def marketplace_name(self) -> str:
        return "Manapool"

    @property
    def marketplace_slug(self) -> str:
        return "manapool"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {
                "User-Agent": self.config.user_agent,
                "Accept": "application/json",
            }

            # Add auth token if available
            if self.config.api_key:
                headers["X-ManaPool-Access-Token"] = self.config.api_key

            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=httpx.Timeout(self.config.timeout_seconds),
                headers=headers,
                follow_redirects=True,
            )
        return self._client

    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        now = datetime.now(timezone.utc)
        elapsed = (now - self._window_start).total_seconds()

        # Reset window if time has passed
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
                self._window_start = datetime.now(timezone.utc)

        self._request_count += 1

        # Also enforce per-request rate limit
        if self._last_request_time is not None:
            elapsed_since_last = (now - self._last_request_time).total_seconds()
            if elapsed_since_last < self.config.rate_limit_seconds:
                await asyncio.sleep(self.config.rate_limit_seconds - elapsed_since_last)

        self._last_request_time = datetime.now(timezone.utc)

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        max_retries: int = 3,
        **kwargs
    ) -> httpx.Response:
        """
        Make an authenticated request to Manapool API.

        Handles retries for transient failures.
        """
        if not self.config.api_key:
            raise ValueError("Manapool API token not configured")

        await self._rate_limit()
        client = await self._get_client()

        last_exception = None

        for attempt in range(max_retries):
            try:
                response = await client.request(method, endpoint, **kwargs)

                # Retry on 5xx errors (server errors)
                if response.status_code >= 500 and attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        "Manapool server error, retrying",
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
                        "Manapool network error, retrying",
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

    async def fetch_bulk_prices(self) -> list[dict[str, Any]]:
        """
        Fetch all in-stock singles prices from Manapool.

        This is the primary endpoint for bulk price data.

        Returns:
            List of price data dictionaries
        """
        try:
            response = await self._make_request("GET", "/prices/singles")
            response.raise_for_status()
            data = response.json()

            # The response structure may be a list or wrapped in a data field
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("data", data.get("prices", []))
            return []

        except httpx.HTTPStatusError as e:
            logger.warning(
                "Manapool bulk prices API error",
                status=e.response.status_code,
                error=e.response.text[:200]
            )
            return []
        except Exception as e:
            logger.error("Manapool bulk prices error", error=str(e))
            return []

    async def fetch_card_info(self, card_names: list[str]) -> list[dict[str, Any]]:
        """
        Lookup card info for up to 100 cards by name.

        Args:
            card_names: List of card names to lookup (max 100)

        Returns:
            List of card info dictionaries
        """
        if not card_names:
            return []

        # Limit to 100 cards per API docs
        card_names = card_names[:100]

        try:
            response = await self._make_request(
                "POST",
                "/card_info",
                json={"cards": card_names}
            )
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("data", data.get("cards", []))
            return []

        except httpx.HTTPStatusError as e:
            logger.warning(
                "Manapool card info API error",
                status=e.response.status_code,
                error=e.response.text[:200]
            )
            return []
        except Exception as e:
            logger.error("Manapool card info error", error=str(e))
            return []

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
            card_name: Card name (optional filter)
            set_code: Set code (optional filter)
            scryfall_id: Scryfall ID (optional filter)
            limit: Maximum number of listings to return

        Returns:
            List of CardListing objects
        """
        try:
            # Build query parameters
            params: dict[str, Any] = {"limit": limit}
            if card_name:
                params["card_name"] = card_name
            if set_code:
                params["set_code"] = set_code

            response = await self._make_request(
                "GET",
                "/inventory/listings",
                params=params
            )
            response.raise_for_status()
            data = response.json()

            # Parse listings from response
            raw_listings = []
            if isinstance(data, list):
                raw_listings = data
            elif isinstance(data, dict):
                raw_listings = data.get("data", data.get("listings", []))

            # Convert to CardListing objects
            listings = []
            for item in raw_listings[:limit]:
                try:
                    listing = self._parse_listing(item, scryfall_id)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    logger.warning(
                        "Error parsing Manapool listing",
                        error=str(e)
                    )
                    continue

            logger.debug(
                "Manapool listings fetched",
                card_name=card_name,
                listings_count=len(listings)
            )

            return listings

        except httpx.HTTPStatusError as e:
            logger.warning(
                "Manapool API error",
                status=e.response.status_code,
                card_name=card_name,
                error=e.response.text[:200]
            )
            return []
        except Exception as e:
            logger.error("Manapool API error", card_name=card_name, error=str(e))
            return []

    def _parse_listing(
        self,
        item: dict[str, Any],
        scryfall_id: str | None = None
    ) -> CardListing | None:
        """Parse a raw listing into a CardListing object."""
        # Extract required fields - field names may vary based on actual API
        card_name = item.get("name") or item.get("card_name") or item.get("cardName")
        set_code = item.get("set") or item.get("set_code") or item.get("setCode") or ""
        collector_number = item.get("collector_number") or item.get("number") or ""

        # Get price - try various field names
        price = item.get("price") or item.get("unit_price") or item.get("unitPrice") or 0
        try:
            price = float(price)
        except (ValueError, TypeError):
            price = 0.0

        if not card_name or price <= 0:
            return None

        # Extract optional fields
        quantity = int(item.get("quantity") or item.get("stock") or 1)
        condition = item.get("condition") or item.get("cond")
        language = item.get("language") or item.get("lang") or "English"
        is_foil = bool(item.get("foil") or item.get("is_foil") or item.get("isFoil"))

        # Seller info
        seller_name = item.get("seller") or item.get("seller_name") or item.get("shop")

        # External reference
        external_id = str(item.get("id") or item.get("listing_id") or "")
        listing_url = item.get("url") or item.get("listing_url")
        if not listing_url and external_id:
            listing_url = f"https://manapool.com/listing/{external_id}"

        return CardListing(
            card_name=card_name,
            set_code=set_code,
            collector_number=collector_number,
            price=price,
            currency="EUR",  # Manapool is European
            quantity=quantity,
            condition=condition,
            language=language,
            is_foil=is_foil,
            seller_name=seller_name,
            external_id=external_id,
            listing_url=listing_url,
            scryfall_id=scryfall_id,
            raw_data=item,
        )

    async def fetch_price(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
    ) -> CardPrice | None:
        """
        Fetch aggregated price data for a specific card.

        Args:
            card_name: Card name
            set_code: Set code
            collector_number: Collector number
            scryfall_id: Scryfall ID

        Returns:
            CardPrice object or None if not found
        """
        try:
            # Use card_info endpoint to get price data
            cards = await self.fetch_card_info([card_name])

            if not cards:
                return None

            # Find matching card (by set if provided)
            matching_card = None
            for card in cards:
                card_set = card.get("set") or card.get("set_code") or ""
                if not set_code or card_set.lower() == set_code.lower():
                    matching_card = card
                    break

            if not matching_card:
                # Take first result if no exact match
                matching_card = cards[0]

            # Extract price data
            price = matching_card.get("price") or matching_card.get("min_price") or 0
            try:
                price = float(price)
            except (ValueError, TypeError):
                price = 0.0

            if price <= 0:
                return None

            # Try to get price variants
            price_low = matching_card.get("min_price") or matching_card.get("price_low")
            price_high = matching_card.get("max_price") or matching_card.get("price_high")
            price_foil = matching_card.get("foil_price") or matching_card.get("price_foil")
            num_listings = matching_card.get("listings") or matching_card.get("num_listings")

            return CardPrice(
                card_name=card_name,
                set_code=set_code,
                collector_number=collector_number or "",
                scryfall_id=scryfall_id,
                price=price,
                currency="EUR",
                price_low=float(price_low) if price_low else None,
                price_high=float(price_high) if price_high else None,
                price_foil=float(price_foil) if price_foil else None,
                num_listings=int(num_listings) if num_listings else None,
                snapshot_time=datetime.now(timezone.utc),
            )

        except Exception as e:
            logger.error("Manapool price fetch error", card_name=card_name, error=str(e))
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
            # Use card_info endpoint with the query as a card name
            # This is a simple approach - real API may have a search endpoint
            cards = await self.fetch_card_info([query])
            return cards[:limit]

        except Exception as e:
            logger.error("Manapool search error", query=query, error=str(e))
            return []

    async def health_check(self) -> bool:
        """
        Check if Manapool API is reachable.

        Returns:
            True if healthy, False otherwise.
        """
        if not self.config.api_key:
            return False

        try:
            client = await self._get_client()
            response = await client.get("/health", timeout=5.0)
            return response.status_code < 500
        except Exception:
            # Try a simple request to check connectivity
            try:
                response = await self._make_request("GET", "/prices/singles", max_retries=1)
                return response.status_code < 500
            except Exception:
                return False

    async def close(self) -> None:
        """Cleanup HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
