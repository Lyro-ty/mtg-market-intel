"""
Search filters for card attributes.

Provides functions to filter search results by colors, type, CMC, format, etc.
"""
import json
from typing import Optional


def apply_card_filters(
    cards: list[dict],
    colors: Optional[list[str]] = None,
    card_type: Optional[str] = None,
    cmc_min: Optional[float] = None,
    cmc_max: Optional[float] = None,
    format_legal: Optional[str] = None,
    rarity: Optional[str] = None,
    keywords: Optional[list[str]] = None,
) -> list[dict]:
    """
    Apply filters to a list of card dicts.

    Args:
        cards: List of card dictionaries
        colors: Filter by colors (e.g., ["R", "U"] for red or blue)
        card_type: Filter by type line (e.g., "Creature", "Instant")
        cmc_min: Minimum converted mana cost
        cmc_max: Maximum converted mana cost
        format_legal: Filter by format legality (e.g., "modern", "standard")
        rarity: Filter by rarity (e.g., "rare", "mythic")
        keywords: Filter by keywords (e.g., ["Flying", "Haste"])

    Returns:
        Filtered list of cards
    """
    result = cards

    if colors:
        result = _filter_by_colors(result, colors)

    if card_type:
        result = _filter_by_type(result, card_type)

    if cmc_min is not None or cmc_max is not None:
        result = _filter_by_cmc(result, cmc_min, cmc_max)

    if format_legal:
        result = _filter_by_format(result, format_legal)

    if rarity:
        result = _filter_by_rarity(result, rarity)

    if keywords:
        result = _filter_by_keywords(result, keywords)

    return result


def _filter_by_colors(cards: list[dict], colors: list[str]) -> list[dict]:
    """Filter cards that contain any of the specified colors."""
    filtered = []
    for card in cards:
        card_colors = card.get("colors", "[]")
        if isinstance(card_colors, str):
            try:
                card_colors = json.loads(card_colors)
            except json.JSONDecodeError:
                card_colors = []

        # Check if card has any of the requested colors
        if any(c in card_colors for c in colors):
            filtered.append(card)

    return filtered


def _filter_by_type(cards: list[dict], card_type: str) -> list[dict]:
    """Filter cards by type line (case-insensitive contains)."""
    card_type_lower = card_type.lower()
    return [
        card for card in cards
        if card.get("type_line") and card_type_lower in card["type_line"].lower()
    ]


def _filter_by_cmc(
    cards: list[dict],
    cmc_min: Optional[float],
    cmc_max: Optional[float],
) -> list[dict]:
    """Filter cards by CMC range."""
    filtered = []
    for card in cards:
        cmc = card.get("cmc")
        if cmc is None:
            continue

        if cmc_min is not None and cmc < cmc_min:
            continue
        if cmc_max is not None and cmc > cmc_max:
            continue

        filtered.append(card)

    return filtered


def _filter_by_format(cards: list[dict], format_legal: str) -> list[dict]:
    """Filter cards that are legal in the specified format."""
    format_lower = format_legal.lower()
    filtered = []

    for card in cards:
        legalities = card.get("legalities", "{}")
        if isinstance(legalities, str):
            try:
                legalities = json.loads(legalities)
            except json.JSONDecodeError:
                legalities = {}

        if legalities.get(format_lower) == "legal":
            filtered.append(card)

    return filtered


def _filter_by_rarity(cards: list[dict], rarity: str) -> list[dict]:
    """Filter cards by rarity."""
    rarity_lower = rarity.lower()
    return [
        card for card in cards
        if card.get("rarity", "").lower() == rarity_lower
    ]


def _filter_by_keywords(cards: list[dict], keywords: list[str]) -> list[dict]:
    """Filter cards that have any of the specified keywords."""
    keywords_lower = [k.lower() for k in keywords]
    filtered = []

    for card in cards:
        card_keywords = card.get("keywords", "[]")
        if isinstance(card_keywords, str):
            try:
                card_keywords = json.loads(card_keywords)
            except json.JSONDecodeError:
                card_keywords = []

        card_keywords_lower = [k.lower() for k in card_keywords]
        if any(k in card_keywords_lower for k in keywords_lower):
            filtered.append(card)

    return filtered


def build_filter_query(base_query, filters: dict):
    """
    Build SQLAlchemy query with filters applied.

    Args:
        base_query: Base SQLAlchemy select query
        filters: Dict of filter parameters

    Returns:
        Modified query with filters applied
    """
    from sqlalchemy import and_, or_
    from app.models import Card

    if filters.get("colors"):
        # Colors stored as JSON string, need to check contains
        color_conditions = []
        for color in filters["colors"]:
            color_conditions.append(Card.colors.contains(f'"{color}"'))
        base_query = base_query.where(or_(*color_conditions))

    if filters.get("card_type"):
        base_query = base_query.where(
            Card.type_line.ilike(f"%{filters['card_type']}%")
        )

    if filters.get("cmc_min") is not None:
        base_query = base_query.where(Card.cmc >= filters["cmc_min"])

    if filters.get("cmc_max") is not None:
        base_query = base_query.where(Card.cmc <= filters["cmc_max"])

    if filters.get("rarity"):
        base_query = base_query.where(Card.rarity == filters["rarity"].lower())

    return base_query
