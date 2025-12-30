"""
Tests for recommendation Celery tasks.

Tests verify task registration, async wrapper functionality,
and proper integration with OutcomeEvaluator service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from celery import Celery


class TestRecommendationTaskRegistration:
    """Test that recommendation tasks are properly registered with Celery."""

    def test_generate_recommendations_task_registered(self):
        """Verify generate_recommendations task is registered."""
        from app.tasks.recommendations import generate_recommendations

        assert generate_recommendations.name == "app.tasks.recommendations.generate_recommendations"
        assert callable(generate_recommendations)

    def test_generate_card_recommendations_task_registered(self):
        """Verify generate_card_recommendations task is registered."""
        from app.tasks.recommendations import generate_card_recommendations

        assert generate_card_recommendations.name == "app.tasks.recommendations.generate_card_recommendations"
        assert callable(generate_card_recommendations)

    def test_cleanup_old_recommendations_task_registered(self):
        """Verify cleanup_old_recommendations task is registered."""
        from app.tasks.recommendations import cleanup_old_recommendations

        assert cleanup_old_recommendations.name == "app.tasks.recommendations.cleanup_old_recommendations"
        assert callable(cleanup_old_recommendations)

    def test_evaluate_outcomes_task_registered(self):
        """Verify evaluate_outcomes task is registered."""
        from app.tasks.recommendations import evaluate_outcomes

        assert evaluate_outcomes.name == "app.tasks.recommendations.evaluate_outcomes"
        assert callable(evaluate_outcomes)


class TestEvaluateOutcomesTask:
    """Tests for the evaluate_outcomes Celery task."""

    @patch("app.tasks.recommendations.run_async")
    def test_evaluate_outcomes_calls_async_impl(self, mock_run_async):
        """Verify evaluate_outcomes delegates to async implementation."""
        mock_run_async.return_value = {
            "started_at": "2025-01-01T00:00:00+00:00",
            "total_processed": 10,
            "successful_evaluations": 8,
            "skipped_no_data": 1,
            "errors": 1,
            "error_details": ["Recommendation 123: Some error"],
        }

        from app.tasks.recommendations import evaluate_outcomes

        result = evaluate_outcomes.run()

        assert mock_run_async.called
        assert result["total_processed"] == 10
        assert result["successful_evaluations"] == 8

    @patch("app.tasks.recommendations.run_async")
    def test_evaluate_outcomes_with_custom_batch_size(self, mock_run_async):
        """Verify evaluate_outcomes accepts custom batch size."""
        mock_run_async.return_value = {
            "started_at": "2025-01-01T00:00:00+00:00",
            "total_processed": 50,
            "successful_evaluations": 50,
            "skipped_no_data": 0,
            "errors": 0,
            "error_details": [],
        }

        from app.tasks.recommendations import evaluate_outcomes

        result = evaluate_outcomes.run(batch_size=50)

        assert mock_run_async.called
        assert result["total_processed"] == 50

    def test_batch_size_constant_defined(self):
        """Verify OUTCOME_EVALUATION_BATCH_SIZE constant is defined."""
        from app.tasks.recommendations import OUTCOME_EVALUATION_BATCH_SIZE

        assert OUTCOME_EVALUATION_BATCH_SIZE == 100


class TestEvaluateOutcomesAsync:
    """Tests for the async implementation of evaluate_outcomes."""

    @pytest.mark.asyncio
    @patch("app.tasks.recommendations.create_task_session_maker")
    async def test_no_recommendations_returns_empty_results(self, mock_session_maker):
        """Verify task returns empty results when no recommendations to evaluate."""
        # Setup mocks
        mock_session = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()

        async_session_maker = MagicMock()
        async_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        async_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = (async_session_maker, mock_engine)

        # Mock empty query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        from app.tasks.recommendations import _evaluate_outcomes_async

        result = await _evaluate_outcomes_async(batch_size=100)

        assert result["total_processed"] == 0
        assert result["successful_evaluations"] == 0
        assert result["skipped_no_data"] == 0
        assert result["errors"] == 0

    @pytest.mark.asyncio
    @patch("app.tasks.recommendations.OutcomeEvaluator")
    @patch("app.tasks.recommendations.create_task_session_maker")
    async def test_successful_evaluation_updates_recommendation(
        self, mock_session_maker, mock_evaluator_cls
    ):
        """Verify successful evaluation updates recommendation fields."""
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(days=7)
        valid_until = now - timedelta(hours=1)

        # Create mock recommendation
        mock_recommendation = MagicMock()
        mock_recommendation.id = 1
        mock_recommendation.card_id = 100
        mock_recommendation.action = "BUY"
        mock_recommendation.created_at = created_at
        mock_recommendation.valid_until = valid_until
        mock_recommendation.current_price = Decimal("10.00")
        mock_recommendation.target_price = Decimal("15.00")

        # Create mock snapshots
        mock_snapshot = MagicMock()
        mock_snapshot.price = Decimal("12.50")
        mock_snapshot.time = valid_until

        # Setup session mock
        mock_session = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()

        async_session_maker = MagicMock()
        async_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        async_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = (async_session_maker, mock_engine)

        # First call returns recommendations, second call returns snapshots
        mock_rec_result = MagicMock()
        mock_rec_result.scalars.return_value.all.return_value = [mock_recommendation]

        mock_snap_result = MagicMock()
        mock_snap_result.scalars.return_value.all.return_value = [mock_snapshot]

        mock_session.execute = AsyncMock(side_effect=[mock_rec_result, mock_snap_result])
        mock_session.commit = AsyncMock()

        # Setup evaluator mock
        from app.services.outcomes.evaluator import OutcomeResult

        mock_outcome = OutcomeResult(
            price_end=12.50,
            price_peak=14.00,
            price_peak_at=created_at + timedelta(days=3),
            accuracy_end=0.50,
            accuracy_peak=0.80,
            profit_pct_end=25.0,
            profit_pct_peak=40.0,
        )
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate_recommendation.return_value = mock_outcome
        mock_evaluator_cls.return_value = mock_evaluator

        from app.tasks.recommendations import _evaluate_outcomes_async

        result = await _evaluate_outcomes_async(batch_size=100)

        assert result["total_processed"] == 1
        assert result["successful_evaluations"] == 1
        assert result["skipped_no_data"] == 0
        assert result["errors"] == 0

        # Verify recommendation was updated
        assert mock_recommendation.outcome_price_end == 12.50
        assert mock_recommendation.outcome_price_peak == 14.00
        assert mock_recommendation.accuracy_score_end == 0.50
        assert mock_recommendation.accuracy_score_peak == 0.80
        assert mock_recommendation.actual_profit_pct_end == 25.0
        assert mock_recommendation.actual_profit_pct_peak == 40.0

    @pytest.mark.asyncio
    @patch("app.tasks.recommendations.OutcomeEvaluator")
    @patch("app.tasks.recommendations.create_task_session_maker")
    async def test_no_snapshots_skips_recommendation(
        self, mock_session_maker, mock_evaluator_cls
    ):
        """Verify recommendation is skipped when no price data available."""
        now = datetime.now(timezone.utc)

        # Create mock recommendation - explicitly set outcome_evaluated_at to None
        mock_recommendation = MagicMock()
        mock_recommendation.id = 1
        mock_recommendation.card_id = 100
        mock_recommendation.action = "BUY"
        mock_recommendation.created_at = now - timedelta(days=7)
        mock_recommendation.valid_until = now - timedelta(hours=1)
        mock_recommendation.outcome_evaluated_at = None  # Track original state

        # Setup session mock
        mock_session = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()

        async_session_maker = MagicMock()
        async_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        async_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = (async_session_maker, mock_engine)

        # First call returns recommendations, second call returns empty snapshots
        mock_rec_result = MagicMock()
        mock_rec_result.scalars.return_value.all.return_value = [mock_recommendation]

        mock_snap_result = MagicMock()
        mock_snap_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(side_effect=[mock_rec_result, mock_snap_result])
        mock_session.commit = AsyncMock()

        # Setup evaluator to return None (no data)
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate_recommendation.return_value = None
        mock_evaluator_cls.return_value = mock_evaluator

        from app.tasks.recommendations import _evaluate_outcomes_async

        result = await _evaluate_outcomes_async(batch_size=100)

        assert result["total_processed"] == 1
        assert result["successful_evaluations"] == 0
        assert result["skipped_no_data"] == 1
        assert result["errors"] == 0

        # Verify outcome_evaluated_at was NOT set (allows retry)
        # Since we skipped processing, it should still be None
        assert mock_recommendation.outcome_evaluated_at is None

    @pytest.mark.asyncio
    @patch("app.tasks.recommendations.OutcomeEvaluator")
    @patch("app.tasks.recommendations.create_task_session_maker")
    async def test_error_continues_processing_other_recommendations(
        self, mock_session_maker, mock_evaluator_cls
    ):
        """Verify errors are logged but processing continues."""
        now = datetime.now(timezone.utc)

        # Create two mock recommendations
        mock_rec_1 = MagicMock()
        mock_rec_1.id = 1
        mock_rec_1.card_id = 100
        mock_rec_1.action = "BUY"
        mock_rec_1.created_at = now - timedelta(days=7)
        mock_rec_1.valid_until = now - timedelta(hours=1)

        mock_rec_2 = MagicMock()
        mock_rec_2.id = 2
        mock_rec_2.card_id = 200
        mock_rec_2.action = "SELL"
        mock_rec_2.created_at = now - timedelta(days=7)
        mock_rec_2.valid_until = now - timedelta(hours=1)

        # Setup session mock
        mock_session = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()

        async_session_maker = MagicMock()
        async_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        async_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = (async_session_maker, mock_engine)

        # First call returns recommendations, subsequent calls return snapshots
        mock_rec_result = MagicMock()
        mock_rec_result.scalars.return_value.all.return_value = [mock_rec_1, mock_rec_2]

        mock_snap_result = MagicMock()
        mock_snap_result.scalars.return_value.all.return_value = [MagicMock(price=Decimal("10.00"), time=now)]

        mock_session.execute = AsyncMock(side_effect=[
            mock_rec_result,
            mock_snap_result,  # For rec 1
            mock_snap_result,  # For rec 2
        ])
        mock_session.commit = AsyncMock()

        # Setup evaluator - first call raises error, second succeeds
        from app.services.outcomes.evaluator import OutcomeResult

        mock_outcome = OutcomeResult(
            price_end=10.00,
            price_peak=12.00,
            price_peak_at=now - timedelta(days=2),
            accuracy_end=0.75,
            accuracy_peak=0.90,
            profit_pct_end=10.0,
            profit_pct_peak=20.0,
        )
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate_recommendation.side_effect = [
            Exception("Test error"),
            mock_outcome,
        ]
        mock_evaluator_cls.return_value = mock_evaluator

        from app.tasks.recommendations import _evaluate_outcomes_async

        result = await _evaluate_outcomes_async(batch_size=100)

        assert result["total_processed"] == 2
        assert result["successful_evaluations"] == 1
        assert result["errors"] == 1
        assert len(result["error_details"]) == 1
        assert "Recommendation 1" in result["error_details"][0]


class TestCeleryBeatScheduleRecommendations:
    """Test that Celery beat schedule includes recommendation tasks."""

    def test_recommendations_included_in_autodiscover(self):
        """Verify recommendations module is included for autodiscovery."""
        from app.tasks.celery_app import celery_app

        assert "app.tasks.recommendations" in celery_app.conf.include

    def test_recommendations_task_routing(self):
        """Verify recommendations tasks are routed to recommendations queue."""
        from app.tasks.celery_app import celery_app

        routes = celery_app.conf.task_routes
        assert "app.tasks.recommendations.*" in routes
        assert routes["app.tasks.recommendations.*"]["queue"] == "recommendations"
