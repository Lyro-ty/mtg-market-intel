"""
TopDeck.gg API client for fetching tournament data.

TopDeck.gg provides comprehensive tournament results, standings, and decklists
for Magic: The Gathering events across multiple formats.

API Documentation: https://topdeck.gg/api/docs
Authentication: API key in Authorization header (not Bearer format)
Rate limit: ~200 requests/minute
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import structlog

from app.core.config import settings
from app.core.circuit_breaker import CircuitOpenError, get_circuit_breaker

logger = structlog.get_logger()


class TopDeckAPIError(Exception):
    """Base exception for TopDeck.gg API errors."""
    pass


class TopDeckRateLimitError(TopDeckAPIError):
    """Exception raised when rate limit is exceeded."""
    pass


class TopDeckCircuitOpenError(TopDeckAPIError):
    """Exception raised when circuit breaker is open."""
    pass


class TopDeckClient:
    """
    Client for TopDeck.gg tournament data API.

    Provides methods to fetch tournament results, standings, and decklists.
    Handles authentication, rate limiting, and error responses.

    Rate limit: ~200 requests per minute
    """

    BASE_URL = "https://topdeck.gg/api/v2"
    RATE_LIMIT_REQUESTS = 200
    RATE_LIMIT_WINDOW = 60  # seconds

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize TopDeck.gg API client.

        Args:
            api_key: API key for authentication. If not provided, will use
                    settings.topdeck_api_key from environment.
        """
        self.api_key = api_key or getattr(settings, "topdeck_api_key", "")
        self.base_url = self.BASE_URL
        self._client: Optional[httpx.AsyncClient] = None
        self._request_count = 0
        self._window_start = datetime.now(timezone.utc)

        # Circuit breaker for external API resilience
        self._circuit = get_circuit_breaker(
            "topdeck",
            failure_threshold=5,
            recovery_timeout=60.0,  # 1 minute before retry
            half_open_requests=2,
        )

        if not self.api_key:
            logger.warning(
                "TopDeck.gg API key not configured - client will not be able to fetch data. "
                "Set TOPDECK_API_KEY environment variable."
            )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {
                "User-Agent": "DualcasterDeals/1.0",
                "Accept": "application/json",
            }

            if self.api_key:
                headers["Authorization"] = self.api_key

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(float(settings.external_api_timeout)),
                headers=headers,
                follow_redirects=True,
            )
        return self._client

    async def _rate_limit(self) -> None:
        """Enforce rate limiting (200 requests per minute)."""
        now = datetime.now(timezone.utc)
        elapsed = (now - self._window_start).total_seconds()

        # Reset window if 60 seconds has passed
        if elapsed >= self.RATE_LIMIT_WINDOW:
            self._request_count = 0
            self._window_start = now
            elapsed = 0

        # If we've hit the limit, wait until window resets
        if self._request_count >= self.RATE_LIMIT_REQUESTS:
            wait_time = self.RATE_LIMIT_WINDOW - elapsed
            if wait_time > 0:
                logger.debug(
                    "TopDeck.gg rate limit reached, waiting",
                    wait_seconds=wait_time
                )
                await asyncio.sleep(wait_time)
                self._request_count = 0
                self._window_start = datetime.now(timezone.utc)

        self._request_count += 1

    async def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        **kwargs
    ) -> httpx.Response:
        """
        Make an HTTP request to TopDeck.gg API.

        Handles rate limiting, circuit breaker, and error responses.

        Args:
            endpoint: API endpoint path (without base URL)
            method: HTTP method (default: GET)
            **kwargs: Additional arguments passed to httpx request

        Returns:
            httpx.Response object

        Raises:
            TopDeckCircuitOpenError: When circuit breaker is open
            TopDeckRateLimitError: When rate limit is exceeded
            TopDeckAPIError: For other API errors
        """
        # Check circuit breaker before making request
        try:
            async with self._circuit:
                await self._rate_limit()
                client = await self._get_client()

                try:
                    response = await client.request(method, endpoint, **kwargs)

                    # Handle rate limiting
                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After", "60")
                        logger.warning(
                            "TopDeck.gg rate limit exceeded",
                            retry_after=retry_after
                        )
                        raise TopDeckRateLimitError(
                            f"Rate limit exceeded. Retry after {retry_after} seconds."
                        )

                    # Handle other HTTP errors (except 404 which is handled by callers)
                    if response.status_code >= 400 and response.status_code != 404:
                        error_msg = f"TopDeck.gg API error {response.status_code}: {response.text}"
                        logger.error(
                            "TopDeck.gg API error",
                            status_code=response.status_code,
                            endpoint=endpoint,
                            error=response.text[:200]
                        )
                        raise TopDeckAPIError(error_msg)

                    return response

                except httpx.NetworkError as e:
                    logger.error("TopDeck.gg network error", endpoint=endpoint, error=str(e))
                    raise TopDeckAPIError(f"Network error: {str(e)}") from e
                except httpx.TimeoutException as e:
                    logger.error("TopDeck.gg timeout", endpoint=endpoint, error=str(e))
                    raise TopDeckAPIError(f"Request timeout: {str(e)}") from e

        except CircuitOpenError as e:
            logger.warning("TopDeck.gg circuit breaker open", error=str(e))
            raise TopDeckCircuitOpenError(str(e)) from e

    def _to_snake_case(self, camel_str: str) -> str:
        """Convert camelCase to snake_case."""
        result = []
        for i, char in enumerate(camel_str):
            if char.isupper() and i > 0:
                # Add underscore before uppercase letter
                result.append('_')
                result.append(char.lower())
            else:
                result.append(char.lower())
        return ''.join(result)

    def _convert_keys_to_snake_case(self, data: dict[str, Any]) -> dict[str, Any]:
        """Convert all dict keys from camelCase to snake_case."""
        converted = {}
        for key, value in data.items():
            snake_key = self._to_snake_case(key)

            # Recursively convert nested dicts
            if isinstance(value, dict):
                converted[snake_key] = self._convert_keys_to_snake_case(value)
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                converted[snake_key] = [
                    self._convert_keys_to_snake_case(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                converted[snake_key] = value

        return converted

    async def get_recent_tournaments(
        self,
        format: str,
        days: int = 30
    ) -> list[dict[str, Any]]:
        """
        Get recent tournaments for a specific format.

        Args:
            format: MTG format (e.g., "Modern", "Pioneer", "Standard", "Legacy")
                   Note: Format names are case-sensitive!
            days: Number of days to look back (default: 30)

        Returns:
            List of tournament dictionaries with normalized fields:
            - id: Tournament ID (from TID)
            - name: Tournament name
            - format: MTG format
            - date: datetime object
            - player_count: Number of players
            - swiss_rounds: Number of swiss rounds
            - top_cut_size: Top cut size (0 if none)
            - city: City name
            - venue: Venue name
            - url: Tournament URL on TopDeck.gg
            - standings: List of standings with wins/losses/draws

        Raises:
            TopDeckAPIError: On API errors
        """
        endpoint = "/tournaments"

        # v2 API uses POST with JSON body
        # 'last' = number of days back, 'game' and 'format' are case-sensitive
        payload = {
            "game": "Magic: The Gathering",
            "format": format,  # Case-sensitive: "Modern", "EDH", "Pioneer", etc.
            "last": days,
        }

        try:
            response = await self._make_request(endpoint, method="POST", json=payload)
            data = response.json()

            # v2 API returns list directly
            tournaments = data if isinstance(data, list) else []

            # Convert to our normalized format
            result = []
            for tournament in tournaments:
                normalized = self._normalize_tournament(tournament)
                if normalized:
                    result.append(normalized)

            logger.debug(
                "Fetched recent tournaments",
                format=format,
                days=days,
                count=len(result)
            )

            return result

        except ValueError as e:
            logger.error("Invalid JSON response from TopDeck.gg", error=str(e))
            raise TopDeckAPIError(f"Invalid JSON response: {str(e)}") from e

    def _normalize_tournament(self, raw: dict[str, Any]) -> Optional[dict[str, Any]]:
        """
        Normalize a raw tournament response to our standard format.

        The TopDeck.gg v2 API returns:
        - TID: Tournament ID
        - tournamentName: Name
        - startDate: Unix timestamp
        - swissNum: Number of swiss rounds
        - topCut: Top cut size
        - eventData: {lat, lng, city, state, location}
        - standings: List of {wins, losses, draws, decklist, deckObj}
        """
        try:
            tid = raw.get("TID")
            if not tid:
                return None

            # Parse Unix timestamp
            start_date = raw.get("startDate", 0)
            tournament_date = datetime.fromtimestamp(start_date, tz=timezone.utc)

            # Extract venue info
            event_data = raw.get("eventData", {}) or {}

            # Count players from standings
            standings_raw = raw.get("standings", []) or []
            player_count = len(standings_raw)

            # Normalize standings
            standings = []
            for i, s in enumerate(standings_raw):
                standings.append({
                    "rank": i + 1,  # Standings are ordered by rank
                    "wins": s.get("wins", 0),
                    "losses": s.get("losses", 0),
                    "draws": s.get("draws", 0),
                    "decklist": s.get("decklist"),
                    "deck_obj": s.get("deckObj"),
                })

            return {
                "id": tid,
                "name": raw.get("tournamentName", "Unknown Tournament"),
                "format": raw.get("format", "Unknown"),
                "date": tournament_date,
                "player_count": player_count,
                "swiss_rounds": raw.get("swissNum"),
                "top_cut_size": raw.get("topCut", 0),
                "city": event_data.get("city"),
                "venue": event_data.get("location"),
                "url": f"https://topdeck.gg/event/{tid}",
                "standings": standings,
            }
        except Exception as e:
            logger.warning(
                "Failed to normalize tournament",
                tid=raw.get("TID"),
                error=str(e)
            )
            return None

    async def get_tournament(self, topdeck_id: str) -> Optional[dict[str, Any]]:
        """
        Get detailed information about a specific tournament.

        Args:
            topdeck_id: TopDeck.gg tournament ID

        Returns:
            Tournament dictionary with detailed information, or None if not found.
            Fields include:
            - id: Tournament ID
            - name: Tournament name
            - format: MTG format
            - date: ISO 8601 date string
            - player_count: Number of players
            - venue: Venue information dict
            - url: Tournament URL

        Raises:
            TopDeckAPIError: On API errors (except 404)
        """
        endpoint = f"/tournaments/{topdeck_id}"

        try:
            response = await self._make_request(endpoint)

            if response.status_code == 404:
                logger.debug("Tournament not found", topdeck_id=topdeck_id)
                return None

            data = response.json()
            converted = self._convert_keys_to_snake_case(data)

            logger.debug("Fetched tournament", topdeck_id=topdeck_id)
            return converted

        except ValueError as e:
            logger.error("Invalid JSON response from TopDeck.gg", error=str(e))
            raise TopDeckAPIError(f"Invalid JSON response: {str(e)}") from e

    async def get_tournament_standings(
        self,
        topdeck_id: str
    ) -> list[dict[str, Any]]:
        """
        Get standings for a specific tournament.

        Args:
            topdeck_id: TopDeck.gg tournament ID

        Returns:
            List of standing dictionaries with fields:
            - rank: Player's final rank
            - player_name: Player name
            - player_id: Player ID
            - wins: Number of wins
            - losses: Number of losses
            - draws: Number of draws

        Raises:
            TopDeckAPIError: On API errors
        """
        endpoint = f"/tournaments/{topdeck_id}/standings"

        try:
            response = await self._make_request(endpoint)
            data = response.json()

            standings = data.get("standings", [])

            # Convert to snake_case
            result = []
            for standing in standings:
                converted = self._convert_keys_to_snake_case(standing)
                result.append(converted)

            logger.debug(
                "Fetched tournament standings",
                topdeck_id=topdeck_id,
                count=len(result)
            )

            return result

        except ValueError as e:
            logger.error("Invalid JSON response from TopDeck.gg", error=str(e))
            raise TopDeckAPIError(f"Invalid JSON response: {str(e)}") from e

    async def get_decklist(
        self,
        topdeck_id: str,
        player_id: str
    ) -> Optional[dict[str, Any]]:
        """
        Get decklist for a specific player in a tournament.

        Args:
            topdeck_id: TopDeck.gg tournament ID
            player_id: Player ID

        Returns:
            Decklist dictionary with fields:
            - archetype: Deck archetype name
            - mainboard: List of card dicts with 'name' and 'quantity'
            - sideboard: List of card dicts with 'name' and 'quantity'

            Returns None if decklist not found.

        Raises:
            TopDeckAPIError: On API errors (except 404)
        """
        endpoint = f"/tournaments/{topdeck_id}/players/{player_id}/decklist"

        try:
            response = await self._make_request(endpoint)

            if response.status_code == 404:
                logger.debug(
                    "Decklist not found",
                    topdeck_id=topdeck_id,
                    player_id=player_id
                )
                return None

            data = response.json()
            converted = self._convert_keys_to_snake_case(data)

            logger.debug(
                "Fetched decklist",
                topdeck_id=topdeck_id,
                player_id=player_id,
                archetype=converted.get("archetype")
            )

            return converted

        except ValueError as e:
            logger.error("Invalid JSON response from TopDeck.gg", error=str(e))
            raise TopDeckAPIError(f"Invalid JSON response: {str(e)}") from e

    async def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    async def __aenter__(self) -> "TopDeckClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - cleanup resources."""
        await self.close()
