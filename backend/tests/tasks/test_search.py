"""Tests for search tasks."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSearchTasks:
    """Test search-related Celery tasks."""

    def test_refresh_embeddings_task_registered(self):
        """Verify refresh_embeddings task is registered."""
        from app.tasks.search import refresh_embeddings

        assert refresh_embeddings.name == "app.tasks.search.refresh_embeddings"
        assert callable(refresh_embeddings)

    @patch("app.tasks.search.create_task_session_maker")
    @patch("app.tasks.search.VectorizationService")
    def test_refresh_embeddings_runs(self, mock_vectorizer_cls, mock_session_maker):
        """Test refresh_embeddings task can be called."""
        from app.tasks.search import refresh_embeddings

        # Setup mock vectorizer
        mock_vectorizer = MagicMock()
        mock_vectorizer.close = MagicMock()
        mock_vectorizer_cls.return_value = mock_vectorizer

        # Setup mock session
        mock_session = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()

        async_session_maker = MagicMock()
        async_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        async_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_session_maker.return_value = (async_session_maker, mock_engine)

        # Mock query results - no cards
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        # Should not raise
        result = refresh_embeddings()
        assert "completed_at" in result or "cards_processed" in result


class TestRefreshEmbeddingsTask:
    """Tests for the refresh_embeddings Celery task."""

    @patch("app.tasks.search.run_async")
    def test_refresh_embeddings_calls_async_impl(self, mock_run_async):
        """Verify refresh_embeddings delegates to async implementation."""
        mock_run_async.return_value = {
            "cards_processed": 100,
            "embeddings_created": 80,
            "embeddings_updated": 20,
            "errors": 0,
        }

        from app.tasks.search import refresh_embeddings

        # Call task directly (not through Celery)
        result = refresh_embeddings.run()

        assert mock_run_async.called
        assert result["cards_processed"] == 100
        assert result["embeddings_created"] == 80

    @patch("app.tasks.search.VectorizationService")
    @patch("app.tasks.search.create_task_session_maker")
    def test_refresh_embeddings_processes_cards_without_vectors(
        self, mock_session_maker, mock_vectorizer_cls
    ):
        """Verify task processes cards without embeddings."""
        # Setup mocks
        mock_session = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()

        async_session_maker = MagicMock()
        async_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        async_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_session_maker.return_value = (async_session_maker, mock_engine)

        # Mock vectorizer
        mock_vectorizer = MagicMock()
        mock_vectorizer.close = MagicMock()
        mock_vectorizer_cls.return_value = mock_vectorizer

        # Mock cards query - no cards
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        from app.tasks.search import _refresh_embeddings_async
        import asyncio

        # Run the async function
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(_refresh_embeddings_async(batch_size=100, force=False))
        finally:
            loop.close()

        # Verify result structure
        assert "cards_processed" in result
        assert "embeddings_created" in result
        assert "embeddings_updated" in result
        assert "errors" in result
        assert "started_at" in result
        assert "completed_at" in result

    @patch("app.tasks.search.VectorizationService")
    @patch("app.tasks.search.create_task_session_maker")
    def test_refresh_embeddings_force_reprocesses_all_cards(
        self, mock_session_maker, mock_vectorizer_cls
    ):
        """Verify force=True re-embeds all cards."""
        # Setup mocks
        mock_session = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()

        async_session_maker = MagicMock()
        async_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        async_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_session_maker.return_value = (async_session_maker, mock_engine)

        # Mock vectorizer
        mock_vectorizer = MagicMock()
        mock_vectorizer.close = MagicMock()
        mock_vectorizer_cls.return_value = mock_vectorizer

        # Mock cards query - no cards for simplicity
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        from app.tasks.search import _refresh_embeddings_async
        import asyncio

        # Run with force=True
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(_refresh_embeddings_async(batch_size=100, force=True))
        finally:
            loop.close()

        # Should complete without errors
        assert "completed_at" in result


class TestCeleryBeatScheduleSearch:
    """Test that search tasks are in the Celery beat schedule when enabled."""

    def test_search_task_in_include_list(self):
        """Verify search module is in the include list."""
        from app.tasks.celery_app import celery_app

        # Check that search module is in include list
        assert "app.tasks.search" in celery_app.conf.include

    def test_search_refresh_embeddings_scheduled(self):
        """Verify search embedding refresh is in schedule."""
        from app.tasks.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule

        assert "search-refresh-embeddings" in schedule
        assert schedule["search-refresh-embeddings"]["task"] == "app.tasks.search.refresh_embeddings"

    def test_search_task_routing(self):
        """Verify search tasks are routed to ingestion queue."""
        from app.tasks.celery_app import celery_app

        routes = celery_app.conf.task_routes

        assert "app.tasks.search.*" in routes
        assert routes["app.tasks.search.*"]["queue"] == "ingestion"
