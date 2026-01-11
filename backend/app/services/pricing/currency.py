"""
Currency conversion service for unified USD pricing.

Converts EUR prices to USD at ingestion time to provide
a consistent view for analytics and charting.
"""
from datetime import datetime, timedelta
from typing import Optional

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()


# Cache exchange rate for 24 hours to avoid API rate limits
_rate_cache: dict = {
    "eur_usd_rate": None,
    "expires_at": None,
}

# Fallback rate if API is unavailable (approximate)
FALLBACK_EUR_USD_RATE = 1.08


async def get_eur_usd_rate(force_refresh: bool = False) -> float:
    """
    Fetch current EUR/USD exchange rate with 24-hour caching.

    Uses exchangerate.host free API (no key required).
    Falls back to approximate rate if API is unavailable.

    Args:
        force_refresh: Bypass cache and fetch fresh rate

    Returns:
        EUR to USD exchange rate (e.g., 1.08 means 1 EUR = 1.08 USD)
    """
    now = datetime.utcnow()

    # Check cache
    if not force_refresh:
        if _rate_cache["eur_usd_rate"] is not None:
            if _rate_cache["expires_at"] and _rate_cache["expires_at"] > now:
                return _rate_cache["eur_usd_rate"]

    # Fetch fresh rate
    try:
        async with httpx.AsyncClient() as client:
            # Try exchangerate.host first (no API key required)
            resp = await client.get(
                "https://api.exchangerate.host/latest",
                params={"base": "EUR", "symbols": "USD"},
                timeout=float(settings.external_api_timeout),
            )

            if resp.status_code == 200:
                data = resp.json()
                if data.get("success", True) and "rates" in data:
                    rate = data["rates"].get("USD")
                    if rate:
                        _update_cache(rate)
                        logger.debug("Fetched EUR/USD rate", rate=rate)
                        return rate

            # Fallback to frankfurter.app (also free)
            resp = await client.get(
                "https://api.frankfurter.app/latest",
                params={"from": "EUR", "to": "USD"},
                timeout=float(settings.external_api_timeout),
            )

            if resp.status_code == 200:
                data = resp.json()
                rate = data.get("rates", {}).get("USD")
                if rate:
                    _update_cache(rate)
                    logger.debug("Fetched EUR/USD rate from frankfurter", rate=rate)
                    return rate

    except Exception as e:
        logger.warning("Failed to fetch exchange rate, using fallback", error=str(e))

    # Use fallback rate
    logger.info("Using fallback EUR/USD rate", rate=FALLBACK_EUR_USD_RATE)
    return FALLBACK_EUR_USD_RATE


def _update_cache(rate: float) -> None:
    """Update the rate cache with a new rate."""
    _rate_cache["eur_usd_rate"] = rate
    _rate_cache["expires_at"] = datetime.utcnow() + timedelta(hours=24)


def convert_eur_to_usd(eur_price: float, rate: Optional[float] = None) -> float:
    """
    Convert EUR price to USD.

    Args:
        eur_price: Price in EUR
        rate: Exchange rate (if None, uses cached or fallback rate)

    Returns:
        Price in USD, rounded to 2 decimal places
    """
    if rate is None:
        rate = _rate_cache.get("eur_usd_rate") or FALLBACK_EUR_USD_RATE

    return round(eur_price * rate, 2)


def convert_usd_to_eur(usd_price: float, rate: Optional[float] = None) -> float:
    """
    Convert USD price to EUR.

    Args:
        usd_price: Price in USD
        rate: Exchange rate (if None, uses cached or fallback rate)

    Returns:
        Price in EUR, rounded to 2 decimal places
    """
    if rate is None:
        rate = _rate_cache.get("eur_usd_rate") or FALLBACK_EUR_USD_RATE

    return round(usd_price / rate, 2)


# Convenience function for getting rate synchronously (uses cache only)
def get_cached_rate() -> float:
    """
    Get the cached exchange rate without making an API call.

    Returns fallback rate if cache is empty or expired.
    """
    now = datetime.utcnow()

    if _rate_cache["eur_usd_rate"] is not None:
        if _rate_cache["expires_at"] and _rate_cache["expires_at"] > now:
            return _rate_cache["eur_usd_rate"]

    return FALLBACK_EUR_USD_RATE
