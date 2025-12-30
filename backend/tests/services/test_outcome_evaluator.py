"""
Tests for the OutcomeEvaluator service.

Tests cover:
- BUY recommendations (price up/down/flat scenarios)
- SELL recommendations (price down/up/flat scenarios)
- HOLD recommendations (stable/volatile scenarios)
- Edge cases (no data, zero prices, missing target)
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

from app.services.outcomes.evaluator import (
    OutcomeEvaluator,
    OutcomeResult,
    HOLD_OPPORTUNITY_THRESHOLD,
)


class TestOutcomeResult:
    """Test the OutcomeResult dataclass."""

    def test_clamps_accuracy_to_valid_range(self):
        """Accuracy should be clamped to 0.0-1.0 range."""
        result = OutcomeResult(
            price_end=10.0,
            price_peak=12.0,
            price_peak_at=datetime.now(timezone.utc),
            accuracy_end=1.5,  # Should be clamped to 1.0
            accuracy_peak=-0.5,  # Should be clamped to 0.0
            profit_pct_end=10.0,
            profit_pct_peak=20.0,
        )
        assert result.accuracy_end == 1.0
        assert result.accuracy_peak == 0.0


class TestOutcomeEvaluatorBuy:
    """Test BUY recommendation evaluation."""

    @pytest.fixture
    def evaluator(self):
        return OutcomeEvaluator()

    @pytest.fixture
    def base_time(self):
        return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def _make_recommendation(
        self,
        action: str = "BUY",
        current_price: float = 10.0,
        target_price: float = 15.0,
    ) -> MagicMock:
        """Create a mock recommendation."""
        rec = MagicMock()
        rec.id = 1
        rec.card_id = 100
        rec.action = action
        rec.current_price = current_price
        rec.target_price = target_price
        return rec

    def _make_snapshots(
        self, base_time: datetime, prices: list[float]
    ) -> list[MagicMock]:
        """Create mock price snapshots."""
        snapshots = []
        for i, price in enumerate(prices):
            s = MagicMock()
            s.price = price
            s.time = base_time + timedelta(hours=i)
            snapshots.append(s)
        return snapshots

    def test_buy_price_reaches_target_exactly(self, evaluator, base_time):
        """BUY: Price goes from $10 to exactly $15 target = 100% accuracy."""
        rec = self._make_recommendation(current_price=10.0, target_price=15.0)
        snapshots = self._make_snapshots(base_time, [11.0, 13.0, 15.0])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        assert result.accuracy_end == 1.0
        assert result.accuracy_peak == 1.0
        assert result.price_end == 15.0
        assert result.price_peak == 15.0
        assert result.profit_pct_end == pytest.approx(50.0, rel=0.01)

    def test_buy_price_exceeds_target(self, evaluator, base_time):
        """BUY: Price goes beyond target = 100% accuracy (capped)."""
        rec = self._make_recommendation(current_price=10.0, target_price=15.0)
        snapshots = self._make_snapshots(base_time, [12.0, 18.0, 20.0])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        assert result.accuracy_end == 1.0  # Capped at 1.0
        assert result.accuracy_peak == 1.0
        assert result.price_end == 20.0
        assert result.price_peak == 20.0
        assert result.profit_pct_end == pytest.approx(100.0, rel=0.01)

    def test_buy_price_partial_gain(self, evaluator, base_time):
        """BUY: Price goes up 50% of predicted gain = 50% accuracy."""
        rec = self._make_recommendation(current_price=10.0, target_price=15.0)
        # Target = 50% gain, actual end = 25% gain = 0.5 accuracy
        snapshots = self._make_snapshots(base_time, [11.0, 12.0, 12.5])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        assert result.accuracy_end == pytest.approx(0.5, rel=0.01)
        assert result.price_end == 12.5
        assert result.profit_pct_end == pytest.approx(25.0, rel=0.01)

    def test_buy_price_goes_down(self, evaluator, base_time):
        """BUY: Price goes down = 0% accuracy."""
        rec = self._make_recommendation(current_price=10.0, target_price=15.0)
        snapshots = self._make_snapshots(base_time, [9.5, 9.0, 8.0])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        assert result.accuracy_end == 0.0
        assert result.accuracy_peak == 0.0  # Even peak was below start
        assert result.price_end == 8.0
        assert result.profit_pct_end == pytest.approx(-20.0, rel=0.01)

    def test_buy_peak_higher_than_end(self, evaluator, base_time):
        """BUY: Peak accuracy can differ from end accuracy."""
        rec = self._make_recommendation(current_price=10.0, target_price=15.0)
        # Spikes to $15 (100% of target) then falls to $12.5 (50% of target)
        snapshots = self._make_snapshots(base_time, [12.0, 15.0, 12.5])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        assert result.accuracy_peak == 1.0  # Hit the target
        assert result.accuracy_end == pytest.approx(0.5, rel=0.01)
        assert result.price_peak == 15.0
        assert result.price_end == 12.5
        assert result.profit_pct_peak == pytest.approx(50.0, rel=0.01)
        assert result.profit_pct_end == pytest.approx(25.0, rel=0.01)


class TestOutcomeEvaluatorSell:
    """Test SELL recommendation evaluation."""

    @pytest.fixture
    def evaluator(self):
        return OutcomeEvaluator()

    @pytest.fixture
    def base_time(self):
        return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def _make_recommendation(
        self,
        action: str = "SELL",
        current_price: float = 20.0,
        target_price: float = 15.0,
    ) -> MagicMock:
        rec = MagicMock()
        rec.id = 1
        rec.card_id = 100
        rec.action = action
        rec.current_price = current_price
        rec.target_price = target_price
        return rec

    def _make_snapshots(
        self, base_time: datetime, prices: list[float]
    ) -> list[MagicMock]:
        snapshots = []
        for i, price in enumerate(prices):
            s = MagicMock()
            s.price = price
            s.time = base_time + timedelta(hours=i)
            snapshots.append(s)
        return snapshots

    def test_sell_price_reaches_target_exactly(self, evaluator, base_time):
        """SELL: Price drops from $20 to exactly $15 target = 100% accuracy."""
        rec = self._make_recommendation(current_price=20.0, target_price=15.0)
        snapshots = self._make_snapshots(base_time, [18.0, 16.0, 15.0])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        assert result.accuracy_end == 1.0
        assert result.accuracy_peak == 1.0
        assert result.price_end == 15.0
        assert result.price_peak == 15.0  # Lowest price for SELL
        assert result.profit_pct_end == pytest.approx(25.0, rel=0.01)

    def test_sell_price_drops_further(self, evaluator, base_time):
        """SELL: Price drops beyond target = 100% accuracy (capped)."""
        rec = self._make_recommendation(current_price=20.0, target_price=15.0)
        snapshots = self._make_snapshots(base_time, [16.0, 12.0, 10.0])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        assert result.accuracy_end == 1.0
        assert result.accuracy_peak == 1.0
        assert result.price_end == 10.0
        assert result.price_peak == 10.0

    def test_sell_price_partial_drop(self, evaluator, base_time):
        """SELL: Price drops 50% of predicted = 50% accuracy."""
        rec = self._make_recommendation(current_price=20.0, target_price=15.0)
        # Target = 25% drop, actual = 12.5% drop
        snapshots = self._make_snapshots(base_time, [19.0, 18.0, 17.5])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        assert result.accuracy_end == pytest.approx(0.5, rel=0.01)
        assert result.price_end == 17.5
        assert result.profit_pct_end == pytest.approx(12.5, rel=0.01)

    def test_sell_price_goes_up(self, evaluator, base_time):
        """SELL: Price goes up = 0% accuracy."""
        rec = self._make_recommendation(current_price=20.0, target_price=15.0)
        snapshots = self._make_snapshots(base_time, [21.0, 23.0, 25.0])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        assert result.accuracy_end == 0.0
        assert result.accuracy_peak == 0.0
        assert result.price_end == 25.0
        assert result.profit_pct_end == pytest.approx(-25.0, rel=0.01)

    def test_sell_peak_lower_than_end(self, evaluator, base_time):
        """SELL: Peak (lowest) can differ from end price."""
        rec = self._make_recommendation(current_price=20.0, target_price=15.0)
        # Drops to $15 (100%) then recovers to $17.5 (50%)
        snapshots = self._make_snapshots(base_time, [18.0, 15.0, 17.5])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        assert result.accuracy_peak == 1.0
        assert result.accuracy_end == pytest.approx(0.5, rel=0.01)
        assert result.price_peak == 15.0  # Lowest
        assert result.price_end == 17.5


class TestOutcomeEvaluatorHold:
    """Test HOLD recommendation evaluation."""

    @pytest.fixture
    def evaluator(self):
        return OutcomeEvaluator()

    @pytest.fixture
    def base_time(self):
        return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def _make_recommendation(
        self,
        action: str = "HOLD",
        current_price: float = 10.0,
        target_price: float = None,
    ) -> MagicMock:
        rec = MagicMock()
        rec.id = 1
        rec.card_id = 100
        rec.action = action
        rec.current_price = current_price
        rec.target_price = target_price
        return rec

    def _make_snapshots(
        self, base_time: datetime, prices: list[float]
    ) -> list[MagicMock]:
        snapshots = []
        for i, price in enumerate(prices):
            s = MagicMock()
            s.price = price
            s.time = base_time + timedelta(hours=i)
            snapshots.append(s)
        return snapshots

    def test_hold_price_stays_flat(self, evaluator, base_time):
        """HOLD: Price stays flat = 100% accuracy."""
        rec = self._make_recommendation(current_price=10.0)
        snapshots = self._make_snapshots(base_time, [10.0, 10.0, 10.0])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        assert result.accuracy_end == 1.0
        assert result.accuracy_peak == 1.0
        assert result.profit_pct_end == pytest.approx(0.0, rel=0.01)

    def test_hold_price_minor_fluctuation(self, evaluator, base_time):
        """HOLD: Minor fluctuation < 15% threshold = high accuracy."""
        rec = self._make_recommendation(current_price=10.0)
        # 5% fluctuation = (0.05 / 0.15) = 0.33 opportunity cost
        # accuracy = 1 - 0.33 = 0.67
        snapshots = self._make_snapshots(base_time, [10.0, 10.5, 10.2])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        # Max move is 5% up, so accuracy = 1 - (0.05 / 0.15) = 0.67
        assert result.accuracy_end == pytest.approx(0.667, rel=0.01)

    def test_hold_price_reaches_threshold(self, evaluator, base_time):
        """HOLD: Movement exactly at 15% threshold = 0% accuracy."""
        rec = self._make_recommendation(current_price=10.0)
        snapshots = self._make_snapshots(base_time, [10.0, 11.5, 10.5])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        assert result.accuracy_end == pytest.approx(0.0, rel=0.01)

    def test_hold_price_exceeds_threshold(self, evaluator, base_time):
        """HOLD: Movement exceeds threshold = 0% accuracy."""
        rec = self._make_recommendation(current_price=10.0)
        snapshots = self._make_snapshots(base_time, [10.0, 12.0, 11.0])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        assert result.accuracy_end == 0.0

    def test_hold_tracks_upward_opportunity(self, evaluator, base_time):
        """HOLD: Tracks upward missed opportunity."""
        rec = self._make_recommendation(current_price=10.0)
        # Price went up 20% - should have been a BUY
        snapshots = self._make_snapshots(base_time, [11.0, 12.0, 11.5])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        assert result.price_peak == 12.0  # Highest = missed opportunity
        assert result.profit_pct_peak == pytest.approx(20.0, rel=0.01)

    def test_hold_tracks_downward_opportunity(self, evaluator, base_time):
        """HOLD: Tracks downward missed opportunity."""
        rec = self._make_recommendation(current_price=10.0)
        # Price went down 25% - should have been a SELL
        snapshots = self._make_snapshots(base_time, [9.0, 7.5, 8.5])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        assert result.price_peak == 7.5  # Lowest = missed opportunity
        assert result.profit_pct_peak == pytest.approx(-25.0, rel=0.01)


class TestOutcomeEvaluatorEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def evaluator(self):
        return OutcomeEvaluator()

    @pytest.fixture
    def base_time(self):
        return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def _make_recommendation(
        self,
        action: str = "BUY",
        current_price: float = 10.0,
        target_price: float = 15.0,
    ) -> MagicMock:
        rec = MagicMock()
        rec.id = 1
        rec.card_id = 100
        rec.action = action
        rec.current_price = current_price
        rec.target_price = target_price
        return rec

    def _make_snapshots(
        self, base_time: datetime, prices: list[float]
    ) -> list[MagicMock]:
        snapshots = []
        for i, price in enumerate(prices):
            s = MagicMock()
            s.price = price
            s.time = base_time + timedelta(hours=i)
            snapshots.append(s)
        return snapshots

    def test_no_snapshots_returns_none(self, evaluator):
        """No price snapshots = None result (skip, retry later)."""
        rec = self._make_recommendation()
        result = evaluator.evaluate_recommendation(rec, [])

        assert result is None

    def test_zero_current_price_returns_none(self, evaluator, base_time):
        """Zero current price = None result (avoids division by zero)."""
        rec = self._make_recommendation(current_price=0.0)
        snapshots = self._make_snapshots(base_time, [10.0, 11.0, 12.0])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is None

    def test_negative_current_price_returns_none(self, evaluator, base_time):
        """Negative current price = None result."""
        rec = self._make_recommendation(current_price=-10.0)
        snapshots = self._make_snapshots(base_time, [10.0, 11.0, 12.0])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is None

    def test_none_current_price_returns_none(self, evaluator, base_time):
        """None current price = None result."""
        rec = self._make_recommendation()
        rec.current_price = None
        snapshots = self._make_snapshots(base_time, [10.0, 11.0, 12.0])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is None

    def test_none_target_price_uses_current(self, evaluator, base_time):
        """None target price falls back to current price."""
        rec = self._make_recommendation(current_price=10.0)
        rec.target_price = None
        snapshots = self._make_snapshots(base_time, [10.0, 11.0, 10.5])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        # With no target, any positive movement is considered a win
        # But predicted_gain = 0, so edge case handling kicks in
        assert result.accuracy_end == 1.0  # Positive gain with no target = success

    def test_single_snapshot(self, evaluator, base_time):
        """Single snapshot should work."""
        rec = self._make_recommendation(current_price=10.0, target_price=15.0)
        snapshots = self._make_snapshots(base_time, [12.0])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        assert result.price_end == 12.0
        assert result.price_peak == 12.0

    def test_buy_same_current_and_target(self, evaluator, base_time):
        """BUY with current == target (edge case)."""
        rec = self._make_recommendation(current_price=10.0, target_price=10.0)
        snapshots = self._make_snapshots(base_time, [10.0, 11.0, 10.5])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        # predicted_gain = 0, so edge case: any positive gain = success
        assert result.accuracy_end == 1.0

    def test_sell_same_current_and_target(self, evaluator, base_time):
        """SELL with current == target (edge case)."""
        rec = self._make_recommendation(action="SELL", current_price=10.0, target_price=10.0)
        snapshots = self._make_snapshots(base_time, [10.0, 9.0, 9.5])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        # predicted_drop = 0, any positive drop = success
        assert result.accuracy_end == 1.0

    def test_peak_at_timestamp_is_correct(self, evaluator, base_time):
        """Peak timestamp should be when peak price occurred."""
        rec = self._make_recommendation(current_price=10.0, target_price=15.0)
        snapshots = self._make_snapshots(base_time, [11.0, 14.0, 12.0])

        result = evaluator.evaluate_recommendation(rec, snapshots)

        assert result is not None
        # Peak ($14) occurred at index 1 = base_time + 1 hour
        expected_peak_time = base_time + timedelta(hours=1)
        assert result.price_peak_at == expected_peak_time


class TestHoldOpportunityThreshold:
    """Test the HOLD opportunity threshold constant."""

    def test_threshold_is_15_percent(self):
        """Verify HOLD_OPPORTUNITY_THRESHOLD is 15%."""
        assert HOLD_OPPORTUNITY_THRESHOLD == 0.15
