"""
TCGPlayer marketplace adapter.

Uses Scryfall's aggregated TCGPlayer price data and web scraping for listings.
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


class TCGPlayerAdapter(MarketplaceAdapter):
    """
    Adapter for TCGPlayer marketplace.
    
    Uses Scryfall's aggregated price data and web scraping for individual listings.
    """
    
    def __init__(self, config: AdapterConfig | None = None):
        if config is None:
            config = AdapterConfig(
                base_url="https://www.tcgplayer.com",
                api_url="https://api.scryfall.com",
                rate_limit_seconds=max(settings.scryfall_rate_limit_ms / 1000, 2.0),  # Be respectful
            )
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._scryfall_client: httpx.AsyncClient | None = None
    
    @property
    def marketplace_name(self) -> str:
        return "TCGPlayer"
    
    @property
    def marketplace_slug(self) -> str:
        return "tcgplayer"
    
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
                "Referer": "https://www.tcgplayer.com/",
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
        Fetch individual listings from TCGPlayer by scraping the website.
        
        TCGPlayer shows listings on product detail pages, not search results.
        Strategy:
        1. Search for the product
        2. Find product link
        3. Navigate to product page
        4. Extract seller listings from product page
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
            
            search_url = f"{self.config.base_url}/search/magic/product"
            params = {
                "q": search_query,
                "view": "grid",
            }
            search_page_url = f"{search_url}?{urlencode(params)}"
            
            await self._rate_limit()
            search_tree = await fetch_page(client, search_page_url, timeout=self.config.timeout_seconds)
            
            if not search_tree:
                logger.warning("Failed to fetch TCGPlayer search page", card_name=card_name)
                return []
            
            # Step 2: Find product link - TCGPlayer product links are typically in anchor tags
            # Look for links that go to /product/ pages
            product_links = []
            for link in search_tree.css("a[href*='/product/']"):
                href = link.attributes.get("href", "")
                if "/product/" in href and href not in product_links:
                    if not href.startswith("http"):
                        href = f"{self.config.base_url}{href}"
                    product_links.append(href)
            
            if not product_links:
                logger.warning("No product links found on TCGPlayer search page", card_name=card_name)
                return []
            
            # Step 3: Navigate to first product page (where listings are shown)
            product_url = product_links[0]
            # Add Language=English parameter to get English listings
            if "?" in product_url:
                product_url += "&Language=English"
            else:
                product_url += "?Language=English"
            
            await self._rate_limit()
            tree = await fetch_page(client, product_url, timeout=self.config.timeout_seconds)
            
            if not tree:
                logger.warning("Failed to fetch TCGPlayer product page", card_name=card_name, url=product_url)
                return []
            
            # Step 4: Extract listings from product page
            # TCGPlayer listings are in a table or list structure on the product page
            # Based on the page structure, listings contain: seller name, price, condition, quantity
            # Try multiple selector strategies for listing rows
            listing_selectors = [
                # Modern TCGPlayer structure - look for seller listing rows
                "tr[class*='seller']",
                "div[class*='seller-listing']",
                "div[class*='listing-row']",
                "li[class*='seller']",
                "article[class*='seller']",
                # Alternative patterns
                "[data-seller-id]",
                "[data-listing-id]",
                # Generic patterns that might contain listings
                "table tbody tr",
                ".listings-table tr",
                "[class*='Listing']",
            ]
            
            listing_elements = []
            for selector in listing_selectors:
                elements = tree.css(selector)
                if elements and len(elements) > 0:
                    listing_elements = elements
                    logger.debug("Found listing elements with selector", selector=selector, count=len(elements))
                    break
            
            # If no listing rows found, try to find individual listing containers
            if not listing_elements:
                # Look for elements that contain seller names and prices together
                # TCGPlayer often has seller info in specific containers
                seller_containers = tree.css("[class*='seller'], [class*='Seller']")
                if seller_containers:
                    listing_elements = seller_containers
                    logger.debug("Found seller containers", count=len(seller_containers))
            
            # Log diagnostic info if no listings found
            if not listing_elements:
                # Get a sample of class names from the page for debugging
                sample_classes = set()
                for el in tree.css("[class]")[:100]:
                    if el.attributes and "class" in el.attributes:
                        classes = el.attributes["class"].split()
                        sample_classes.update(classes[:5])
                
                logger.warning(
                    "No listing elements found on TCGPlayer product page - selectors may need updating",
                    card_name=card_name,
                    url=product_url,
                    sample_classes=list(sample_classes)[:30],
                    page_title=tree.css_first("title").text() if tree.css_first("title") else "N/A",
                )
            
            for i, element in enumerate(listing_elements[:limit]):
                try:
                    # Extract seller name - TCGPlayer shows seller names prominently
                    seller_name = (
                        extract_text(element, "[class*='seller-name']") or
                        extract_text(element, "[class*='SellerName']") or
                        extract_text(element, ".seller") or
                        extract_text(element, "[data-seller-name]") or
                        extract_attr(element, "data-seller-name") or
                        None
                    )
                    
                    # If no seller name found, skip this element (not a valid listing)
                    if not seller_name or len(seller_name.strip()) < 2:
                        continue
                    
                    # Extract price - look for price patterns in text or data attributes
                    price_text = (
                        extract_text(element, "[class*='price']") or
                        extract_text(element, "[class*='Price']") or
                        extract_text(element, "[data-price]") or
                        extract_attr(element, "data-price") or
                        None
                    )
                    
                    # If no price in element, look in child elements
                    if not price_text:
                        price_elem = element.css_first("[class*='price'], [class*='Price'], [data-price]")
                        if price_elem:
                            price_text = price_elem.text(strip=True) or price_elem.attributes.get("data-price")
                    
                    price = clean_price(price_text) if price_text else None
                    
                    if not price or price <= 0:
                        # Try to extract from full element text as fallback
                        full_text = element.text(strip=True)
                        # Look for price patterns like $0.01, $2.50, etc.
                        price_match = re.search(r'\$?\s*(\d+\.?\d*)', full_text)
                        if price_match:
                            try:
                                price = float(price_match.group(1))
                            except (ValueError, AttributeError):
                                continue
                        else:
                            continue
                    
                    # Extract condition - TCGPlayer uses standard conditions
                    condition_text = (
                        extract_text(element, "[class*='condition']") or
                        extract_text(element, "[class*='Condition']") or
                        extract_text(element, "[data-condition]") or
                        extract_attr(element, "data-condition") or
                        ""
                    )
                    
                    # If no condition in element, check full text for condition keywords
                    if not condition_text:
                        full_text_lower = element.text(strip=True).lower()
                        if "near mint" in full_text_lower or "nm" in full_text_lower:
                            condition_text = "Near Mint"
                        elif "lightly played" in full_text_lower or "lp" in full_text_lower:
                            condition_text = "Lightly Played"
                        elif "moderately played" in full_text_lower or "mp" in full_text_lower:
                            condition_text = "Moderately Played"
                        elif "heavily played" in full_text_lower or "hp" in full_text_lower:
                            condition_text = "Heavily Played"
                        elif "damaged" in full_text_lower or "dmg" in full_text_lower:
                            condition_text = "Damaged"
                    
                    condition = self.normalize_condition(condition_text) if condition_text else "NM"
                    
                    # Extract quantity - look for quantity patterns
                    qty_text = (
                        extract_text(element, "[class*='quantity']") or
                        extract_text(element, "[class*='Quantity']") or
                        extract_text(element, "[data-quantity]") or
                        extract_attr(element, "data-quantity") or
                        "1"
                    )
                    
                    # Parse quantity - look for patterns like "1 of 13", "13 available", etc.
                    quantity = 1
                    if qty_text:
                        # Try to find number in quantity text
                        qty_match = re.search(r'(\d+)', qty_text)
                        if qty_match:
                            try:
                                quantity = int(qty_match.group(1))
                            except (ValueError, AttributeError):
                                quantity = 1
                    
                    # Extract seller rating - TCGPlayer shows star ratings
                    rating_text = (
                        extract_text(element, "[class*='rating']") or
                        extract_text(element, "[class*='Rating']") or
                        extract_attr(element, "data-rating") or
                        None
                    )
                    seller_rating = None
                    if rating_text:
                        # Look for star rating patterns
                        rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                        if rating_match:
                            try:
                                seller_rating = float(rating_match.group(1))
                                if seller_rating > 5.0:
                                    seller_rating = seller_rating / 10.0  # Normalize if out of 10
                            except (ValueError, AttributeError):
                                pass
                    
                    # Check for foil - look for foil indicators
                    full_text_lower = element.text(strip=True).lower()
                    is_foil = (
                        "foil" in full_text_lower or
                        element.css_first("[class*='foil'], [data-foil='true']") is not None
                    )
                    
                    # Extract listing URL - product page URL with seller info
                    listing_url = product_url  # Use product page as base
                    
                    # Generate external ID - use seller name + price + condition for uniqueness
                    external_id = (
                        extract_attr(element, "data-listing-id") or
                        extract_attr(element, "data-id") or
                        f"tcgplayer-{hash(f'{seller_name}-{price}-{condition}-{i}')}"
                    )
                    
                    listing = CardListing(
                        card_name=card_name,
                        set_code=set_code or "",
                        collector_number="",
                        price=price,
                        currency="USD",
                        quantity=quantity,
                        condition=condition,
                        language="English",
                        is_foil=is_foil,
                        seller_name=seller_name.strip() if seller_name else None,
                        seller_rating=seller_rating,
                        external_id=external_id,
                        listing_url=listing_url,
                        scraped_at=datetime.utcnow(),
                    )
                    
                    listings.append(listing)
                    
                except Exception as e:
                    logger.debug("Failed to parse listing element", error=str(e), index=i)
                    continue
            
            # Try to fetch additional pages of listings if available
            if len(listings) < limit:
                # Look for pagination on product page
                page_num = 2
                max_pages = 5
                while page_num <= max_pages and len(listings) < limit:
                    # TCGPlayer product pages use ?page=N parameter
                    paginated_url = product_url.replace("?Language=English", f"?page={page_num}&Language=English") if "?" in product_url else f"{product_url}?page={page_num}&Language=English"
                    
                    await self._rate_limit()
                    next_tree = await fetch_page(client, paginated_url, timeout=self.config.timeout_seconds)
                    
                    if not next_tree:
                        break
                    
                    # Extract listings from this page using same selectors
                    next_listing_elements = []
                    for selector in listing_selectors:
                        elements = next_tree.css(selector)
                        if elements and len(elements) > 0:
                            next_listing_elements = elements
                            break
                    
                    if not next_listing_elements:
                        # No more listings found
                        break
                    
                    # Parse listings from this page (reuse same parsing logic)
                    for i, element in enumerate(next_listing_elements[:limit - len(listings)]):
                        try:
                            seller_name = (
                                extract_text(element, "[class*='seller-name']") or
                                extract_text(element, "[class*='SellerName']") or
                                extract_text(element, ".seller") or
                                extract_text(element, "[data-seller-name]") or
                                extract_attr(element, "data-seller-name") or
                                None
                            )
                            
                            if not seller_name or len(seller_name.strip()) < 2:
                                continue
                            
                            price_text = (
                                extract_text(element, "[class*='price']") or
                                extract_text(element, "[class*='Price']") or
                                extract_text(element, "[data-price]") or
                                extract_attr(element, "data-price") or
                                None
                            )
                            
                            if not price_text:
                                price_elem = element.css_first("[class*='price'], [class*='Price'], [data-price]")
                                if price_elem:
                                    price_text = price_elem.text(strip=True) or price_elem.attributes.get("data-price")
                            
                            price = clean_price(price_text) if price_text else None
                            
                            if not price or price <= 0:
                                full_text = element.text(strip=True)
                                price_match = re.search(r'\$?\s*(\d+\.?\d*)', full_text)
                                if price_match:
                                    try:
                                        price = float(price_match.group(1))
                                    except (ValueError, AttributeError):
                                        continue
                                else:
                                    continue
                            
                            condition_text = (
                                extract_text(element, "[class*='condition']") or
                                extract_text(element, "[class*='Condition']") or
                                extract_text(element, "[data-condition]") or
                                extract_attr(element, "data-condition") or
                                ""
                            )
                            
                            if not condition_text:
                                full_text_lower = element.text(strip=True).lower()
                                if "near mint" in full_text_lower or "nm" in full_text_lower:
                                    condition_text = "Near Mint"
                                elif "lightly played" in full_text_lower or "lp" in full_text_lower:
                                    condition_text = "Lightly Played"
                                elif "moderately played" in full_text_lower or "mp" in full_text_lower:
                                    condition_text = "Moderately Played"
                                elif "heavily played" in full_text_lower or "hp" in full_text_lower:
                                    condition_text = "Heavily Played"
                                elif "damaged" in full_text_lower or "dmg" in full_text_lower:
                                    condition_text = "Damaged"
                            
                            condition = self.normalize_condition(condition_text) if condition_text else "NM"
                            
                            qty_text = (
                                extract_text(element, "[class*='quantity']") or
                                extract_text(element, "[class*='Quantity']") or
                                extract_text(element, "[data-quantity]") or
                                extract_attr(element, "data-quantity") or
                                "1"
                            )
                            
                            quantity = 1
                            if qty_text:
                                qty_match = re.search(r'(\d+)', qty_text)
                                if qty_match:
                                    try:
                                        quantity = int(qty_match.group(1))
                                    except (ValueError, AttributeError):
                                        quantity = 1
                            
                            rating_text = (
                                extract_text(element, "[class*='rating']") or
                                extract_text(element, "[class*='Rating']") or
                                extract_attr(element, "data-rating") or
                                None
                            )
                            seller_rating = None
                            if rating_text:
                                rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                                if rating_match:
                                    try:
                                        seller_rating = float(rating_match.group(1))
                                        if seller_rating > 5.0:
                                            seller_rating = seller_rating / 10.0
                                    except (ValueError, AttributeError):
                                        pass
                            
                            full_text_lower = element.text(strip=True).lower()
                            is_foil = (
                                "foil" in full_text_lower or
                                element.css_first("[class*='foil'], [data-foil='true']") is not None
                            )
                            
                            external_id = (
                                extract_attr(element, "data-listing-id") or
                                extract_attr(element, "data-id") or
                                f"tcgplayer-{hash(f'{seller_name}-{price}-{condition}-{len(listings) + i}')}"
                            )
                            
                            listing = CardListing(
                                card_name=card_name,
                                set_code=set_code or "",
                                collector_number="",
                                price=price,
                                currency="USD",
                                quantity=quantity,
                                condition=condition,
                                language="English",
                                is_foil=is_foil,
                                seller_name=seller_name.strip() if seller_name else None,
                                seller_rating=seller_rating,
                                external_id=external_id,
                                listing_url=paginated_url,
                                scraped_at=datetime.utcnow(),
                            )
                            
                            listings.append(listing)
                            
                        except Exception as e:
                            logger.debug("Failed to parse listing element", error=str(e))
                            continue
                    
                    page_num += 1
            
            logger.info("Scraped TCGPlayer listings", card_name=card_name, count=len(listings))
            
        except Exception as e:
            logger.error("Error scraping TCGPlayer listings", card_name=card_name, error=str(e))
        
        return listings[:limit]
    
    async def fetch_price(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
    ) -> CardPrice | None:
        """
        Fetch TCGPlayer price data via Scryfall.
        
        Scryfall aggregates TCGPlayer prices (usd, usd_foil fields).
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
            logger.debug("No TCGPlayer price", card_name=card_name, set_code=set_code)
            return None
        
        return CardPrice(
            card_name=data.get("name", card_name),
            set_code=data.get("set", set_code).upper() if data.get("set") else set_code,
            collector_number=data.get("collector_number", collector_number),
            scryfall_id=data.get("id", scryfall_id),
            price=float(price_usd),
            currency="USD",
            price_foil=float(price_foil) if price_foil else None,
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
