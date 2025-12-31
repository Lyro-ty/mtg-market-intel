"""HTTP client for backend API communication."""
from decimal import Decimal
from typing import Any, Optional
from dataclasses import dataclass
from datetime import datetime

import aiohttp
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class User:
    """User data from the backend."""
    user_id: int
    username: str
    display_name: Optional[str]
    discord_alerts_enabled: bool


@dataclass
class PortfolioCard:
    """Card in portfolio."""
    card_id: int
    name: str
    set_code: str
    quantity: int
    current_price: Decimal
    total_value: Decimal


@dataclass
class Portfolio:
    """Portfolio summary."""
    total_value: Decimal
    total_cards: int
    unique_cards: int
    change_24h: Optional[Decimal]
    change_24h_pct: Optional[float]
    top_cards: list[PortfolioCard]


@dataclass
class WantListItem:
    """Want list item."""
    card_id: int
    name: str
    set_code: str
    target_price: Optional[Decimal]
    current_price: Optional[Decimal]
    alert_triggered: bool


@dataclass
class WantList:
    """Want list summary."""
    total_items: int
    items_with_alerts: int
    alerts_triggered: int
    items: list[WantListItem]


@dataclass
class PendingAlert:
    """Alert pending delivery."""
    alert_id: int
    user_id: int
    discord_id: str
    alert_type: str
    title: str
    message: str
    card_id: Optional[int]
    card_name: Optional[str]
    current_price: Optional[Decimal]
    created_at: datetime


@dataclass
class CardPrice:
    """Card price info."""
    card_id: int
    name: str
    set_code: str
    set_name: str
    price_usd: Optional[Decimal]
    price_usd_foil: Optional[Decimal]
    change_24h_pct: Optional[float]
    scryfall_uri: Optional[str]
    image_uri: Optional[str]


@dataclass
class MarketMover:
    """Market mover card."""
    card_id: int
    name: str
    set_code: str
    price: Decimal
    change_pct: float
    direction: str  # "up" or "down"


class APIClient:
    """Async HTTP client for backend API."""

    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "X-Bot-Token": self.api_token,
                    "Content-Type": "application/json",
                }
            )
        return self._session

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> dict[str, Any]:
        """Make an HTTP request to the backend."""
        session = await self._get_session()
        url = f"{self.base_url}/api{path}"

        try:
            async with session.request(method, url, **kwargs) as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error("API request failed", url=url, error=str(e))
            raise

    async def get_user_by_discord_id(self, discord_id: str) -> Optional[User]:
        """Look up a user by their Discord ID."""
        data = await self._request("GET", f"/bot/users/by-discord/{discord_id}")
        if not data:
            return None
        return User(
            user_id=data["user_id"],
            username=data["username"],
            display_name=data.get("display_name"),
            discord_alerts_enabled=data["discord_alerts_enabled"],
        )

    async def get_portfolio(self, user_id: int) -> Optional[Portfolio]:
        """Get a user's portfolio summary."""
        data = await self._request("GET", f"/bot/users/{user_id}/portfolio")
        if not data:
            return None

        top_cards = [
            PortfolioCard(
                card_id=c["card_id"],
                name=c["name"],
                set_code=c["set_code"],
                quantity=c["quantity"],
                current_price=Decimal(str(c["current_price"])),
                total_value=Decimal(str(c["total_value"])),
            )
            for c in data.get("top_cards", [])
        ]

        return Portfolio(
            total_value=Decimal(str(data["total_value"])),
            total_cards=data["total_cards"],
            unique_cards=data["unique_cards"],
            change_24h=Decimal(str(data["change_24h"])) if data.get("change_24h") else None,
            change_24h_pct=data.get("change_24h_pct"),
            top_cards=top_cards,
        )

    async def get_wantlist(self, user_id: int, limit: int = 10) -> Optional[WantList]:
        """Get a user's want list."""
        data = await self._request("GET", f"/bot/users/{user_id}/wantlist", params={"limit": limit})
        if not data:
            return None

        items = [
            WantListItem(
                card_id=i["card_id"],
                name=i["name"],
                set_code=i["set_code"],
                target_price=Decimal(str(i["target_price"])) if i.get("target_price") else None,
                current_price=Decimal(str(i["current_price"])) if i.get("current_price") else None,
                alert_triggered=i.get("alert_triggered", False),
            )
            for i in data.get("items", [])
        ]

        return WantList(
            total_items=data["total_items"],
            items_with_alerts=data["items_with_alerts"],
            alerts_triggered=data["alerts_triggered"],
            items=items,
        )

    async def get_pending_alerts(self, limit: int = 50) -> list[PendingAlert]:
        """Get pending Discord alerts."""
        data = await self._request("GET", "/bot/alerts/pending", params={"limit": limit})
        if not data:
            return []

        return [
            PendingAlert(
                alert_id=a["alert_id"],
                user_id=a["user_id"],
                discord_id=a["discord_id"],
                alert_type=a["alert_type"],
                title=a["title"],
                message=a["message"],
                card_id=a.get("card_id"),
                card_name=a.get("card_name"),
                current_price=Decimal(str(a["current_price"])) if a.get("current_price") else None,
                created_at=datetime.fromisoformat(a["created_at"].replace("Z", "+00:00")),
            )
            for a in data
        ]

    async def mark_alerts_delivered(self, alert_ids: list[int]) -> int:
        """Mark alerts as delivered."""
        data = await self._request(
            "POST",
            "/bot/alerts/delivered",
            json={"alert_ids": alert_ids},
        )
        return data.get("marked", 0) if data else 0

    async def mark_alert_failed(self, alert_id: int, error: str) -> None:
        """Mark an alert as failed."""
        await self._request(
            "POST",
            f"/bot/alerts/{alert_id}/failed",
            params={"error": error},
        )

    async def search_cards(self, query: str, limit: int = 5) -> list[CardPrice]:
        """Search for cards by name."""
        data = await self._request(
            "GET",
            "/search/cards",
            params={"q": query, "limit": limit},
        )
        if not data or "results" not in data:
            return []

        return [
            CardPrice(
                card_id=c["id"],
                name=c["name"],
                set_code=c.get("set_code", ""),
                set_name=c.get("set_name", ""),
                price_usd=Decimal(str(c["price_usd"])) if c.get("price_usd") else None,
                price_usd_foil=Decimal(str(c["price_usd_foil"])) if c.get("price_usd_foil") else None,
                change_24h_pct=c.get("change_24h_pct"),
                scryfall_uri=c.get("scryfall_uri"),
                image_uri=c.get("image_uris", {}).get("normal") if c.get("image_uris") else None,
            )
            for c in data["results"]
        ]

    async def get_card_price(self, card_id: int) -> Optional[CardPrice]:
        """Get price for a specific card."""
        data = await self._request("GET", f"/cards/{card_id}")
        if not data:
            return None

        return CardPrice(
            card_id=data["id"],
            name=data["name"],
            set_code=data.get("set_code", ""),
            set_name=data.get("set_name", ""),
            price_usd=Decimal(str(data["price_usd"])) if data.get("price_usd") else None,
            price_usd_foil=Decimal(str(data["price_usd_foil"])) if data.get("price_usd_foil") else None,
            change_24h_pct=data.get("change_24h_pct"),
            scryfall_uri=data.get("scryfall_uri"),
            image_uri=data.get("image_uris", {}).get("normal") if data.get("image_uris") else None,
        )

    async def get_top_movers(self, direction: str = "up", limit: int = 5) -> list[MarketMover]:
        """Get top gaining or losing cards."""
        data = await self._request(
            "GET",
            "/market/movers",
            params={"direction": direction, "limit": limit},
        )
        if not data:
            return []

        movers_key = "gainers" if direction == "up" else "losers"
        movers = data.get(movers_key, [])

        return [
            MarketMover(
                card_id=m["card_id"],
                name=m["name"],
                set_code=m.get("set_code", ""),
                price=Decimal(str(m["current_price"])) if m.get("current_price") else Decimal("0"),
                change_pct=m.get("change_pct", 0),
                direction=direction,
            )
            for m in movers
        ]
