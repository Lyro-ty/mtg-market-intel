"""
MTGJSON adapter for historical price data and card information.

MTGJSON provides aggregated historical price data and comprehensive card data.
This adapter supplements our scrapers by providing historical price trends.
"""
import asyncio
import gzip
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

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


class MTGJSONAdapter(MarketplaceAdapter):
    """
    Adapter for MTGJSON data.
    
    Provides historical price data and card information.
    MTGJSON data is updated periodically, so we cache downloads.
    """
    
    # MTGJSON base URLs
    MTGJSON_BASE_URL = "https://mtgjson.com/api/v5"
    MTGJSON_DOWNLOAD_BASE = "https://mtgjson.com/api/v5"
    
    def __init__(self, config: AdapterConfig | None = None):
        if config is None:
            config = AdapterConfig(
                base_url=self.MTGJSON_BASE_URL,
                api_url=self.MTGJSON_BASE_URL,
                rate_limit_seconds=1.0,  # Be respectful to MTGJSON
            )
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._cache_dir = Path("data/mtgjson_cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cached_data: dict | None = None  # Cache loaded AllPrintings JSON data in memory
        self._cached_allprices_data: dict | None = None  # Cache loaded AllPrices JSON data in memory
    
    @property
    def marketplace_name(self) -> str:
        return "MTGJSON"
    
    @property
    def marketplace_slug(self) -> str:
        return "mtgjson"
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=httpx.Timeout(60.0),  # Longer timeout for large downloads
                headers={"User-Agent": self.config.user_agent},
                follow_redirects=True,
            )
        return self._client
    
    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        if self._last_request_time is not None:
            elapsed = (datetime.now(timezone.utc) - self._last_request_time).total_seconds()
            if elapsed < self.config.rate_limit_seconds:
                await asyncio.sleep(self.config.rate_limit_seconds - elapsed)
        self._last_request_time = datetime.now(timezone.utc)
    
    async def _download_file(self, url: str, cache_file: Path) -> dict | None:
        """
        Download and cache a file from MTGJSON.
        
        MTGJSON updates weekly, so we cache files for 7 days to avoid unnecessary downloads.
        Also uses in-memory cache to avoid reloading from disk.
        
        Args:
            url: URL to download from.
            cache_file: Local path to cache the file.
            
        Returns:
            Parsed JSON data or None if download fails.
        """
        # Check in-memory cache first (fastest)
        if "AllPrintings.json.gz" in str(cache_file) and self._cached_data is not None:
            logger.debug("Using in-memory cached AllPrintings data")
            return self._cached_data
        if "AllPrices.json.gz" in str(cache_file) and self._cached_allprices_data is not None:
            logger.debug("Using in-memory cached AllPrices data")
            return self._cached_allprices_data
        
        # Check disk cache (if less than 7 days old, since MTGJSON updates weekly)
        if cache_file.exists():
            cache_age = datetime.now(timezone.utc) - datetime.fromtimestamp(cache_file.stat().st_mtime, tz=timezone.utc)
            if cache_age < timedelta(days=7):
                logger.debug("Using cached MTGJSON file", file=str(cache_file), age_hours=cache_age.total_seconds() / 3600)
                try:
                    with open(cache_file, "rb") as f:
                        data = None
                        if cache_file.suffix == ".gz":
                            data = json.loads(gzip.decompress(f.read()))
                        else:
                            data = json.load(f)
                        
                        # Store in in-memory cache for future use
                        if "AllPrintings.json.gz" in str(cache_file):
                            self._cached_data = data
                        elif "AllPrices.json.gz" in str(cache_file):
                            self._cached_allprices_data = data
                        
                        return data
                except Exception as e:
                    logger.warning("Failed to read cache", file=str(cache_file), error=str(e))
        
        # Download file
        await self._rate_limit()
        client = await self._get_client()
        
        try:
            logger.info("Downloading MTGJSON file", url=url)
            response = await client.get(url)
            response.raise_for_status()
            
            # Save to cache
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_file, "wb") as f:
                f.write(response.content)
            
            # Parse JSON
            data = None
            if url.endswith(".gz") or cache_file.suffix == ".gz":
                data = json.loads(gzip.decompress(response.content))
            else:
                data = response.json()
            
            # Store in in-memory cache
            if "AllPrintings.json.gz" in str(cache_file):
                self._cached_data = data
            elif "AllPrices.json.gz" in str(cache_file):
                self._cached_allprices_data = data
            
            return data
                
        except httpx.HTTPStatusError as e:
            logger.error("MTGJSON download failed", url=url, status=e.response.status_code)
            return None
        except Exception as e:
            logger.error("MTGJSON download error", url=url, error=str(e))
            return None
    
    async def fetch_price(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
    ) -> CardPrice | None:
        """
        Fetch current price data from MTGJSON.
        
        Note: MTGJSON provides historical/aggregated prices, not real-time.
        This method returns the most recent price data available.
        """
        # MTGJSON doesn't provide real-time prices, so we return None
        # Historical prices should be fetched via fetch_price_history
        return None
    
    async def fetch_price_history(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
        days: int = 90,
    ) -> list[CardPrice]:
        """
        Fetch historical price data from MTGJSON.
        
        MTGJSON provides weekly price intervals going back ~3 months.
        
        Args:
            card_name: Card name.
            set_code: Set code.
            collector_number: Collector number.
            scryfall_id: Scryfall ID (not used by MTGJSON but kept for interface).
            days: Number of days of history to fetch (max ~90 days).
            
        Returns:
            List of CardPrice objects with historical timestamps.
        """
        # Try AllPrices.json first (price-only, more efficient)
        # Fallback to AllPrintings.json if AllPrices is not available
        # Only download once and cache in memory
        if self._cached_allprices_data is None:
            allprices_cache = self._cache_dir / "AllPrices.json.gz"
            allprices_url = f"{self.MTGJSON_DOWNLOAD_BASE}/AllPrices.json.gz"
            allprices_data = await self._download_file(allprices_url, allprices_cache)
            if allprices_data:
                self._cached_allprices_data = allprices_data
                logger.debug("AllPrices.json downloaded and cached in memory")
        else:
            allprices_data = self._cached_allprices_data
            logger.debug("Using in-memory cached AllPrices data")
        
        # Download AllPrintings file (contains price data and card metadata for lookup)
        cache_file = self._cache_dir / "AllPrintings.json.gz"
        url = f"{self.MTGJSON_DOWNLOAD_BASE}/AllPrintings.json.gz"
        
        # Use cached data if available, otherwise download
        if self._cached_data is None:
            data = await self._download_file(url, cache_file)
            if not data:
                logger.warning("Failed to download MTGJSON data")
                return []
            # Cache the data in memory for subsequent lookups
            self._cached_data = data
        else:
            # Use cached data
            data = self._cached_data
            logger.debug("Using in-memory cached MTGJSON data")
        
        # Find the card in the data
        set_data = data.get("data", {}).get(set_code.upper())
        if not set_data:
            logger.debug("Set not found in MTGJSON", set_code=set_code)
            return []
        
        cards = set_data.get("cards", [])
        card_data = None
        
        # Try to find by collector number first
        if collector_number:
            for card in cards:
                if str(card.get("number", "")) == str(collector_number):
                    card_data = card
                    break
        
        # Fallback to name matching
        if not card_data:
            for card in cards:
                if card.get("name", "").lower() == card_name.lower():
                    card_data = card
                    break
        
        if not card_data:
            logger.debug("Card not found in MTGJSON", card_name=card_name, set_code=set_code)
            return []
        
        # Extract price data
        prices = card_data.get("prices", {})
        
        # If we have AllPrices data, try to use it for better historical coverage
        if allprices_data and card_data.get("uuid"):
            card_uuid = card_data.get("uuid")
            allprices_card = allprices_data.get("data", {}).get(card_uuid)
            if allprices_card:
                # AllPrices has better historical data structure
                paper_prices = allprices_card.get("paper", {})
                if paper_prices:
                    # Merge AllPrices data with AllPrintings data
                    # AllPrices may have more complete historical data
                    tcgplayer_allprices = paper_prices.get("tcgplayer", {})
                    cardmarket_allprices = paper_prices.get("cardmarket", {})
                    
                    # Prefer AllPrices data if available (it's more complete)
                    if tcgplayer_allprices:
                        prices.setdefault("tcgplayer", {}).update(tcgplayer_allprices)
                    if cardmarket_allprices:
                        prices.setdefault("cardmarket", {}).update(cardmarket_allprices)
        if not prices:
            return []
        
        historical_prices = []
        
        # MTGJSON price structure:
        # - tcgplayer: { "normal": {...}, "foil": {...} }
        # - cardmarket: { "normal": {...}, "foil": {...} }
        # Each price object may have historical data with dates
        
        # Process TCGPlayer prices
        tcgplayer_prices = prices.get("tcgplayer", {})
        if tcgplayer_prices:
            for variant in ["normal", "foil"]:
                variant_data = tcgplayer_prices.get(variant, {})
                if not variant_data:
                    continue
                
                # MTGJSON may have historical data with date keys
                # Format: { "2024-01-01": 10.50, "2024-01-08": 11.00, ... }
                for date_str, price_value in variant_data.items():
                    if isinstance(price_value, (int, float)) and price_value > 0:
                        try:
                            price_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                            # Only include prices within requested days
                            if (datetime.now(timezone.utc) - price_date).days <= days:
                                historical_prices.append(
                                    CardPrice(
                                        card_name=card_data.get("name", card_name),
                                        set_code=set_code.upper(),
                                        collector_number=str(card_data.get("number", collector_number or "")),
                                        price=float(price_value),
                                        currency="USD",
                                        price_foil=float(price_value) if variant == "foil" else None,
                                        snapshot_time=price_date,
                                    )
                                )
                        except (ValueError, TypeError):
                            # Skip invalid date formats
                            continue
        
        # Process Cardmarket prices (EUR)
        cardmarket_prices = prices.get("cardmarket", {})
        if cardmarket_prices:
            for variant in ["normal", "foil"]:
                variant_data = cardmarket_prices.get(variant, {})
                if not variant_data:
                    continue
                
                for date_str, price_value in variant_data.items():
                    if isinstance(price_value, (int, float)) and price_value > 0:
                        try:
                            price_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                            if (datetime.now(timezone.utc) - price_date).days <= days:
                                historical_prices.append(
                                    CardPrice(
                                        card_name=card_data.get("name", card_name),
                                        set_code=set_code.upper(),
                                        collector_number=str(card_data.get("number", collector_number or "")),
                                        price=float(price_value),
                                        currency="EUR",  # Cardmarket uses EUR
                                        price_foil=float(price_value) if variant == "foil" else None,
                                        snapshot_time=price_date,
                                    )
                                )
                        except (ValueError, TypeError):
                            continue
        
        # If no historical data with dates, try to get current price
        if not historical_prices:
            # Try to get most recent price (may be in different format)
            current_price = None
            current_foil_price = None
            
            # Check TCGPlayer
            if tcgplayer_prices.get("normal"):
                normal_data = tcgplayer_prices["normal"]
                if isinstance(normal_data, dict):
                    # Get most recent date
                    dates = [d for d in normal_data.keys() if isinstance(normal_data[d], (int, float))]
                    if dates:
                        latest_date = max(dates)
                        current_price = normal_data[latest_date]
                elif isinstance(normal_data, (int, float)):
                    current_price = normal_data
            
            if tcgplayer_prices.get("foil"):
                foil_data = tcgplayer_prices["foil"]
                if isinstance(foil_data, dict):
                    dates = [d for d in foil_data.keys() if isinstance(foil_data[d], (int, float))]
                    if dates:
                        latest_date = max(dates)
                        current_foil_price = foil_data[latest_date]
                elif isinstance(foil_data, (int, float)):
                    current_foil_price = foil_data
            
            if current_price:
                historical_prices.append(
                    CardPrice(
                        card_name=card_data.get("name", card_name),
                        set_code=set_code.upper(),
                        collector_number=str(card_data.get("number", collector_number or "")),
                        price=float(current_price),
                        currency="USD",
                        price_foil=float(current_foil_price) if current_foil_price else None,
                        snapshot_time=datetime.now(timezone.utc),
                    )
                )
        
        # Sort by date
        historical_prices.sort(key=lambda x: x.snapshot_time)
        
        logger.info(
            "Fetched MTGJSON price history",
            card_name=card_name,
            set_code=set_code,
            count=len(historical_prices),
        )
        
        return historical_prices
    
    async def fetch_listings(
        self,
        card_name: str | None = None,
        set_code: str | None = None,
        scryfall_id: str | None = None,
        limit: int = 100,
    ) -> list[CardListing]:
        """
        MTGJSON doesn't provide individual listings.
        
        Returns empty list as this is not supported.
        """
        return []
    
    async def search_cards(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Search for cards in MTGJSON data.
        
        Note: This requires downloading the full dataset, so it's not efficient
        for real-time search. Consider using Scryfall for search instead.
        """
        # For efficiency, we'd need to cache the full dataset
        # This is a placeholder - consider implementing a local search index
        logger.warning("MTGJSON search not efficiently implemented - use Scryfall for search")
        return []
    
    async def health_check(self) -> bool:
        """Check if MTGJSON is reachable."""
        try:
            client = await self._get_client()
            # Try to access the API endpoint
            response = await client.get("/", timeout=10.0)
            return response.status_code < 500
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

