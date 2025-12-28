"""
Tests for TopDeck.gg API client.

Following TDD, this test file defines the expected behavior
of the TopDeckClient before implementation.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.services.tournaments.topdeck_client import (
    TopDeckClient,
    TopDeckAPIError,
    TopDeckRateLimitError,
)


@pytest.fixture
def topdeck_client():
    """Create TopDeckClient with mock API key."""
    return TopDeckClient(api_key="test-api-key")


@pytest.fixture
def mock_tournament_response():
    """Mock tournament data from TopDeck.gg API."""
    return {
        "id": "tour-123",
        "name": "Weekly Modern Tournament",
        "format": "modern",
        "date": "2024-12-20T18:00:00Z",
        "playerCount": 32,
        "venue": {
            "name": "LGS Store",
            "city": "Seattle",
            "state": "WA",
            "country": "USA"
        },
        "url": "https://topdeck.gg/event/tour-123"
    }


@pytest.fixture
def mock_standings_response():
    """Mock standings data from TopDeck.gg API."""
    return {
        "standings": [
            {
                "rank": 1,
                "playerName": "Alice Smith",
                "playerId": "player-001",
                "wins": 4,
                "losses": 0,
                "draws": 1
            },
            {
                "rank": 2,
                "playerName": "Bob Jones",
                "playerId": "player-002",
                "wins": 3,
                "losses": 1,
                "draws": 1
            }
        ]
    }


@pytest.fixture
def mock_decklist_response():
    """Mock decklist data from TopDeck.gg API."""
    return {
        "archetype": "Izzet Murktide",
        "mainboard": [
            {
                "name": "Dragon's Rage Channeler",
                "quantity": 4
            },
            {
                "name": "Murktide Regent",
                "quantity": 4
            },
            {
                "name": "Lightning Bolt",
                "quantity": 4
            }
        ],
        "sideboard": [
            {
                "name": "Blood Moon",
                "quantity": 2
            },
            {
                "name": "Dress Down",
                "quantity": 3
            }
        ]
    }


class TestTopDeckClientInit:
    """Test TopDeckClient initialization."""

    def test_init_with_api_key(self):
        """Test client can be initialized with API key."""
        client = TopDeckClient(api_key="test-key")
        assert client.api_key == "test-key"
        assert client.base_url == "https://topdeck.gg/api/v2"

    def test_init_without_api_key(self):
        """Test client can be initialized without API key (uses settings)."""
        with patch("app.services.tournaments.topdeck_client.settings") as mock_settings:
            mock_settings.topdeck_api_key = "settings-key"
            client = TopDeckClient()
            assert client.api_key == "settings-key"

    def test_init_without_api_key_no_settings(self):
        """Test client initialization when no API key available."""
        with patch("app.services.tournaments.topdeck_client.settings") as mock_settings:
            mock_settings.topdeck_api_key = ""
            client = TopDeckClient()
            assert client.api_key == ""


class TestTopDeckClientGetRecentTournaments:
    """Test get_recent_tournaments method."""

    @pytest.mark.asyncio
    async def test_get_recent_tournaments_success(self, topdeck_client, mock_tournament_response):
        """Test fetching recent tournaments successfully."""
        # Use MagicMock for response since httpx's json() is synchronous
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [mock_tournament_response]  # v2 API returns list directly

        with patch.object(topdeck_client, "_make_request", return_value=mock_response):
            tournaments = await topdeck_client.get_recent_tournaments(format="modern", days=30)

            assert len(tournaments) == 1
            tournament = tournaments[0]
            assert tournament["id"] == "tour-123"
            assert tournament["name"] == "Weekly Modern Tournament"
            assert tournament["format"] == "modern"
            assert tournament["player_count"] == 32

    @pytest.mark.asyncio
    async def test_get_recent_tournaments_empty(self, topdeck_client):
        """Test fetching recent tournaments when none exist."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []  # v2 API returns empty list

        with patch.object(topdeck_client, "_make_request", return_value=mock_response):
            tournaments = await topdeck_client.get_recent_tournaments(format="modern")
            assert tournaments == []

    @pytest.mark.asyncio
    async def test_get_recent_tournaments_default_params(self, topdeck_client):
        """Test get_recent_tournaments uses default params (POST with JSON body)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch.object(topdeck_client, "_make_request", return_value=mock_response) as mock_req:
            await topdeck_client.get_recent_tournaments(format="modern")

            # Verify POST method and JSON body with default days=30
            call_args = mock_req.call_args
            assert call_args[0][0] == "/tournaments"  # endpoint
            assert call_args[1]["method"] == "POST"
            assert call_args[1]["json"]["last"] == 30  # default days


class TestTopDeckClientGetTournament:
    """Test get_tournament method."""

    @pytest.mark.asyncio
    async def test_get_tournament_success(self, topdeck_client, mock_tournament_response):
        """Test fetching a specific tournament successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_tournament_response

        with patch.object(topdeck_client, "_make_request", return_value=mock_response):
            tournament = await topdeck_client.get_tournament("tour-123")

            assert tournament is not None
            assert tournament["id"] == "tour-123"
            assert tournament["name"] == "Weekly Modern Tournament"

    @pytest.mark.asyncio
    async def test_get_tournament_not_found(self, topdeck_client):
        """Test fetching a tournament that doesn't exist."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(topdeck_client, "_make_request", return_value=mock_response):
            tournament = await topdeck_client.get_tournament("nonexistent")
            assert tournament is None


class TestTopDeckClientGetTournamentStandings:
    """Test get_tournament_standings method."""

    @pytest.mark.asyncio
    async def test_get_tournament_standings_success(
        self, topdeck_client, mock_standings_response
    ):
        """Test fetching tournament standings successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_standings_response

        with patch.object(topdeck_client, "_make_request", return_value=mock_response):
            standings = await topdeck_client.get_tournament_standings("tour-123")

            assert len(standings) == 2
            assert standings[0]["player_name"] == "Alice Smith"
            assert standings[0]["rank"] == 1
            assert standings[0]["wins"] == 4

    @pytest.mark.asyncio
    async def test_get_tournament_standings_empty(self, topdeck_client):
        """Test fetching standings for tournament with no results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"standings": []}

        with patch.object(topdeck_client, "_make_request", return_value=mock_response):
            standings = await topdeck_client.get_tournament_standings("tour-123")
            assert standings == []


class TestTopDeckClientGetDecklist:
    """Test get_decklist method."""

    @pytest.mark.asyncio
    async def test_get_decklist_success(self, topdeck_client, mock_decklist_response):
        """Test fetching a decklist successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_decklist_response

        with patch.object(topdeck_client, "_make_request", return_value=mock_response):
            decklist = await topdeck_client.get_decklist("tour-123", "player-001")

            assert decklist is not None
            assert decklist["archetype"] == "Izzet Murktide"
            assert len(decklist["mainboard"]) == 3
            assert len(decklist["sideboard"]) == 2

    @pytest.mark.asyncio
    async def test_get_decklist_not_found(self, topdeck_client):
        """Test fetching a decklist that doesn't exist."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch.object(topdeck_client, "_make_request", return_value=mock_response):
            decklist = await topdeck_client.get_decklist("tour-123", "player-999")
            assert decklist is None


class TestTopDeckClientErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, topdeck_client):
        """Test handling of rate limit (429) errors.

        Note: _make_request already raises TopDeckRateLimitError for 429 responses,
        so we test by making it raise the exception directly.
        """
        with patch.object(
            topdeck_client,
            "_make_request",
            side_effect=TopDeckRateLimitError("Rate limit exceeded. Retry after 60 seconds.")
        ):
            with pytest.raises(TopDeckRateLimitError) as exc_info:
                await topdeck_client.get_tournament("tour-123")

            assert "rate limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_api_error_5xx(self, topdeck_client):
        """Test handling of 5xx server errors.

        Note: _make_request raises TopDeckAPIError for 5xx responses.
        """
        with patch.object(
            topdeck_client,
            "_make_request",
            side_effect=TopDeckAPIError("TopDeck.gg API error 500: Internal Server Error")
        ):
            with pytest.raises(TopDeckAPIError) as exc_info:
                await topdeck_client.get_tournament("tour-123")

            assert "500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_network_error(self, topdeck_client):
        """Test handling of network errors."""
        with patch.object(
            topdeck_client,
            "_make_request",
            side_effect=TopDeckAPIError("Network error: Connection failed")
        ):
            with pytest.raises(TopDeckAPIError) as exc_info:
                await topdeck_client.get_tournament("tour-123")

            assert "network" in str(exc_info.value).lower() or "connection" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, topdeck_client):
        """Test handling of invalid JSON in response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with patch.object(topdeck_client, "_make_request", return_value=mock_response):
            with pytest.raises(TopDeckAPIError):
                await topdeck_client.get_tournament("tour-123")


class TestTopDeckClientResponseParsing:
    """Test response parsing and data extraction."""

    @pytest.mark.asyncio
    async def test_parse_tournament_extracts_all_fields(
        self, topdeck_client, mock_tournament_response
    ):
        """Test that all expected tournament fields are extracted."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_tournament_response

        with patch.object(topdeck_client, "_make_request", return_value=mock_response):
            tournament = await topdeck_client.get_tournament("tour-123")

            # Check all expected fields are present
            assert "id" in tournament
            assert "name" in tournament
            assert "format" in tournament
            assert "date" in tournament
            assert "player_count" in tournament
            assert "venue" in tournament
            assert "url" in tournament

    @pytest.mark.asyncio
    async def test_parse_standing_snake_case_conversion(
        self, topdeck_client, mock_standings_response
    ):
        """Test that standing fields are converted from camelCase to snake_case."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_standings_response

        with patch.object(topdeck_client, "_make_request", return_value=mock_response):
            standings = await topdeck_client.get_tournament_standings("tour-123")

            # Check snake_case conversion
            standing = standings[0]
            assert "player_name" in standing
            assert "player_id" in standing
            # Should not have camelCase versions
            assert "playerName" not in standing
            assert "playerId" not in standing


class TestTopDeckClientCleanup:
    """Test client cleanup and resource management."""

    @pytest.mark.asyncio
    async def test_close_client(self, topdeck_client):
        """Test that client can be closed properly."""
        # Create mock client with is_closed property returning False
        mock_httpx_client = AsyncMock()
        mock_httpx_client.is_closed = False  # Explicitly set as boolean

        topdeck_client._client = mock_httpx_client

        await topdeck_client.close()

        # Verify client was closed
        mock_httpx_client.aclose.assert_called_once()
        assert topdeck_client._client is None

    @pytest.mark.asyncio
    async def test_context_manager_support(self):
        """Test client can be used as async context manager."""
        async with TopDeckClient(api_key="test-key") as client:
            assert client is not None
            assert isinstance(client, TopDeckClient)

        # Client should be closed after context
        assert client._client is None
