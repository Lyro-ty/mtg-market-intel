"""Condition-based pricing service using TCGPlayer or multipliers."""
import logging
from typing import Optional

import httpx

from app.services.pricing.valuation import ConditionMultiplier

logger = logging.getLogger(__name__)

TCGPLAYER_API_URL = "https://api.tcgplayer.com/v1.39.0"
PRICE_THRESHOLD = 5.00  # Use TCGPlayer for cards above this price


class ConditionPricer:
    """Get condition-specific prices from TCGPlayer or calculate from multipliers."""

    # Map TCGPlayer condition names to our enum values
    CONDITION_MAP = {
        "Near Mint": "NEAR_MINT",
        "Lightly Played": "LIGHTLY_PLAYED",
        "Moderately Played": "MODERATELY_PLAYED",
        "Heavily Played": "HEAVILY_PLAYED",
        "Damaged": "DAMAGED",
    }

    def __init__(self, tcgplayer_api_key: Optional[str] = None):
        self.api_key = tcgplayer_api_key
        self._access_token: Optional[str] = None

    def should_use_tcgplayer(self, nm_price: float) -> bool:
        """Determine if TCGPlayer API should be used based on card value."""
        return nm_price > PRICE_THRESHOLD and self.api_key is not None

    def calculate_condition_prices_from_multipliers(
        self, nm_price: float
    ) -> dict[str, float]:
        """Calculate prices for all conditions using standard multipliers."""
        return {
            condition: nm_price * multiplier
            for condition, multiplier in ConditionMultiplier.MULTIPLIERS.items()
        }

    async def get_tcgplayer_prices(
        self, tcgplayer_product_id: int
    ) -> dict[str, float]:
        """Fetch condition prices from TCGPlayer API."""
        response = await self._fetch_tcgplayer_prices(tcgplayer_product_id)

        prices = {}
        for result in response.get("results", []):
            condition_name = result.get("subTypeName")
            market_price = result.get("marketPrice")

            if condition_name in self.CONDITION_MAP and market_price:
                our_condition = self.CONDITION_MAP[condition_name]
                prices[our_condition] = float(market_price)

        return prices

    async def _fetch_tcgplayer_prices(self, product_id: int) -> dict:
        """Make API call to TCGPlayer for pricing data."""
        if not self.api_key:
            raise ValueError("TCGPlayer API key not configured")

        # Ensure we have valid access token
        if not self._access_token:
            await self._authenticate()

        url = f"{TCGPLAYER_API_URL}/pricing/product/{product_id}"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    async def _authenticate(self) -> None:
        """Authenticate with TCGPlayer OAuth2."""
        if not self.api_key:
            raise ValueError("TCGPlayer API key not configured")

        # TCGPlayer uses client_id:client_secret format
        parts = self.api_key.split(":")
        if len(parts) != 2:
            raise ValueError("TCGPlayer API key should be in format 'client_id:client_secret'")

        client_id, client_secret = parts

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.tcgplayer.com/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            data = response.json()
            self._access_token = data["access_token"]

    async def get_prices_for_card(
        self,
        nm_price: float,
        tcgplayer_product_id: Optional[int] = None,
        is_foil: bool = False,
    ) -> dict[str, float]:
        """
        Get condition prices for a card.

        Uses TCGPlayer for expensive cards, multipliers for cheap ones.
        """
        if self.should_use_tcgplayer(nm_price) and tcgplayer_product_id:
            try:
                return await self.get_tcgplayer_prices(tcgplayer_product_id)
            except Exception as e:
                logger.warning(f"TCGPlayer fetch failed, using multipliers: {e}")

        # Fallback to multipliers
        return self.calculate_condition_prices_from_multipliers(nm_price)
