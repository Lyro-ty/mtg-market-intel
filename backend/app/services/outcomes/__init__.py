"""
Outcome tracking services for recommendation evaluation.

This module provides services for evaluating recommendation outcomes
against actual price data to calculate accuracy metrics.
"""
from app.services.outcomes.evaluator import OutcomeEvaluator, OutcomeResult

__all__ = ["OutcomeEvaluator", "OutcomeResult"]
