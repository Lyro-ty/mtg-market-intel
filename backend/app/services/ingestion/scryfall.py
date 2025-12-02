"""
Scryfall adapter for card data and reference information.

Scryfall is not a marketplace but provides canonical card data
and basic price information from major marketplaces.
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


class ScryfallAdapter(MarketplaceAdapter):
    """
    Adapter for Scryfall API.
    
    Provides canonical card data and aggregated prices from
    TCGPlayer and Cardmarket.
    """
    
    def __init__(self, config: AdapterConfig | None = None):
        if config is None:
            config = AdapterConfig(
                base_url=settings.scryfall_base_url,
                api_url=settings.scryfall_base_url,
                rate_limit_seconds=settings.scryfall_rate_limit_ms / 1000,
            )
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
    
    @property
    def marketplace_name(self) -> str:
        return "Scryfall"
    
    @property
    def marketplace_slug(self) -> str:
        return "scryfall"
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout_seconds,
                headers={"User-Agent": self.config.user_agent},
            )
        return self._client
    
    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        if self._last_request_time is not None:
            elapsed = (datetime.utcnow() - self._last_request_time).total_seconds()
            if elapsed < self.config.rate_limit_seconds:
                await asyncio.sleep(self.config.rate_limit_seconds - elapsed)
        self._last_request_time = datetime.utcnow()
    
    async def _request(self, endpoint: str, params: dict | None = None) -> dict | None:
        """Make a rate-limited request to the API."""
        await self._rate_limit()
        client = await self._get_client()
        
        try:
            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error("Scryfall API error", endpoint=endpoint, status=e.response.status_code)
            raise
        except Exception as e:
            logger.error("Scryfall request failed", endpoint=endpoint, error=str(e))
            raise
    
    async def fetch_listings(
        self,
        card_name: str | None = None,
        set_code: str | None = None,
        scryfall_id: str | None = None,
        limit: int = 100,
    ) -> list[CardListing]:
        """
        Scryfall doesn't provide individual listings.
        Returns empty list as this is not supported.
        """
        return []
    
    async def fetch_price(
        self,
        card_name: str,
        set_code: str,
        collector_number: str | None = None,
        scryfall_id: str | None = None,
    ) -> CardPrice | None:
        """Fetch price data for a card from Scryfall."""
        # Try to fetch by Scryfall ID first
        if scryfall_id:
            data = await self._request(f"/cards/{scryfall_id}")
            if data:
                return self._parse_price_data(data)
        
        # Try by set and collector number
        if set_code and collector_number:
            data = await self._request(f"/cards/{set_code.lower()}/{collector_number}")
            if data:
                return self._parse_price_data(data)
        
        # Search by name and set
        query = f'!"{card_name}"'
        if set_code:
            query += f" set:{set_code.lower()}"
        
        data = await self._request("/cards/search", params={"q": query})
        if data and data.get("data"):
            return self._parse_price_data(data["data"][0])
        
        return None
    
    async def search_cards(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search for cards using Scryfall's search."""
        data = await self._request("/cards/search", params={"q": query})
        if not data or not data.get("data"):
            return []
        
        results = []
        for card in data["data"][:limit]:
            results.append(self._normalize_card_data(card))
        
        return results
    
    async def fetch_card_by_id(self, scryfall_id: str) -> dict | None:
        """Fetch a single card by Scryfall ID."""
        data = await self._request(f"/cards/{scryfall_id}")
        if data:
            return self._normalize_card_data(data)
        return None
    
    async def fetch_cards_bulk(self, identifiers: list[dict]) -> list[dict]:
        """
        Fetch multiple cards in a single request.
        
        Args:
            identifiers: List of card identifiers, each a dict with
                         'id', 'name', or 'set'+'collector_number'.
        
        Returns:
            List of normalized card data.
        """
        await self._rate_limit()
        client = await self._get_client()
        
        try:
            response = await client.post(
                "/cards/collection",
                json={"identifiers": identifiers},
            )
            response.raise_for_status()
            data = response.json()
            
            return [self._normalize_card_data(card) for card in data.get("data", [])]
        except Exception as e:
            logger.error("Scryfall bulk request failed", error=str(e))
            raise
    
    async def fetch_set_cards(self, set_code: str) -> list[dict]:
        """Fetch all cards from a specific set."""
        cards = []
        endpoint = f"/cards/search"
        params = {"q": f"set:{set_code.lower()}", "order": "set"}
        
        while endpoint:
            data = await self._request(endpoint, params=params if not endpoint.startswith("http") else None)
            if not data:
                break
            
            cards.extend([self._normalize_card_data(c) for c in data.get("data", [])])
            
            if data.get("has_more"):
                endpoint = data.get("next_page", "").replace(self.config.base_url, "")
                params = None  # Next page URL includes params
            else:
                endpoint = None
        
        return cards
    
    async def fetch_bulk_data_url(self, data_type: str = "default_cards") -> str | None:
        """
        Get URL for bulk data download.
        
        Args:
            data_type: Type of bulk data (default_cards, oracle_cards, etc.)
            
        Returns:
            Download URL or None.
        """
        data = await self._request("/bulk-data")
        if not data:
            return None
        
        for item in data.get("data", []):
            if item.get("type") == data_type:
                return item.get("download_uri")
        
        return None
    
    def _parse_price_data(self, card_data: dict) -> CardPrice:
        """Parse Scryfall card data into CardPrice."""
        prices = card_data.get("prices", {})
        
        # Get USD prices (prefer TCGPlayer)
        price_usd = prices.get("usd")
        price_foil = prices.get("usd_foil")
        
        return CardPrice(
            card_name=card_data.get("name", ""),
            set_code=card_data.get("set", "").upper(),
            collector_number=card_data.get("collector_number", ""),
            scryfall_id=card_data.get("id"),
            price=float(price_usd) if price_usd else 0.0,
            currency="USD",
            price_foil=float(price_foil) if price_foil else None,
            snapshot_time=datetime.utcnow(),
        )
    
    def _parse_all_price_data(self, card_data: dict) -> list[CardPrice]:
        """
        Parse all marketplace prices from Scryfall card data.
        
        Scryfall provides prices from multiple marketplaces:
        - usd/usd_foil: TCGPlayer (USD)
        - eur/eur_foil: Cardmarket (EUR)
        - tix: MTGO (tix)
        
        Returns a list of CardPrice objects, one per marketplace/currency.
        """
        prices = card_data.get("prices", {})
        price_list = []
        
        # TCGPlayer prices (USD)
        price_usd = prices.get("usd")
        price_usd_foil = prices.get("usd_foil")
        if price_usd:
            price_list.append(CardPrice(
                card_name=card_data.get("name", ""),
                set_code=card_data.get("set", "").upper(),
                collector_number=card_data.get("collector_number", ""),
                scryfall_id=card_data.get("id"),
                price=float(price_usd),
                currency="USD",
                price_foil=float(price_usd_foil) if price_usd_foil else None,
                snapshot_time=datetime.utcnow(),
            ))
        
        # Cardmarket prices (EUR)
        price_eur = prices.get("eur")
        price_eur_foil = prices.get("eur_foil")
        if price_eur:
            price_list.append(CardPrice(
                card_name=card_data.get("name", ""),
                set_code=card_data.get("set", "").upper(),
                collector_number=card_data.get("collector_number", ""),
                scryfall_id=card_data.get("id"),
                price=float(price_eur),
                currency="EUR",
                price_foil=float(price_eur_foil) if price_eur_foil else None,
                snapshot_time=datetime.utcnow(),
            ))
        
        # MTGO prices (tix) - less common but useful
        price_tix = prices.get("tix")
        if price_tix:
            price_list.append(CardPrice(
                card_name=card_data.get("name", ""),
                set_code=card_data.get("set", "").upper(),
                collector_number=card_data.get("collector_number", ""),
                scryfall_id=card_data.get("id"),
                price=float(price_tix),
                currency="TIX",
                snapshot_time=datetime.utcnow(),
            ))
        
        return price_list
    
    def _normalize_card_data(self, card: dict) -> dict:
        """Normalize Scryfall card data to our schema."""
        # Handle double-faced cards
        image_uris = card.get("image_uris", {})
        if not image_uris and card.get("card_faces"):
            image_uris = card["card_faces"][0].get("image_uris", {})
        
        # Parse colors as JSON string
        colors = card.get("colors", [])
        color_identity = card.get("color_identity", [])
        
        # Parse legalities
        legalities = card.get("legalities", {})
        
        return {
            "scryfall_id": card.get("id"),
            "oracle_id": card.get("oracle_id"),
            "name": card.get("name"),
            "set_code": card.get("set", "").upper(),
            "set_name": card.get("set_name"),
            "collector_number": card.get("collector_number"),
            "rarity": card.get("rarity"),
            "mana_cost": card.get("mana_cost"),
            "cmc": card.get("cmc"),
            "type_line": card.get("type_line"),
            "oracle_text": card.get("oracle_text"),
            "colors": str(colors) if colors else None,
            "color_identity": str(color_identity) if color_identity else None,
            "power": card.get("power"),
            "toughness": card.get("toughness"),
            "legalities": str(legalities) if legalities else None,
            "image_url": image_uris.get("normal"),
            "image_url_small": image_uris.get("small"),
            "image_url_large": image_uris.get("large") or image_uris.get("png"),
            "released_at": card.get("released_at"),
            "prices": card.get("prices", {}),
        }
    
    async def health_check(self) -> bool:
        """Check if Scryfall API is reachable."""
        try:
            data = await self._request("/cards/random")
            return data is not None
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

