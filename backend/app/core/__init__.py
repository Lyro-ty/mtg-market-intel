"""
Core module containing configuration and shared utilities.
"""
from app.core.config import settings
from app.core.constants import (
    CardCondition,
    CardLanguage,
    normalize_condition,
    normalize_language,
    CONDITION_ALIASES,
    LANGUAGE_ALIASES,
    PERIOD_INTERVALS,
    get_currency_for_marketplace,
)

__all__ = [
    "settings",
    "CardCondition",
    "CardLanguage",
    "normalize_condition",
    "normalize_language",
    "CONDITION_ALIASES",
    "LANGUAGE_ALIASES",
    "PERIOD_INTERVALS",
    "get_currency_for_marketplace",
]

