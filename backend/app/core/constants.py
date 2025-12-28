"""
Core constants and enums for the MTG Market Intel application.

This module provides standardized enums for card conditions and languages,
along with normalization functions to map external data sources to our
internal representation.
"""
from enum import Enum
from typing import Optional


class CardCondition(str, Enum):
    """
    Standardized card condition grades.

    These map to industry-standard condition grades used across
    major marketplaces (TCGPlayer, CardTrader, Cardmarket).
    """
    MINT = "MINT"
    NEAR_MINT = "NEAR_MINT"
    LIGHTLY_PLAYED = "LIGHTLY_PLAYED"
    MODERATELY_PLAYED = "MODERATELY_PLAYED"
    HEAVILY_PLAYED = "HEAVILY_PLAYED"
    DAMAGED = "DAMAGED"


class CardLanguage(str, Enum):
    """
    Supported card languages.

    Covers all languages in which Magic: The Gathering cards
    have been officially printed.
    """
    ENGLISH = "English"
    JAPANESE = "Japanese"
    GERMAN = "German"
    FRENCH = "French"
    ITALIAN = "Italian"
    SPANISH = "Spanish"
    PORTUGUESE = "Portuguese"
    KOREAN = "Korean"
    CHINESE_SIMPLIFIED = "Chinese Simplified"
    CHINESE_TRADITIONAL = "Chinese Traditional"
    RUSSIAN = "Russian"
    PHYREXIAN = "Phyrexian"


# Condition normalization mappings from external sources
# Maps various external condition strings to our standardized enum
CONDITION_ALIASES: dict[str | None, CardCondition] = {
    # TCGPlayer conditions
    "Near Mint": CardCondition.NEAR_MINT,
    "Lightly Played": CardCondition.LIGHTLY_PLAYED,
    "Moderately Played": CardCondition.MODERATELY_PLAYED,
    "Heavily Played": CardCondition.HEAVILY_PLAYED,
    "Damaged": CardCondition.DAMAGED,

    # CardTrader / Cardmarket abbreviations
    "M": CardCondition.MINT,
    "NM": CardCondition.NEAR_MINT,
    "LP": CardCondition.LIGHTLY_PLAYED,
    "SP": CardCondition.LIGHTLY_PLAYED,  # Slightly Played = LP
    "MP": CardCondition.MODERATELY_PLAYED,
    "HP": CardCondition.HEAVILY_PLAYED,
    "DMG": CardCondition.DAMAGED,
    "PO": CardCondition.DAMAGED,  # Poor = Damaged

    # Cardmarket specific grades
    "Mint": CardCondition.MINT,
    "Near Mint/Mint": CardCondition.NEAR_MINT,
    "Excellent": CardCondition.NEAR_MINT,
    "Good": CardCondition.LIGHTLY_PLAYED,
    "Light Played": CardCondition.LIGHTLY_PLAYED,
    "Played": CardCondition.MODERATELY_PLAYED,
    "Poor": CardCondition.DAMAGED,

    # Common variations
    "near mint": CardCondition.NEAR_MINT,
    "nm": CardCondition.NEAR_MINT,
    "lp": CardCondition.LIGHTLY_PLAYED,
    "mp": CardCondition.MODERATELY_PLAYED,
    "hp": CardCondition.HEAVILY_PLAYED,

    # Default for sources that don't track condition
    None: CardCondition.NEAR_MINT,
    "": CardCondition.NEAR_MINT,
}


# Language normalization mappings from external sources
LANGUAGE_ALIASES: dict[str | None, CardLanguage] = {
    # ISO 639-1 / Scryfall codes
    "en": CardLanguage.ENGLISH,
    "ja": CardLanguage.JAPANESE,
    "de": CardLanguage.GERMAN,
    "fr": CardLanguage.FRENCH,
    "it": CardLanguage.ITALIAN,
    "es": CardLanguage.SPANISH,
    "pt": CardLanguage.PORTUGUESE,
    "ko": CardLanguage.KOREAN,
    "zhs": CardLanguage.CHINESE_SIMPLIFIED,
    "zht": CardLanguage.CHINESE_TRADITIONAL,
    "ru": CardLanguage.RUSSIAN,
    "ph": CardLanguage.PHYREXIAN,

    # Uppercase variants
    "EN": CardLanguage.ENGLISH,
    "JA": CardLanguage.JAPANESE,
    "DE": CardLanguage.GERMAN,
    "FR": CardLanguage.FRENCH,
    "IT": CardLanguage.ITALIAN,
    "ES": CardLanguage.SPANISH,
    "PT": CardLanguage.PORTUGUESE,
    "KO": CardLanguage.KOREAN,
    "ZHS": CardLanguage.CHINESE_SIMPLIFIED,
    "ZHT": CardLanguage.CHINESE_TRADITIONAL,
    "RU": CardLanguage.RUSSIAN,
    "PH": CardLanguage.PHYREXIAN,

    # Full names (case insensitive mapping done in function)
    "English": CardLanguage.ENGLISH,
    "Japanese": CardLanguage.JAPANESE,
    "German": CardLanguage.GERMAN,
    "French": CardLanguage.FRENCH,
    "Italian": CardLanguage.ITALIAN,
    "Spanish": CardLanguage.SPANISH,
    "Portuguese": CardLanguage.PORTUGUESE,
    "Korean": CardLanguage.KOREAN,
    "Chinese Simplified": CardLanguage.CHINESE_SIMPLIFIED,
    "Chinese Traditional": CardLanguage.CHINESE_TRADITIONAL,
    "Russian": CardLanguage.RUSSIAN,
    "Phyrexian": CardLanguage.PHYREXIAN,

    # Common variations
    "Chinese": CardLanguage.CHINESE_SIMPLIFIED,  # Default to simplified
    "Chinese (Simplified)": CardLanguage.CHINESE_SIMPLIFIED,
    "Chinese (Traditional)": CardLanguage.CHINESE_TRADITIONAL,
    "Simplified Chinese": CardLanguage.CHINESE_SIMPLIFIED,
    "Traditional Chinese": CardLanguage.CHINESE_TRADITIONAL,

    # Default
    None: CardLanguage.ENGLISH,
    "": CardLanguage.ENGLISH,
}


# Currency to marketplace mapping
MARKETPLACE_CURRENCIES: dict[str, str] = {
    "tcgplayer": "USD",
    "manapool": "USD",
    "cardtrader": "EUR",
    "cardmarket": "EUR",
    "scryfall": "USD",  # Scryfall reports USD prices
}


# Period intervals for TimescaleDB queries
PERIOD_INTERVALS: dict[str, str] = {
    "1d": "1 day",
    "7d": "7 days",
    "30d": "30 days",
    "90d": "90 days",
    "1y": "1 year",
    "all": "10 years",  # Effectively "all time"
}


def normalize_condition(condition: Optional[str]) -> CardCondition:
    """
    Normalize any condition string to our standard CardCondition enum.

    Args:
        condition: Raw condition string from external source

    Returns:
        Normalized CardCondition enum value

    Examples:
        >>> normalize_condition("Near Mint")
        CardCondition.NEAR_MINT
        >>> normalize_condition("LP")
        CardCondition.LIGHTLY_PLAYED
        >>> normalize_condition(None)
        CardCondition.NEAR_MINT
    """
    if condition is None or condition == "":
        return CardCondition.NEAR_MINT

    # Try exact match first
    if condition in CONDITION_ALIASES:
        return CONDITION_ALIASES[condition]

    # Try case-insensitive match
    condition_lower = condition.lower().strip()
    for key, value in CONDITION_ALIASES.items():
        if key and key.lower() == condition_lower:
            return value

    # Default to Near Mint if no match found
    return CardCondition.NEAR_MINT


def normalize_language(language: Optional[str]) -> CardLanguage:
    """
    Normalize any language string to our standard CardLanguage enum.

    Args:
        language: Raw language string from external source

    Returns:
        Normalized CardLanguage enum value

    Examples:
        >>> normalize_language("en")
        CardLanguage.ENGLISH
        >>> normalize_language("Japanese")
        CardLanguage.JAPANESE
        >>> normalize_language(None)
        CardLanguage.ENGLISH
    """
    if language is None or language == "":
        return CardLanguage.ENGLISH

    # Try exact match first
    if language in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[language]

    # Try case-insensitive match
    language_lower = language.lower().strip()
    for key, value in LANGUAGE_ALIASES.items():
        if key and key.lower() == language_lower:
            return value

    # Default to English if no match found
    return CardLanguage.ENGLISH


def get_currency_for_marketplace(marketplace_name: str) -> str:
    """
    Get the default currency for a marketplace.

    Args:
        marketplace_name: Name of the marketplace (case-insensitive)

    Returns:
        Currency code (USD, EUR, etc.)
    """
    return MARKETPLACE_CURRENCIES.get(marketplace_name.lower(), "USD")
