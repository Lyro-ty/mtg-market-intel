"""
Tests for card schema default values.

These tests verify that price and metrics fields default to 0.0 (not null)
and that has_price_data/has_metrics_data flags are correctly set.
"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.schemas.card import (
    CardPriceResponse,
    CardMetricsResponse,
    CardDetailResponse,
    CardResponse,
    MarketplacePriceDetail,
)


class TestCardPriceResponseDefaults:
    """Test CardPriceResponse schema defaults."""

    def test_price_fields_default_to_zero(self):
        """Price fields should default to 0.0, not null."""
        response = CardPriceResponse(
            card_id=1,
            card_name="Test Card",
            prices=[],
            updated_at=datetime.now(timezone.utc),
        )
        assert response.lowest_price == 0.0
        assert response.highest_price == 0.0
        assert response.spread_pct == 0.0
        assert response.has_price_data is False

    def test_has_price_data_defaults_to_false(self):
        """has_price_data should default to False."""
        response = CardPriceResponse(
            card_id=1,
            card_name="Test Card",
            prices=[],
            updated_at=datetime.now(timezone.utc),
        )
        assert response.has_price_data is False

    def test_has_price_data_can_be_set_to_true(self):
        """has_price_data can be explicitly set to True."""
        response = CardPriceResponse(
            card_id=1,
            card_name="Test Card",
            prices=[],
            lowest_price=5.0,
            highest_price=10.0,
            spread_pct=100.0,
            updated_at=datetime.now(timezone.utc),
            has_price_data=True,
        )
        assert response.has_price_data is True
        assert response.lowest_price == 5.0
        assert response.highest_price == 10.0
        assert response.spread_pct == 100.0

    def test_price_response_serialization(self):
        """Ensure response serializes correctly (no null values)."""
        response = CardPriceResponse(
            card_id=1,
            card_name="Test Card",
            prices=[],
            updated_at=datetime.now(timezone.utc),
        )
        data = response.model_dump()

        # All price fields should be numeric, not None
        assert data["lowest_price"] == 0.0
        assert data["highest_price"] == 0.0
        assert data["spread_pct"] == 0.0
        assert data["has_price_data"] is False


class TestCardMetricsResponseDefaults:
    """Test CardMetricsResponse schema defaults."""

    def test_metrics_fields_default_to_zero(self):
        """Metrics fields should default to 0.0 or 0, not null."""
        response = CardMetricsResponse(card_id=1)

        assert response.avg_price == 0.0
        assert response.min_price == 0.0
        assert response.max_price == 0.0
        assert response.spread_pct == 0.0
        assert response.price_change_7d == 0.0
        assert response.price_change_30d == 0.0
        assert response.volatility_7d == 0.0
        assert response.ma_7d == 0.0
        assert response.ma_30d == 0.0
        assert response.total_listings == 0
        assert response.has_metrics_data is False

    def test_date_can_be_none(self):
        """Date field should allow None when no metrics data."""
        response = CardMetricsResponse(card_id=1)
        assert response.date is None

    def test_has_metrics_data_defaults_to_false(self):
        """has_metrics_data should default to False."""
        response = CardMetricsResponse(card_id=1)
        assert response.has_metrics_data is False

    def test_has_metrics_data_can_be_set_to_true(self):
        """has_metrics_data can be explicitly set to True."""
        response = CardMetricsResponse(
            card_id=1,
            date="2024-01-15",
            avg_price=25.50,
            min_price=20.0,
            max_price=30.0,
            has_metrics_data=True,
        )
        assert response.has_metrics_data is True
        assert response.avg_price == 25.50

    def test_metrics_response_serialization(self):
        """Ensure response serializes correctly (no null values for numeric fields)."""
        response = CardMetricsResponse(card_id=1)
        data = response.model_dump()

        # All numeric fields should be numbers, not None
        assert data["avg_price"] == 0.0
        assert data["min_price"] == 0.0
        assert data["max_price"] == 0.0
        assert data["spread_pct"] == 0.0
        assert data["price_change_7d"] == 0.0
        assert data["price_change_30d"] == 0.0
        assert data["volatility_7d"] == 0.0
        assert data["ma_7d"] == 0.0
        assert data["ma_30d"] == 0.0
        assert data["total_listings"] == 0
        assert data["has_metrics_data"] is False
        # Date can be None
        assert data["date"] is None


class TestCardDetailResponseDefaults:
    """Test CardDetailResponse schema defaults."""

    def test_has_price_data_defaults_to_false(self):
        """has_price_data should default to False."""
        card_response = CardResponse(
            id=1,
            name="Test Card",
            set_code="TST",
            collector_number="001",
            scryfall_id="test-scryfall-id",
        )
        response = CardDetailResponse(card=card_response)

        assert response.has_price_data is False
        assert response.current_prices == []

    def test_has_price_data_can_be_set_to_true(self):
        """has_price_data can be explicitly set when prices exist."""
        card_response = CardResponse(
            id=1,
            name="Test Card",
            set_code="TST",
            collector_number="001",
            scryfall_id="test-scryfall-id",
        )
        price = MarketplacePriceDetail(
            marketplace_id=1,
            marketplace_name="TCGPlayer",
            marketplace_slug="tcgplayer",
            price=10.0,
            currency="USD",
            last_updated=datetime.now(timezone.utc),
        )
        response = CardDetailResponse(
            card=card_response,
            current_prices=[price],
            has_price_data=True,
        )

        assert response.has_price_data is True
        assert len(response.current_prices) == 1

    def test_card_detail_with_metrics_defaults(self):
        """CardDetailResponse with metrics should have proper defaults."""
        card_response = CardResponse(
            id=1,
            name="Test Card",
            set_code="TST",
            collector_number="001",
            scryfall_id="test-scryfall-id",
        )
        metrics = CardMetricsResponse(
            card_id=1,
            has_metrics_data=False,  # No real metrics data
        )
        response = CardDetailResponse(
            card=card_response,
            metrics=metrics,
            has_price_data=False,
        )

        assert response.metrics is not None
        assert response.metrics.avg_price == 0.0
        assert response.metrics.has_metrics_data is False
        assert response.has_price_data is False

    def test_card_detail_serialization(self):
        """Ensure CardDetailResponse serializes correctly."""
        card_response = CardResponse(
            id=1,
            name="Test Card",
            set_code="TST",
            collector_number="001",
            scryfall_id="test-scryfall-id",
        )
        response = CardDetailResponse(card=card_response)
        data = response.model_dump()

        assert data["has_price_data"] is False
        assert data["current_prices"] == []
        assert data["metrics"] is None


class TestPriceFieldsNeverNull:
    """Integration tests to verify price fields are never null in responses."""

    def test_empty_prices_returns_zeros(self):
        """When no prices exist, fields should be 0.0 not null."""
        response = CardPriceResponse(
            card_id=1,
            card_name="Test Card",
            prices=[],
            updated_at=datetime.now(timezone.utc),
            has_price_data=False,
        )

        # Verify JSON serialization doesn't produce null
        json_data = response.model_dump_json()
        assert '"lowest_price":0.0' in json_data or '"lowest_price":0' in json_data
        assert '"highest_price":0.0' in json_data or '"highest_price":0' in json_data
        assert '"spread_pct":0.0' in json_data or '"spread_pct":0' in json_data
        assert '"has_price_data":false' in json_data

    def test_empty_metrics_returns_zeros(self):
        """When no metrics exist, fields should be 0.0/0 not null."""
        response = CardMetricsResponse(
            card_id=1,
            has_metrics_data=False,
        )

        # Verify JSON serialization doesn't produce null for numeric fields
        json_data = response.model_dump_json()
        assert '"avg_price":0.0' in json_data or '"avg_price":0' in json_data
        assert '"total_listings":0' in json_data
        assert '"has_metrics_data":false' in json_data
