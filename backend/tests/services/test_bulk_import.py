"""Tests for bulk price import service."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.pricing.bulk_import import BulkPriceImporter


class TestBulkPriceImporter:
    """Test bulk price import from Scryfall."""

    @pytest.fixture
    def importer(self):
        return BulkPriceImporter()

    def test_parse_scryfall_prices_extracts_all_fields(self, importer):
        """Should extract USD, EUR, foil prices from Scryfall card data."""
        card_data = {
            "id": "abc-123",
            "oracle_id": "def-456",
            "name": "Lightning Bolt",
            "set": "lea",
            "collector_number": "161",
            "prices": {
                "usd": "450.00",
                "usd_foil": None,
                "eur": "400.00",
                "eur_foil": None,
                "tix": "0.50"
            },
            "keywords": ["Instant"],
            "flavor_text": "The spark ignites...",
            "edhrec_rank": 5,
            "reserved": True
        }

        prices = importer.parse_scryfall_prices(card_data)

        assert prices["usd"] == 450.00
        assert prices["usd_foil"] is None
        assert prices["eur"] == 400.00
        assert prices["keywords"] == ["Instant"]
        assert prices["flavor_text"] == "The spark ignites..."
        assert prices["edhrec_rank"] == 5
        assert prices["reserved"] is True

    def test_parse_scryfall_prices_handles_missing_prices(self, importer):
        """Should handle cards with no price data gracefully."""
        card_data = {
            "id": "abc-123",
            "name": "Test Card",
            "set": "tst",
            "collector_number": "1",
            "prices": {}
        }

        prices = importer.parse_scryfall_prices(card_data)

        assert prices["usd"] is None
        assert prices["eur"] is None

    def test_parse_scryfall_prices_handles_string_prices(self, importer):
        """Should convert string prices to floats."""
        card_data = {
            "id": "abc-123",
            "name": "Test Card",
            "set": "tst",
            "collector_number": "1",
            "prices": {
                "usd": "1.50",
                "usd_foil": "3.00",
                "eur": "1.20",
                "eur_foil": "2.50",
            }
        }

        prices = importer.parse_scryfall_prices(card_data)

        assert prices["usd"] == 1.50
        assert prices["usd_foil"] == 3.00
        assert prices["eur"] == 1.20
        assert prices["eur_foil"] == 2.50

    def test_parse_scryfall_prices_handles_invalid_prices(self, importer):
        """Should handle invalid price values gracefully."""
        card_data = {
            "id": "abc-123",
            "name": "Test Card",
            "set": "tst",
            "collector_number": "1",
            "prices": {
                "usd": "invalid",
                "eur": "",
            }
        }

        prices = importer.parse_scryfall_prices(card_data)

        assert prices["usd"] is None
        assert prices["eur"] is None

    def test_parse_scryfall_prices_extracts_all_identifiers(self, importer):
        """Should extract all card identifiers."""
        card_data = {
            "id": "abc-123",
            "oracle_id": "def-456",
            "name": "Lightning Bolt",
            "set": "lea",
            "collector_number": "161",
            "prices": {}
        }

        prices = importer.parse_scryfall_prices(card_data)

        assert prices["scryfall_id"] == "abc-123"
        assert prices["oracle_id"] == "def-456"
        assert prices["name"] == "Lightning Bolt"
        assert prices["set_code"] == "lea"
        assert prices["collector_number"] == "161"

    def test_parse_scryfall_prices_handles_missing_semantic_fields(self, importer):
        """Should handle cards with missing semantic fields."""
        card_data = {
            "id": "abc-123",
            "name": "Test Card",
            "set": "tst",
            "collector_number": "1",
            "prices": {}
        }

        prices = importer.parse_scryfall_prices(card_data)

        assert prices["keywords"] == []
        assert prices["flavor_text"] is None
        assert prices["edhrec_rank"] is None
        assert prices["reserved"] is False

    @pytest.mark.asyncio
    async def test_get_bulk_data_url_returns_default_cards(self, importer):
        """Should fetch and return the default_cards bulk data URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"type": "oracle_cards", "download_uri": "https://example.com/oracle"},
                {"type": "default_cards", "download_uri": "https://example.com/default"},
                {"type": "all_cards", "download_uri": "https://example.com/all"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            url = await importer.get_bulk_data_url()

        assert url == "https://example.com/default"

    @pytest.mark.asyncio
    async def test_get_bulk_data_url_returns_requested_type(self, importer):
        """Should fetch and return the requested bulk data type URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"type": "oracle_cards", "download_uri": "https://example.com/oracle"},
                {"type": "default_cards", "download_uri": "https://example.com/default"},
                {"type": "all_cards", "download_uri": "https://example.com/all"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            url = await importer.get_bulk_data_url(data_type="all_cards")

        assert url == "https://example.com/all"

    @pytest.mark.asyncio
    async def test_get_bulk_data_url_raises_for_unknown_type(self, importer):
        """Should raise ValueError for unknown bulk data type."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"type": "default_cards", "download_uri": "https://example.com/default"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ValueError) as exc_info:
                await importer.get_bulk_data_url(data_type="nonexistent_type")

        assert "nonexistent_type" in str(exc_info.value)

    def test_create_snapshots_creates_usd_snapshot(self, importer):
        """Should create USD snapshot for TCGPlayer."""
        from datetime import datetime, timezone

        parsed = {
            "scryfall_id": "abc-123",
            "usd": 10.00,
            "usd_foil": None,
            "eur": None,
            "eur_foil": None,
        }
        now = datetime.now(timezone.utc)

        snapshots = importer._create_snapshots(parsed, now, tcgplayer_id=1, cardmarket_id=2)

        assert len(snapshots) == 1
        assert snapshots[0]["scryfall_id"] == "abc-123"
        assert snapshots[0]["marketplace_id"] == 1
        assert snapshots[0]["price"] == 10.00
        assert snapshots[0]["currency"] == "USD"
        assert snapshots[0]["is_foil"] is False

    def test_create_snapshots_creates_foil_snapshot(self, importer):
        """Should create foil snapshot for TCGPlayer."""
        from datetime import datetime, timezone

        parsed = {
            "scryfall_id": "abc-123",
            "usd": None,
            "usd_foil": 25.00,
            "eur": None,
            "eur_foil": None,
        }
        now = datetime.now(timezone.utc)

        snapshots = importer._create_snapshots(parsed, now, tcgplayer_id=1, cardmarket_id=2)

        assert len(snapshots) == 1
        assert snapshots[0]["price"] == 25.00
        assert snapshots[0]["is_foil"] is True

    def test_create_snapshots_creates_eur_snapshots(self, importer):
        """Should create EUR snapshots for Cardmarket."""
        from datetime import datetime, timezone

        parsed = {
            "scryfall_id": "abc-123",
            "usd": None,
            "usd_foil": None,
            "eur": 8.00,
            "eur_foil": 20.00,
        }
        now = datetime.now(timezone.utc)

        snapshots = importer._create_snapshots(parsed, now, tcgplayer_id=1, cardmarket_id=2)

        assert len(snapshots) == 2
        # EUR non-foil
        eur_snapshot = next(s for s in snapshots if not s["is_foil"])
        assert eur_snapshot["marketplace_id"] == 2
        assert eur_snapshot["price"] == 8.00
        assert eur_snapshot["currency"] == "EUR"
        # EUR foil
        eur_foil = next(s for s in snapshots if s["is_foil"])
        assert eur_foil["price"] == 20.00

    def test_create_snapshots_creates_all_variants(self, importer):
        """Should create all price variants when available."""
        from datetime import datetime, timezone

        parsed = {
            "scryfall_id": "abc-123",
            "usd": 10.00,
            "usd_foil": 25.00,
            "eur": 8.00,
            "eur_foil": 20.00,
        }
        now = datetime.now(timezone.utc)

        snapshots = importer._create_snapshots(parsed, now, tcgplayer_id=1, cardmarket_id=2)

        assert len(snapshots) == 4

    def test_create_snapshots_returns_empty_for_no_prices(self, importer):
        """Should return empty list when no prices available."""
        from datetime import datetime, timezone

        parsed = {
            "scryfall_id": "abc-123",
            "usd": None,
            "usd_foil": None,
            "eur": None,
            "eur_foil": None,
        }
        now = datetime.now(timezone.utc)

        snapshots = importer._create_snapshots(parsed, now, tcgplayer_id=1, cardmarket_id=2)

        assert len(snapshots) == 0

    def test_create_snapshots_returns_empty_for_missing_scryfall_id(self, importer):
        """Should return empty list when scryfall_id is missing."""
        from datetime import datetime, timezone

        parsed = {
            "scryfall_id": None,
            "usd": 10.00,
        }
        now = datetime.now(timezone.utc)

        snapshots = importer._create_snapshots(parsed, now, tcgplayer_id=1, cardmarket_id=2)

        assert len(snapshots) == 0
