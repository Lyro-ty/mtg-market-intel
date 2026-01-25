"""
Card Kingdom Buylist Adapter.

Scrapes buylist prices from Card Kingdom's purchasing page.
Note: Card Kingdom doesn't have a public API for buylist, so we scrape their HTML.

Respect rate limits: 2 second delay between requests.
"""
import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from bs4 import BeautifulSoup

from app.core.config import settings

logger = structlog.get_logger()


@dataclass
class BuylistPrice:
    """Buylist price data for a card."""
    card_name: str
    set_code: str
    vendor: str = "cardkingdom"
    condition: str = "NM"
    is_foil: bool = False
    price: float = 0.0
    credit_price: float | None = None
    quantity: int | None = None
    fetched_at: datetime | None = None

    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = datetime.now(timezone.utc)


class CardKingdomBuylistAdapter:
    """
    Card Kingdom buylist scraper.

    Scrapes buylist prices from Card Kingdom's purchasing page.
    Rate limit: 2 seconds between requests (be respectful).

    Usage:
        adapter = CardKingdomBuylistAdapter()
        prices = await adapter.get_buylist_prices("Black Lotus", "LEA")
        await adapter.close()
    """

    BASE_URL = "https://www.cardkingdom.com"
    RATE_LIMIT_SECONDS = 2.0

    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._last_request_time: datetime | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(float(settings.external_api_timeout)),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
                follow_redirects=True,
            )
        return self._client

    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        if self._last_request_time is not None:
            elapsed = (datetime.now(timezone.utc) - self._last_request_time).total_seconds()
            if elapsed < self.RATE_LIMIT_SECONDS:
                await asyncio.sleep(self.RATE_LIMIT_SECONDS - elapsed)
        self._last_request_time = datetime.now(timezone.utc)

    async def get_buylist_prices(
        self,
        card_name: str,
        set_code: str | None = None,
    ) -> list[BuylistPrice]:
        """
        Fetch buylist prices for a card from Card Kingdom.

        Args:
            card_name: Card name to search for
            set_code: Optional set code to filter results

        Returns:
            List of BuylistPrice objects (one per condition/foil variant)
        """
        await self._rate_limit()
        client = await self._get_client()

        # Search Card Kingdom's purchasing (buylist) page
        search_query = card_name
        if set_code:
            search_query = f"{card_name} [{set_code}]"

        search_url = f"{self.BASE_URL}/purchasing/search"
        params = {"filter[search]": search_query}

        try:
            response = await client.get(search_url, params=params)
            response.raise_for_status()

            return self._parse_buylist_page(response.text, card_name, set_code)

        except httpx.HTTPStatusError as e:
            logger.warning(
                "Card Kingdom buylist request failed",
                status=e.response.status_code,
                card_name=card_name,
            )
            return []
        except Exception as e:
            logger.error(
                "Card Kingdom buylist error",
                card_name=card_name,
                error=str(e),
            )
            return []

    def _parse_buylist_page(
        self,
        html: str,
        card_name: str,
        set_code: str | None,
    ) -> list[BuylistPrice]:
        """Parse buylist prices from Card Kingdom HTML."""
        soup = BeautifulSoup(html, "html.parser")
        prices = []

        # Card Kingdom uses a table-like structure for buylist items
        # Look for product items in the purchasing page
        product_items = soup.select(".productItemWrapper, .itemContentWrapper, .mainListing")

        if not product_items:
            # Try alternative selectors
            product_items = soup.select("[data-product-id], .product-info")

        for item in product_items:
            try:
                # Extract card name from the item
                name_elem = item.select_one(".productDetailTitle, .itemTitle, a.productDetailLink")
                if not name_elem:
                    continue

                item_name = name_elem.get_text(strip=True)

                # Skip if name doesn't match (basic fuzzy matching)
                if card_name.lower() not in item_name.lower():
                    continue

                # Extract set info
                set_elem = item.select_one(".productDetailSet, .itemSet, .setInfo")
                item_set = set_elem.get_text(strip=True) if set_elem else ""

                # If we have a set filter, check it matches
                if set_code and set_code.upper() not in item_set.upper():
                    # Try extracting set code from brackets like [LEA]
                    set_match = re.search(r'\[([A-Z0-9]+)\]', item_set)
                    if set_match:
                        if set_match.group(1).upper() != set_code.upper():
                            continue
                    else:
                        continue

                # Determine set_code from the item
                found_set = set_code or ""
                set_match = re.search(r'\[([A-Z0-9]+)\]', item_set)
                if set_match:
                    found_set = set_match.group(1)

                # Check if foil
                is_foil = "foil" in item_name.lower() or "foil" in item.get_text().lower()

                # Extract buylist prices
                # Card Kingdom shows cash price and sometimes credit price
                price_elems = item.select(".sellPrice, .buylistPrice, .price")

                cash_price = 0.0
                credit_price = None

                for price_elem in price_elems:
                    price_text = price_elem.get_text(strip=True)
                    # Extract dollar amount
                    price_match = re.search(r'\$?([\d,]+\.?\d*)', price_text)
                    if price_match:
                        try:
                            price_val = float(price_match.group(1).replace(",", ""))
                            if "credit" in price_text.lower():
                                credit_price = price_val
                            else:
                                cash_price = max(cash_price, price_val)
                        except (ValueError, TypeError):
                            # Skip malformed price values
                            continue

                if cash_price <= 0:
                    continue

                # Extract quantity if available
                qty_elem = item.select_one(".qty, .quantity, [data-qty]")
                quantity = None
                if qty_elem:
                    qty_text = qty_elem.get_text(strip=True)
                    qty_match = re.search(r'(\d+)', qty_text)
                    if qty_match:
                        quantity = int(qty_match.group(1))

                # Create price entries for different conditions
                # Card Kingdom typically buys NM, LP, MP, HP
                conditions = self._parse_conditions(item)

                if not conditions:
                    # Default to NM if we can't parse conditions
                    conditions = [("NM", cash_price, credit_price)]

                for condition, cond_price, cond_credit in conditions:
                    if cond_price > 0:
                        prices.append(BuylistPrice(
                            card_name=item_name.split(" - ")[0].strip(),  # Remove variant info
                            set_code=found_set,
                            condition=condition,
                            is_foil=is_foil,
                            price=cond_price,
                            credit_price=cond_credit,
                            quantity=quantity,
                        ))

            except Exception as e:
                logger.debug(
                    "Error parsing Card Kingdom buylist item",
                    error=str(e),
                )
                continue

        logger.debug(
            "Card Kingdom buylist parsed",
            card_name=card_name,
            prices_found=len(prices),
        )

        return prices

    def _parse_conditions(
        self,
        item: Any,
    ) -> list[tuple[str, float, float | None]]:
        """
        Parse condition-specific prices from a buylist item.

        Returns list of (condition, cash_price, credit_price) tuples.
        """
        conditions = []

        # Look for condition rows/tabs
        condition_elems = item.select(".conditionRow, .condition-price, [data-condition]")

        for elem in condition_elems:
            text = elem.get_text(strip=True).upper()

            # Determine condition
            if "NM" in text or "NEAR MINT" in text:
                cond = "NM"
            elif "LP" in text or "LIGHTLY" in text:
                cond = "LP"
            elif "MP" in text or "MODERATELY" in text:
                cond = "MP"
            elif "HP" in text or "HEAVILY" in text:
                cond = "HP"
            else:
                continue

            # Extract price
            price_match = re.search(r'\$?([\d,]+\.?\d*)', text)
            if price_match:
                try:
                    price = float(price_match.group(1).replace(",", ""))
                    conditions.append((cond, price, None))
                except (ValueError, TypeError):
                    # Skip malformed price values
                    continue

        return conditions

    async def get_bulk_buylist_prices(
        self,
        cards: list[tuple[str, str]],  # (card_name, set_code)
    ) -> list[BuylistPrice]:
        """
        Fetch buylist prices for multiple cards.

        Args:
            cards: List of (card_name, set_code) tuples

        Returns:
            Combined list of all buylist prices found
        """
        all_prices = []

        for card_name, set_code in cards:
            prices = await self.get_buylist_prices(card_name, set_code)
            all_prices.extend(prices)

            # Rate limiting is handled in get_buylist_prices

        return all_prices

    async def close(self) -> None:
        """Cleanup HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
