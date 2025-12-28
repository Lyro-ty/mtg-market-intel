"""Tests for search filters."""
import pytest
from unittest.mock import MagicMock

from app.services.search.filters import apply_card_filters, build_filter_query


class TestSearchFilters:
    """Test search filter functions."""

    def test_filter_by_colors(self):
        """Test filtering cards by color."""
        cards = [
            {"id": 1, "name": "Lightning Bolt", "colors": '["R"]'},
            {"id": 2, "name": "Counterspell", "colors": '["U"]'},
            {"id": 3, "name": "Giant Growth", "colors": '["G"]'},
        ]

        filtered = apply_card_filters(cards, colors=["R"])
        assert len(filtered) == 1
        assert filtered[0]["name"] == "Lightning Bolt"

    def test_filter_by_type(self):
        """Test filtering cards by type."""
        cards = [
            {"id": 1, "name": "Lightning Bolt", "type_line": "Instant"},
            {"id": 2, "name": "Llanowar Elves", "type_line": "Creature - Elf Druid"},
            {"id": 3, "name": "Wrath of God", "type_line": "Sorcery"},
        ]

        filtered = apply_card_filters(cards, card_type="Creature")
        assert len(filtered) == 1
        assert filtered[0]["name"] == "Llanowar Elves"

    def test_filter_by_cmc_range(self):
        """Test filtering cards by CMC range."""
        cards = [
            {"id": 1, "name": "Lightning Bolt", "cmc": 1},
            {"id": 2, "name": "Counterspell", "cmc": 2},
            {"id": 3, "name": "Wrath of God", "cmc": 4},
        ]

        filtered = apply_card_filters(cards, cmc_min=1, cmc_max=2)
        assert len(filtered) == 2

    def test_filter_by_format_legality(self):
        """Test filtering cards by format legality."""
        cards = [
            {"id": 1, "name": "Lightning Bolt", "legalities": '{"modern": "legal", "standard": "not_legal"}'},
            {"id": 2, "name": "Oko", "legalities": '{"modern": "banned", "standard": "banned"}'},
        ]

        filtered = apply_card_filters(cards, format_legal="modern")
        assert len(filtered) == 1
        assert filtered[0]["name"] == "Lightning Bolt"
