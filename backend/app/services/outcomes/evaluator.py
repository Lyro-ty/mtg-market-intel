"""
Outcome evaluator service for recommendation accuracy tracking.

This module evaluates recommendation outcomes by comparing predictions
against actual price data to calculate accuracy metrics.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import structlog

from app.models.recommendation import ActionType, Recommendation
from app.models.price_snapshot import PriceSnapshot

logger = structlog.get_logger()

# Opportunity cost threshold for HOLD recommendations
HOLD_OPPORTUNITY_THRESHOLD = 0.15  # 15%


@dataclass
class OutcomeResult:
    """
    Result of evaluating a recommendation outcome.

    Attributes:
        price_end: Price at the end of the evaluation horizon
        price_peak: Best price during the horizon (max for BUY, min for SELL)
        price_peak_at: When the peak price was observed
        accuracy_end: Accuracy score based on end price (0.0 to 1.0)
        accuracy_peak: Accuracy score based on peak price (0.0 to 1.0)
        profit_pct_end: Actual profit/loss percentage at end
        profit_pct_peak: Actual profit/loss percentage at peak
    """
    price_end: float
    price_peak: float
    price_peak_at: datetime
    accuracy_end: float
    accuracy_peak: float
    profit_pct_end: float
    profit_pct_peak: float

    def __post_init__(self):
        """Clamp accuracy values to valid range."""
        self.accuracy_end = max(0.0, min(1.0, self.accuracy_end))
        self.accuracy_peak = max(0.0, min(1.0, self.accuracy_peak))


class OutcomeEvaluator:
    """
    Evaluates recommendation outcomes against actual price data.

    This service calculates how accurate a recommendation was by comparing
    the predicted price movement against what actually happened during
    the recommendation's horizon period.
    """

    def evaluate_recommendation(
        self,
        recommendation: Recommendation,
        snapshots: list[PriceSnapshot],
    ) -> Optional[OutcomeResult]:
        """
        Evaluate a recommendation against actual price data.

        Args:
            recommendation: The recommendation to evaluate
            snapshots: Price snapshots from the recommendation period.
                       Should be ordered chronologically (oldest first).

        Returns:
            OutcomeResult with accuracy metrics, or None if insufficient data
        """
        if not snapshots:
            logger.debug(
                "No price snapshots for evaluation",
                recommendation_id=recommendation.id,
                card_id=recommendation.card_id,
            )
            return None

        # Get prices from snapshots
        prices = [float(s.price) for s in snapshots]
        if not prices:
            return None

        # Get current price from recommendation, with fallback handling
        current_price = self._get_current_price(recommendation)
        if current_price is None or current_price <= 0:
            logger.warning(
                "Invalid current_price for recommendation",
                recommendation_id=recommendation.id,
                current_price=current_price,
            )
            return None

        action = ActionType(recommendation.action)

        if action == ActionType.BUY:
            return self._evaluate_buy(recommendation, snapshots, current_price)
        elif action == ActionType.SELL:
            return self._evaluate_sell(recommendation, snapshots, current_price)
        elif action == ActionType.HOLD:
            return self._evaluate_hold(recommendation, snapshots, current_price)
        else:
            logger.warning(
                "Unknown action type",
                recommendation_id=recommendation.id,
                action=recommendation.action,
            )
            return None

    def _get_current_price(self, recommendation: Recommendation) -> Optional[float]:
        """Extract current price from recommendation with fallback."""
        if recommendation.current_price is not None:
            return float(recommendation.current_price)
        return None

    def _get_target_price(self, recommendation: Recommendation, current_price: float) -> float:
        """Extract target price with fallback to current price."""
        if recommendation.target_price is not None:
            return float(recommendation.target_price)
        return current_price

    def _evaluate_buy(
        self,
        recommendation: Recommendation,
        snapshots: list[PriceSnapshot],
        current_price: float,
    ) -> OutcomeResult:
        """
        Evaluate a BUY recommendation.

        Success = price went up toward/past target.
        Peak = highest price observed (best exit point).
        """
        prices = [float(s.price) for s in snapshots]
        end_price = prices[-1]
        peak_price = max(prices)
        peak_at = next(s.time for s in snapshots if float(s.price) == peak_price)

        target_price = self._get_target_price(recommendation, current_price)

        # Predicted gain percentage
        predicted_gain = (target_price - current_price) / current_price

        # Actual gain at end and peak
        actual_gain_end = (end_price - current_price) / current_price
        actual_gain_peak = (peak_price - current_price) / current_price

        # Calculate accuracy
        # 0 if price went down, else ratio of actual vs predicted (capped at 1.0)
        if predicted_gain <= 0:
            # Edge case: target was same or lower than current
            # This shouldn't happen for BUY but handle gracefully
            accuracy_end = 1.0 if actual_gain_end >= 0 else 0.0
            accuracy_peak = 1.0 if actual_gain_peak >= 0 else 0.0
        else:
            if actual_gain_end <= 0:
                accuracy_end = 0.0
            else:
                accuracy_end = min(1.0, actual_gain_end / predicted_gain)

            if actual_gain_peak <= 0:
                accuracy_peak = 0.0
            else:
                accuracy_peak = min(1.0, actual_gain_peak / predicted_gain)

        logger.debug(
            "Evaluated BUY recommendation",
            recommendation_id=recommendation.id,
            current_price=current_price,
            target_price=target_price,
            end_price=end_price,
            peak_price=peak_price,
            accuracy_end=accuracy_end,
            accuracy_peak=accuracy_peak,
        )

        return OutcomeResult(
            price_end=end_price,
            price_peak=peak_price,
            price_peak_at=peak_at,
            accuracy_end=accuracy_end,
            accuracy_peak=accuracy_peak,
            profit_pct_end=actual_gain_end * 100,
            profit_pct_peak=actual_gain_peak * 100,
        )

    def _evaluate_sell(
        self,
        recommendation: Recommendation,
        snapshots: list[PriceSnapshot],
        current_price: float,
    ) -> OutcomeResult:
        """
        Evaluate a SELL recommendation.

        Success = price went down toward/past target.
        Peak = lowest price observed (confirms sell was good).
        """
        prices = [float(s.price) for s in snapshots]
        end_price = prices[-1]
        peak_price = min(prices)  # For SELL, "peak" is the lowest price
        peak_at = next(s.time for s in snapshots if float(s.price) == peak_price)

        target_price = self._get_target_price(recommendation, current_price)

        # Predicted drop percentage
        predicted_drop = (current_price - target_price) / current_price

        # Actual drop at end and peak (positive = price dropped as predicted)
        actual_drop_end = (current_price - end_price) / current_price
        actual_drop_peak = (current_price - peak_price) / current_price

        # Calculate accuracy
        # 0 if price went up, else ratio of actual vs predicted (capped at 1.0)
        if predicted_drop <= 0:
            # Edge case: target was same or higher than current
            accuracy_end = 1.0 if actual_drop_end >= 0 else 0.0
            accuracy_peak = 1.0 if actual_drop_peak >= 0 else 0.0
        else:
            if actual_drop_end <= 0:
                accuracy_end = 0.0
            else:
                accuracy_end = min(1.0, actual_drop_end / predicted_drop)

            if actual_drop_peak <= 0:
                accuracy_peak = 0.0
            else:
                accuracy_peak = min(1.0, actual_drop_peak / predicted_drop)

        logger.debug(
            "Evaluated SELL recommendation",
            recommendation_id=recommendation.id,
            current_price=current_price,
            target_price=target_price,
            end_price=end_price,
            peak_price=peak_price,
            accuracy_end=accuracy_end,
            accuracy_peak=accuracy_peak,
        )

        return OutcomeResult(
            price_end=end_price,
            price_peak=peak_price,
            price_peak_at=peak_at,
            accuracy_end=accuracy_end,
            accuracy_peak=accuracy_peak,
            profit_pct_end=actual_drop_end * 100,
            profit_pct_peak=actual_drop_peak * 100,
        )

    def _evaluate_hold(
        self,
        recommendation: Recommendation,
        snapshots: list[PriceSnapshot],
        current_price: float,
    ) -> OutcomeResult:
        """
        Evaluate a HOLD recommendation.

        Success = price stayed stable (no major moves).
        Uses opportunity cost model: HOLD succeeds if price didn't move >15%.
        """
        prices = [float(s.price) for s in snapshots]
        end_price = prices[-1]
        max_price = max(prices)
        min_price = min(prices)

        # Calculate max moves in each direction
        max_up_move = (max_price - current_price) / current_price
        max_down_move = (current_price - min_price) / current_price
        max_move = max(max_up_move, max_down_move)

        # Accuracy decreases as opportunity cost increases
        # 1.0 when no movement, 0.0 when movement >= threshold
        accuracy = max(0.0, 1.0 - (max_move / HOLD_OPPORTUNITY_THRESHOLD))

        # Track the direction of the biggest missed opportunity
        if max_up_move > max_down_move:
            peak_price = max_price
            profit_pct_peak = max_up_move * 100
        else:
            peak_price = min_price
            profit_pct_peak = -max_down_move * 100

        peak_at = next(s.time for s in snapshots if float(s.price) == peak_price)

        # Profit at end (relative to hold start)
        profit_pct_end = ((end_price - current_price) / current_price) * 100

        logger.debug(
            "Evaluated HOLD recommendation",
            recommendation_id=recommendation.id,
            current_price=current_price,
            end_price=end_price,
            max_price=max_price,
            min_price=min_price,
            max_move=max_move,
            accuracy=accuracy,
        )

        return OutcomeResult(
            price_end=end_price,
            price_peak=peak_price,
            price_peak_at=peak_at,
            accuracy_end=accuracy,
            accuracy_peak=accuracy,  # Same for HOLD
            profit_pct_end=profit_pct_end,
            profit_pct_peak=profit_pct_peak,
        )
