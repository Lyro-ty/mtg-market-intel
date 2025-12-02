"""
Card Kingdom marketplace adapter.

Uses Scryfall's aggregated Card Kingdom price data and web scraping for listings.
"""
import asyncio
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode

import httpx
import structlog
from selectolax.parser import HTMLParser

from app.core.config import settings
from app.services.ingestion.base import (
    AdapterConfig,
    CardListing,
    CardPrice,
    MarketplaceAdapter,
)
from app.services.ingestion.scraper_utils import (
    clean_price,
    extract_text,
    extract_attr,
    fetch_page,
)

logger = structlog.get_logger()


class CardKingdomAdapter(MarketplaceAdapter):
    """
    Adapter for Card Kingdom marketplace.
    
    Uses Scryfall's aggregated price data and web scraping for individual listings.
    """
    
    def __init__(self, config: AdapterConfig | None = None):
        if config is None:
            config = AdapterConfig(
                base_url="https://www.cardkingdom.com",
                api_url="https://api.scryfall.com",
                rate_limit_seconds=max(settings.scryfall_rate_limit_ms / 1000, 2.0),
            )
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._scryfall_client: httpx.AsyncClient | None = None
        # Card Kingdom typically prices 10-20% higher than TCGPlayer market
        self._markup_factor = 1.15
    
    @property
    def marketplace_name(self) -> str:
        return "Card Kingdom"
    
    @property
    def marketplace_slug(self) -> str:
        return "cardkingdom"
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for web scraping."""
        if self._client is None or self._client.is_closed:
            # Use proper headers to avoid being blocked
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Referer": "https://www.cardkingdom.com/",
            }
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                follow_redirects=True,
                headers=headers,
            )
        return self._client
    
    async def _get_scryfall_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for Scryfall API."""
        if self._scryfall_client is None or self._scryfall_client.is_closed:
            self._scryfall_client = httpx.AsyncClient(
                base_url=self.config.api_url or "https://api.scryfall.com",
                timeout=self.config.timeout_seconds,
                headers={"User-Agent": self.config.user_agent},
            )
        return self._scryfall_client
    
    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        if self._last_request_time is not None:
            elapsed = (datetime.utcnow() - self._last_request_time).total_seconds()
            if elapsed < self.config.rate_limit_seconds:
                await asyncio.sleep(self.config.rate_limit_seconds - elapsed)
        self._last_request_time = datetime.utcnow()
    
    async def _request_scryfall(self, endpoint: str, params: dict | None = None) -> dict | None:
        """Make a rate-limited request to Scryfall."""
        await self._rate_limit()
        client = await self._get_scryfall_client()
        
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
        Fetch individual listings from Card Kingdom by scraping the website.
        
        Card Kingdom is a single-seller marketplace that shows condition variants
        on product detail pages. Strategy:
        1. Search for the product
        2. Find product link
        3. Navigate to product page
        4. Extract condition variants (NM, EX, VG, G) as separate listings
        5. Handle foil variants if available
        """
        if not card_name:
            return []
        
        listings = []
        client = await self._get_client()
        
        try:
            # Step 1: Search for the product
            search_query = card_name
            if set_code:
                search_query += f" {set_code}"
            
            # Card Kingdom search URL
            search_url = f"{self.config.base_url}/mtg/search"
            params = {
                "search": search_query,
            }
            search_page_url = f"{search_url}?{urlencode(params)}"
            
            await self._rate_limit()
            search_tree = await fetch_page(client, search_page_url, timeout=self.config.timeout_seconds)
            
            if not search_tree:
                logger.warning("Failed to fetch Card Kingdom search page", card_name=card_name)
                return []
            
            # Step 2: Find product link - Card Kingdom product links are typically /mtg/{set}/{card-name}
            product_links = []
            for link in search_tree.css("a[href*='/mtg/']"):
                href = link.attributes.get("href", "")
                if "/mtg/" in href and href not in product_links:
                    if not href.startswith("http"):
                        href = f"{self.config.base_url}{href}"
                    product_links.append(href)
            
            if not product_links:
                logger.warning("No product links found on Card Kingdom search page", card_name=card_name)
                return []
            
            # Step 3: Navigate to first product page (where condition variants are shown)
            product_url = product_links[0]
            
            await self._rate_limit()
            tree = await fetch_page(client, product_url, timeout=self.config.timeout_seconds)
            
            if not tree:
                logger.warning("Failed to fetch Card Kingdom product page", card_name=card_name, url=product_url)
                return []
            
            # Step 4: Extract condition variants from product page
            # Card Kingdom shows conditions as tabs/buttons: NM, EX, VG, G
            # Each condition has its own price and quantity
            
            # Look for condition tabs/buttons
            condition_elements = []
            condition_selectors = [
                "button[class*='condition']",
                "a[class*='condition']",
                "[data-condition]",
                "button[class*='tab']",
                "a[class*='tab']",
                "[role='tab']",
            ]
            
            for selector in condition_selectors:
                elements = tree.css(selector)
                if elements:
                    condition_elements = elements
                    logger.debug("Found condition elements", selector=selector, count=len(elements))
                    break
            
            # If no condition tabs found, try to find condition indicators in text
            if not condition_elements:
                # Look for text patterns like "NM", "EX", "VG", "G" or "Near Mint", etc.
                all_text = tree.text()
                conditions_found = []
                for cond in ["NM", "Near Mint", "EX", "Excellent", "VG", "Very Good", "G", "Good"]:
                    if cond.lower() in all_text.lower():
                        conditions_found.append(cond)
                
                if conditions_found:
                    logger.debug("Found condition keywords in page", conditions=conditions_found)
            
            # Extract price and quantity from the product page
            # Card Kingdom shows current price and availability for the selected condition
            price_text = None
            quantity_text = None
            
            # Try multiple selectors for price
            price_selectors = [
                "[class*='price']",
                "[class*='Price']",
                "[data-price]",
                "span:contains('$')",
            ]
            
            for selector in price_selectors:
                price_elem = tree.css_first(selector)
                if price_elem:
                    price_text = price_elem.text(strip=True)
                    if price_text and "$" in price_text:
                        break
            
            # Try to extract from full page text if not found
            if not price_text:
                full_text = tree.text()
                price_match = re.search(r'\$(\d+\.?\d*)', full_text)
                if price_match:
                    price_text = f"${price_match.group(1)}"
            
            # Try multiple selectors for quantity/availability
            quantity_selectors = [
                "[class*='available']",
                "[class*='stock']",
                "[class*='quantity']",
                "span:contains('available')",
            ]
            
            for selector in quantity_selectors:
                qty_elem = tree.css_first(selector)
                if qty_elem:
                    quantity_text = qty_elem.text(strip=True)
                    if quantity_text and ("available" in quantity_text.lower() or quantity_text.isdigit()):
                        break
            
            # Extract from full text if not found
            if not quantity_text:
                full_text = tree.text()
                qty_match = re.search(r'(\d+)\s+available', full_text, re.IGNORECASE)
                if qty_match:
                    quantity_text = qty_match.group(1)
            
            # Parse price and quantity
            price = clean_price(price_text) if price_text else None
            quantity = 1
            if quantity_text:
                qty_match = re.search(r'(\d+)', quantity_text)
                if qty_match:
                    try:
                        quantity = int(qty_match.group(1))
                    except (ValueError, AttributeError):
                        quantity = 1
            
            # Card Kingdom shows different conditions - create listings for each
            # Standard conditions: NM, EX (LP), VG (MP), G (HP)
            conditions_to_check = ["NM", "EX", "VG", "G"]
            full_text_lower = tree.text().lower()
            
            for condition_abbr in conditions_to_check:
                # Check if this condition is available on the page
                condition_available = False
                if condition_abbr == "NM":
                    condition_available = "nm" in full_text_lower or "near mint" in full_text_lower
                elif condition_abbr == "EX":
                    condition_available = "ex" in full_text_lower or "excellent" in full_text_lower or "lp" in full_text_lower or "lightly played" in full_text_lower
                elif condition_abbr == "VG":
                    condition_available = "vg" in full_text_lower or "very good" in full_text_lower or "mp" in full_text_lower or "moderately played" in full_text_lower
                elif condition_abbr == "G":
                    condition_available = "g" in full_text_lower or "good" in full_text_lower or "hp" in full_text_lower or "heavily played" in full_text_lower
                
                if condition_available and price and price > 0:
                    # Map Card Kingdom conditions to our standard
                    condition_map = {
                        "NM": "NM",
                        "EX": "LP",  # Card Kingdom's "Excellent" is similar to "Lightly Played"
                        "VG": "MP",  # Card Kingdom's "Very Good" is similar to "Moderately Played"
                        "G": "HP",   # Card Kingdom's "Good" is similar to "Heavily Played"
                    }
                    normalized_condition = condition_map.get(condition_abbr, "NM")
                    
                    listing = CardListing(
                        card_name=card_name,
                        set_code=set_code or "",
                        collector_number="",
                        price=price,  # Use same price for now (Card Kingdom may show different prices per condition)
                        currency="USD",
                        quantity=quantity,
                        condition=normalized_condition,
                        language="English",
                        is_foil=False,
                        seller_name="Card Kingdom",
                        seller_rating=5.0,
                        external_id=f"ck-{hash(f'{card_name}-{normalized_condition}-regular')}",
                        listing_url=product_url,
                        scraped_at=datetime.utcnow(),
                    )
                    listings.append(listing)
            
            # Check for foil version
            if "foil" in full_text_lower or "switch to foil" in full_text_lower:
                # Try to get foil price (may require clicking "Switch to Foil" button)
                # For now, create a foil listing with same price structure
                foil_price = price  # Card Kingdom typically shows foil prices when available
                
                for condition_abbr in conditions_to_check:
                    condition_available = False
                    if condition_abbr == "NM":
                        condition_available = "nm" in full_text_lower or "near mint" in full_text_lower
                    elif condition_abbr == "EX":
                        condition_available = "ex" in full_text_lower or "excellent" in full_text_lower
                    elif condition_abbr == "VG":
                        condition_available = "vg" in full_text_lower or "very good" in full_text_lower
                    elif condition_abbr == "G":
                        condition_available = "g" in full_text_lower or "good" in full_text_lower
                    
                    if condition_available and foil_price and foil_price > 0:
                        condition_map = {
                            "NM": "NM",
                            "EX": "LP",
                            "VG": "MP",
                            "G": "HP",
                        }
                        normalized_condition = condition_map.get(condition_abbr, "NM")
                        
                        listing = CardListing(
                            card_name=card_name,
                            set_code=set_code or "",
                            collector_number="",
                            price=foil_price,
                            currency="USD",
                            quantity=quantity,
                            condition=normalized_condition,
                            language="English",
                            is_foil=True,
                            seller_name="Card Kingdom",
                            seller_rating=5.0,
                            external_id=f"ck-{hash(f'{card_name}-{normalized_condition}-foil')}",
                            listing_url=product_url,
                            scraped_at=datetime.utcnow(),
                        )
                        listings.append(listing)
            
            # Log diagnostic info if no listings found
            if not listings:
                sample_classes = set()
                for el in tree.css("[class]")[:100]:
                    if el.attributes and "class" in el.attributes:
                        classes = el.attributes["class"].split()
                        sample_classes.update(classes[:5])
                
                logger.warning(
                    "No listings extracted from Card Kingdom product page",
                    card_name=card_name,
                    url=product_url,
                    price_found=price is not None,
                    quantity_found=quantity_text is not None,
                    sample_classes=list(sample_classes)[:30],
                    page_title=tree.css_first("title").text() if tree.css_first("title") else "N/A",
                )
            
            logger.info("Scraped Card Kingdom listings", card_name=card_name, count=len(listings))
            
        except Exception as e:
            logger.error("Error scraping Card Kingdom listings", card_name=card_name, error=str(e))
        
        return listings[:limit]
    
    async def fetch_price(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
    ) -> CardPrice | None:
        """
        Fetch Card Kingdom price data via Scryfall.
        
        Scryfall doesn't directly provide CK prices, but we estimate
        based on TCGPlayer prices with typical CK markup.
        """
        data = None
        
        # Try to fetch by Scryfall ID first (most reliable)
        if scryfall_id:
            data = await self._request_scryfall(f"/cards/{scryfall_id}")
        
        # Try by set and collector number
        if not data and set_code and collector_number:
            data = await self._request_scryfall(f"/cards/{set_code.lower()}/{collector_number}")
        
        # Search by name and set
        if not data:
            query = f'!"{card_name}"'
            if set_code:
                query += f" set:{set_code.lower()}"
            
            search_data = await self._request_scryfall("/cards/search", params={"q": query})
            if search_data and search_data.get("data"):
                data = search_data["data"][0]
        
        if not data:
            return None
        
        prices = data.get("prices", {})
        price_usd = prices.get("usd")
        price_foil = prices.get("usd_foil")
        
        # Skip if no USD price
        if not price_usd:
            logger.debug("No base price for CK estimate", card_name=card_name, set_code=set_code)
            return None
        
        # Apply Card Kingdom markup estimate
        ck_price = float(price_usd) * self._markup_factor
        ck_foil = float(price_foil) * self._markup_factor if price_foil else None
        
        return CardPrice(
            card_name=data.get("name", card_name),
            set_code=data.get("set", set_code).upper() if data.get("set") else set_code,
            collector_number=data.get("collector_number", collector_number),
            scryfall_id=data.get("id", scryfall_id),
            price=round(ck_price, 2),
            currency="USD",
            price_foil=round(ck_foil, 2) if ck_foil else None,
            snapshot_time=datetime.utcnow(),
        )
    
    async def search_cards(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search for cards via Scryfall."""
        data = await self._request_scryfall("/cards/search", params={"q": query})
        if not data or not data.get("data"):
            return []
        
        return data["data"][:limit]
    
    async def health_check(self) -> bool:
        """Check if Scryfall (data source) is reachable."""
        try:
            data = await self._request_scryfall("/cards/random")
            return data is not None
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close the HTTP clients."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        if self._scryfall_client and not self._scryfall_client.is_closed:
            await self._scryfall_client.aclose()
