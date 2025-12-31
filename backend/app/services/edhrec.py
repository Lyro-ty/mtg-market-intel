"""
EDHREC Integration Service.

Fetches Commander popularity data from EDHREC's public JSON API.
This data helps users understand card demand in the Commander format.
"""
import asyncio
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)


class EDHRECClient:
    """
    Client for EDHREC's public JSON API.

    EDHREC provides popularity data for Commander format:
    - Top commanders
    - Card usage statistics
    - Synergy scores
    """

    BASE_URL = "https://json.edhrec.com"
    TIMEOUT = 30.0
    RATE_LIMIT_SECONDS = 1.0  # Be respectful

    def __init__(self):
        self._last_request_time = 0.0

    async def _rate_limit(self):
        """Ensure we don't hit EDHREC too frequently."""
        import time
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.RATE_LIMIT_SECONDS:
            await asyncio.sleep(self.RATE_LIMIT_SECONDS - elapsed)
        self._last_request_time = time.time()

    async def _get(self, path: str) -> Optional[dict]:
        """Make a GET request to EDHREC."""
        await self._rate_limit()

        url = f"{self.BASE_URL}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                response = await client.get(url)

                if response.status_code == 404:
                    logger.debug("EDHREC resource not found", path=path)
                    return None

                response.raise_for_status()
                return response.json()

        except httpx.TimeoutException:
            logger.warning("EDHREC request timed out", path=path)
            return None
        except httpx.HTTPStatusError as e:
            logger.warning("EDHREC HTTP error", path=path, status=e.response.status_code)
            return None
        except Exception as e:
            logger.error("EDHREC request failed", path=path, error=str(e))
            return None

    async def get_top_commanders(self, limit: int = 100) -> list[dict]:
        """
        Get the most popular commanders.

        Returns:
            List of commander data with name, color identity, deck count, etc.
        """
        data = await self._get("/top/commanders.json")
        if not data:
            return []

        commanders = data.get("container", {}).get("json_dict", {}).get("cardlists", [])
        if not commanders:
            # Fallback to different structure
            commanders = data.get("commanders", [])

        result = []
        for cmd in commanders[:limit]:
            result.append({
                "name": cmd.get("name"),
                "color_identity": cmd.get("color_identity", []),
                "num_decks": cmd.get("num_decks", 0),
                "rank": cmd.get("rank"),
                "url": cmd.get("url"),
            })

        logger.info("Fetched top commanders from EDHREC", count=len(result))
        return result

    async def get_card_data(self, card_name: str) -> Optional[dict]:
        """
        Get EDHREC data for a specific card.

        Args:
            card_name: The card name to look up

        Returns:
            Card data including usage stats, synergies, etc.
        """
        # EDHREC uses URL-friendly slugs
        slug = self._name_to_slug(card_name)
        data = await self._get(f"/cards/{slug}.json")

        if not data:
            return None

        card_info = data.get("container", {}).get("json_dict", {}).get("card", {})
        if not card_info:
            card_info = data.get("card", {})

        return {
            "name": card_info.get("name", card_name),
            "num_decks": card_info.get("num_decks", 0),
            "rank": card_info.get("rank"),
            "potential_decks": card_info.get("potential_decks", 0),
            "inclusion_rate": self._calculate_inclusion_rate(card_info),
            "synergies": self._extract_synergies(data),
        }

    async def get_commander_cards(self, commander_name: str) -> Optional[dict]:
        """
        Get recommended cards for a specific commander.

        Args:
            commander_name: The commander name

        Returns:
            Lists of recommended cards with synergy scores
        """
        slug = self._name_to_slug(commander_name)
        data = await self._get(f"/commanders/{slug}.json")

        if not data:
            return None

        cardlists = data.get("container", {}).get("json_dict", {}).get("cardlists", [])

        result = {
            "commander": commander_name,
            "high_synergy": [],
            "top_cards": [],
            "new_cards": [],
        }

        for cardlist in cardlists:
            header = cardlist.get("header", "").lower()
            cards = cardlist.get("cardviews", [])

            if "high synergy" in header:
                result["high_synergy"] = [
                    {"name": c.get("name"), "synergy": c.get("synergy_score", 0)}
                    for c in cards[:20]
                ]
            elif "top cards" in header:
                result["top_cards"] = [
                    {"name": c.get("name"), "inclusion": c.get("inclusion", 0)}
                    for c in cards[:20]
                ]
            elif "new cards" in header:
                result["new_cards"] = [
                    {"name": c.get("name")}
                    for c in cards[:10]
                ]

        return result

    async def get_staples(self, colors: str = "") -> list[dict]:
        """
        Get Commander staple cards, optionally filtered by color.

        Args:
            colors: Color identity filter (e.g., "WU" for Azorius)

        Returns:
            List of staple cards with usage data
        """
        if colors:
            slug = "".join(sorted(colors.upper()))
            data = await self._get(f"/combos/{slug}.json")
        else:
            data = await self._get("/top/cards.json")

        if not data:
            return []

        cardlists = data.get("container", {}).get("json_dict", {}).get("cardlists", [])

        staples = []
        for cardlist in cardlists:
            for card in cardlist.get("cardviews", []):
                staples.append({
                    "name": card.get("name"),
                    "num_decks": card.get("num_decks", 0),
                    "inclusion": card.get("inclusion", 0),
                })

        return staples[:100]

    def _name_to_slug(self, name: str) -> str:
        """Convert a card name to EDHREC's URL slug format."""
        # Remove special characters, lowercase, replace spaces with hyphens
        slug = name.lower()
        slug = slug.replace("'", "")
        slug = slug.replace(",", "")
        slug = slug.replace(":", "")
        slug = slug.replace("!", "")
        slug = slug.replace("?", "")
        slug = slug.replace(" ", "-")
        slug = slug.replace("--", "-")
        return slug

    def _calculate_inclusion_rate(self, card_info: dict) -> float:
        """Calculate what percentage of eligible decks run this card."""
        num_decks = card_info.get("num_decks", 0)
        potential = card_info.get("potential_decks", 0)
        if potential > 0:
            return round(num_decks / potential * 100, 1)
        return 0.0

    def _extract_synergies(self, data: dict) -> list[dict]:
        """Extract synergy cards from card data."""
        synergies = []
        cardlists = data.get("container", {}).get("json_dict", {}).get("cardlists", [])

        for cardlist in cardlists:
            if "synergy" in cardlist.get("header", "").lower():
                for card in cardlist.get("cardviews", [])[:10]:
                    synergies.append({
                        "name": card.get("name"),
                        "synergy_score": card.get("synergy_score", 0),
                    })
                break

        return synergies


# Singleton instance
edhrec_client = EDHRECClient()
