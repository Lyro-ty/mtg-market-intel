"""
Marketplace constants for consistent naming across the application.

Provides centralized display names and normalization functions
to ensure marketplace names are consistent in charts, API responses,
and analytics.
"""

# Display names for each marketplace
# These are the canonical names shown to users
MARKETPLACE_DISPLAY_NAMES = {
    # Primary marketplaces
    "tcgplayer": "TCGPlayer",
    "cardmarket": "Cardmarket",
    "cardtrader": "CardTrader",
    "manapool": "Manapool",
    "mtgo": "MTGO",

    # Scryfall uses TCGPlayer for USD prices
    # This ensures charts don't show duplicate "Scryfall" and "TCGPlayer" series
    "scryfall": "TCGPlayer",

    # Alternative spellings/cases that might appear
    "tcg player": "TCGPlayer",
    "card market": "Cardmarket",
    "card trader": "CardTrader",
    "mana pool": "Manapool",
}

# Currency typically used by each marketplace
MARKETPLACE_CURRENCIES = {
    "tcgplayer": "USD",
    "scryfall": "USD",  # Scryfall provides both USD and EUR
    "cardmarket": "EUR",
    "cardtrader": "EUR",
    "manapool": "EUR",
    "mtgo": "TIX",
}

# Marketplace slugs that should be grouped together
# (e.g., scryfall USD prices are actually TCGPlayer prices)
MARKETPLACE_SLUG_ALIASES = {
    "scryfall": "tcgplayer",  # For USD prices
}


def get_marketplace_display_name(
    slug: str,
    currency: str = "USD",
) -> str:
    """
    Get consistent display name for a marketplace.

    Args:
        slug: Marketplace slug (e.g., "tcgplayer", "scryfall")
        currency: Currency of the price (affects scryfall handling)

    Returns:
        Human-readable marketplace name
    """
    slug_lower = slug.lower().strip()

    # Special handling for scryfall based on currency
    if slug_lower == "scryfall":
        if currency == "USD":
            return "TCGPlayer"
        elif currency == "EUR":
            return "Cardmarket"
        elif currency == "TIX":
            return "MTGO"

    return MARKETPLACE_DISPLAY_NAMES.get(slug_lower, slug.title())


def normalize_marketplace_slug(
    slug: str,
    currency: str = "USD",
) -> str:
    """
    Normalize marketplace slug for grouping.

    This helps combine data from different sources that represent
    the same marketplace (e.g., scryfall USD = tcgplayer).

    Args:
        slug: Marketplace slug
        currency: Currency of the price

    Returns:
        Normalized slug for grouping
    """
    slug_lower = slug.lower().strip()

    # Handle scryfall aliasing based on currency
    if slug_lower == "scryfall":
        if currency == "USD":
            return "tcgplayer"
        elif currency == "EUR":
            return "cardmarket"
        elif currency == "TIX":
            return "mtgo"

    return MARKETPLACE_SLUG_ALIASES.get(slug_lower, slug_lower)


def get_marketplace_currency(slug: str) -> str:
    """
    Get the default currency for a marketplace.

    Args:
        slug: Marketplace slug

    Returns:
        Currency code (e.g., "USD", "EUR", "TIX")
    """
    return MARKETPLACE_CURRENCIES.get(slug.lower(), "USD")


def is_same_marketplace(
    slug1: str,
    slug2: str,
    currency1: str = "USD",
    currency2: str = "USD",
) -> bool:
    """
    Check if two marketplace identifiers refer to the same marketplace.

    Useful for deduplication and grouping.

    Args:
        slug1: First marketplace slug
        slug2: Second marketplace slug
        currency1: Currency for first marketplace
        currency2: Currency for second marketplace

    Returns:
        True if they represent the same marketplace
    """
    norm1 = normalize_marketplace_slug(slug1, currency1)
    norm2 = normalize_marketplace_slug(slug2, currency2)
    return norm1 == norm2
