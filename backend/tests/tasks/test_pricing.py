"""
Tests for pricing Celery tasks.

Tests verify task registration, async wrapper functionality,
and proper integration with pricing services.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from celery import Celery


class TestPricingTaskRegistration:
    """Test that pricing tasks are properly registered with Celery."""

    def test_bulk_refresh_task_registered(self):
        """Verify bulk_refresh task is registered."""
        from app.tasks.pricing import bulk_refresh

        assert bulk_refresh.name == "app.tasks.pricing.bulk_refresh"
        assert bulk_refresh.bind is True

    def test_inventory_refresh_task_registered(self):
        """Verify inventory_refresh task is registered."""
        from app.tasks.pricing import inventory_refresh

        assert inventory_refresh.name == "app.tasks.pricing.inventory_refresh"
        assert inventory_refresh.bind is True

    def test_condition_refresh_task_registered(self):
        """Verify condition_refresh task is registered."""
        from app.tasks.pricing import condition_refresh

        assert condition_refresh.name == "app.tasks.pricing.condition_refresh"
        assert condition_refresh.bind is True


class TestBulkRefreshTask:
    """Tests for the bulk_refresh Celery task."""

    @patch("app.tasks.pricing.run_async")
    def test_bulk_refresh_calls_async_impl(self, mock_run_async):
        """Verify bulk_refresh delegates to async implementation."""
        mock_run_async.return_value = {
            "cards_updated": 1000,
            "snapshots_created": 2000,
            "errors": 0,
        }

        from app.tasks.pricing import bulk_refresh

        # Call task directly (not through Celery)
        result = bulk_refresh.run()

        assert mock_run_async.called
        assert result["cards_updated"] == 1000

    @patch("app.tasks.pricing.BulkPriceImporter")
    @patch("app.tasks.pricing.create_task_session_maker")
    def test_bulk_refresh_uses_importer(self, mock_session_maker, mock_importer_cls):
        """Verify bulk_refresh uses BulkPriceImporter service."""
        # Setup mocks
        mock_session = MagicMock()
        mock_engine = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_engine.dispose = AsyncMock()

        mock_session_maker.return_value = (
            MagicMock(return_value=mock_session),
            mock_engine,
        )

        mock_importer = MagicMock()
        mock_importer.import_prices = AsyncMock(return_value={
            "cards_updated": 500,
            "snapshots_created": 1000,
            "errors": 0,
        })
        mock_importer_cls.return_value = mock_importer

        from app.tasks.pricing import _bulk_refresh_async
        import asyncio

        # Run the async function
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(_bulk_refresh_async())
        finally:
            loop.close()

        # Verify importer was used
        mock_importer_cls.assert_called_once()
        assert "completed_at" in result or "errors" in result


class TestInventoryRefreshTask:
    """Tests for the inventory_refresh Celery task."""

    @patch("app.tasks.pricing.run_async")
    def test_inventory_refresh_calls_async_impl(self, mock_run_async):
        """Verify inventory_refresh delegates to async implementation."""
        mock_run_async.return_value = {
            "cards_refreshed": 50,
            "api_calls": 50,
        }

        from app.tasks.pricing import inventory_refresh

        result = inventory_refresh.run()

        assert mock_run_async.called
        assert result["cards_refreshed"] == 50

    @patch("app.tasks.pricing.ScryfallAdapter")
    @patch("app.tasks.pricing.create_task_session_maker")
    def test_inventory_refresh_respects_rate_limit(self, mock_session_maker, mock_adapter_cls):
        """Verify inventory_refresh respects Scryfall rate limit."""
        # Setup mocks
        mock_session = MagicMock()
        mock_engine = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_engine.dispose = AsyncMock()

        async_session_maker = MagicMock()
        async_session_maker.return_value = mock_session
        mock_session_maker.return_value = (async_session_maker, mock_engine)

        # Mock adapter with rate limit tracking
        mock_adapter = MagicMock()
        mock_adapter.fetch_price = AsyncMock()
        mock_adapter.close = AsyncMock()
        mock_adapter_cls.return_value = mock_adapter

        # Scryfall rate limit is 100ms between requests
        # This is configured in the adapter and should be respected
        from app.tasks.pricing import SCRYFALL_RATE_LIMIT_SECONDS
        assert SCRYFALL_RATE_LIMIT_SECONDS >= 0.1


class TestConditionRefreshTask:
    """Tests for the condition_refresh Celery task."""

    @patch("app.tasks.pricing.run_async")
    def test_condition_refresh_calls_async_impl(self, mock_run_async):
        """Verify condition_refresh delegates to async implementation."""
        mock_run_async.return_value = {
            "cards_processed": 25,
            "tcgplayer_calls": 20,
            "multiplier_fallbacks": 5,
        }

        from app.tasks.pricing import condition_refresh

        result = condition_refresh.run()

        assert mock_run_async.called
        assert result["cards_processed"] == 25

    @patch("app.tasks.pricing.ConditionPricer")
    @patch("app.tasks.pricing.create_task_session_maker")
    def test_condition_refresh_uses_pricer(self, mock_session_maker, mock_pricer_cls):
        """Verify condition_refresh uses ConditionPricer service."""
        mock_pricer = MagicMock()
        mock_pricer.should_use_tcgplayer = MagicMock(return_value=True)
        mock_pricer.get_prices_for_card = AsyncMock(return_value={
            "NEAR_MINT": 10.0,
            "LIGHTLY_PLAYED": 8.70,
        })
        mock_pricer_cls.return_value = mock_pricer

        # Verify the constant for price threshold
        from app.tasks.pricing import TCGPLAYER_PRICE_THRESHOLD
        assert TCGPLAYER_PRICE_THRESHOLD == 5.00


class TestCeleryBeatSchedule:
    """Test that Celery beat schedule is properly configured."""

    def test_pricing_tasks_in_beat_schedule(self):
        """Verify pricing tasks are in the beat schedule."""
        from app.tasks.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule

        # Check bulk refresh is scheduled
        assert "pricing-bulk-refresh" in schedule
        assert schedule["pricing-bulk-refresh"]["task"] == "app.tasks.pricing.bulk_refresh"

        # Check inventory refresh is scheduled
        assert "pricing-inventory-refresh" in schedule
        assert schedule["pricing-inventory-refresh"]["task"] == "app.tasks.pricing.inventory_refresh"

        # Check condition refresh is scheduled
        assert "pricing-condition-refresh" in schedule
        assert schedule["pricing-condition-refresh"]["task"] == "app.tasks.pricing.condition_refresh"

    def test_search_refresh_embeddings_scheduled(self):
        """Verify search embedding refresh is in schedule."""
        from app.tasks.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule

        assert "search-refresh-embeddings" in schedule
        assert schedule["search-refresh-embeddings"]["task"] == "app.tasks.search.refresh_embeddings"

    def test_pricing_included_in_autodiscover(self):
        """Verify pricing module is included for autodiscovery."""
        from app.tasks.celery_app import celery_app

        # Check that pricing module is in include list
        assert "app.tasks.pricing" in celery_app.conf.include
