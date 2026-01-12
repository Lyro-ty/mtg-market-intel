"""
Tests for cursor-based pagination utilities.
"""
import pytest
from datetime import datetime, date
from decimal import Decimal

from app.api.utils.pagination import (
    encode_cursor,
    decode_cursor,
    build_cursor_response,
    build_cursor_from_item,
)


class TestCursorEncodeDecode:
    """Tests for cursor encoding and decoding."""

    def test_cursor_encode_decode_roundtrip(self):
        """Cursor should survive encode/decode."""
        data = {"v": "2025-01-01", "id": 123}
        encoded = encode_cursor(data)
        decoded = decode_cursor(encoded)
        assert decoded == data

    def test_cursor_encode_decode_with_numeric_value(self):
        """Cursor with numeric sort value should roundtrip."""
        data = {"v": 99.99, "id": 456}
        encoded = encode_cursor(data)
        decoded = decode_cursor(encoded)
        assert decoded == data

    def test_cursor_encode_decode_with_datetime(self):
        """Cursor with datetime value should serialize as ISO string."""
        dt = datetime(2025, 1, 15, 10, 30, 0)
        data = {"v": dt, "id": 789}
        encoded = encode_cursor(data)
        decoded = decode_cursor(encoded)
        # datetime gets serialized to string
        assert decoded["v"] == "2025-01-15T10:30:00"
        assert decoded["id"] == 789

    def test_cursor_encode_decode_with_date(self):
        """Cursor with date value should serialize as ISO string."""
        d = date(2025, 1, 15)
        data = {"v": d, "id": 101}
        encoded = encode_cursor(data)
        decoded = decode_cursor(encoded)
        # date gets serialized to string
        assert decoded["v"] == "2025-01-15"
        assert decoded["id"] == 101

    def test_cursor_encode_decode_with_decimal(self):
        """Cursor with Decimal value should serialize as string."""
        data = {"v": Decimal("123.45"), "id": 202}
        encoded = encode_cursor(data)
        decoded = decode_cursor(encoded)
        # Decimal gets serialized to string
        assert decoded["v"] == "123.45"
        assert decoded["id"] == 202

    def test_decode_invalid_cursor_returns_empty(self):
        """Invalid cursor should return empty dict."""
        assert decode_cursor("not-valid-base64!!!") == {}
        assert decode_cursor("") == {}
        assert decode_cursor("aW52YWxpZC1qc29u") == {}  # "invalid-json" in base64

    def test_cursor_is_url_safe(self):
        """Encoded cursor should be URL-safe."""
        data = {"v": "Test Card Name", "id": 12345}
        encoded = encode_cursor(data)
        # URL-safe base64 should not contain +, /, or =
        assert "+" not in encoded
        assert "/" not in encoded
        # Note: = padding is still possible in urlsafe_b64encode


class FakeItem:
    """Fake item for testing cursor response building."""

    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name


class TestBuildCursorResponse:
    """Tests for build_cursor_response function."""

    def test_build_cursor_response_with_more(self):
        """Should return cursor when more items exist."""
        items = [FakeItem(i, f"Item {i}") for i in range(11)]  # 11 items

        result_items, cursor, has_more = build_cursor_response(
            items, limit=10, order_attr="name"
        )

        assert len(result_items) == 10
        assert has_more is True
        assert cursor is not None

    def test_build_cursor_response_last_page(self):
        """Should not return cursor on last page."""
        items = [FakeItem(i, f"Item {i}") for i in range(5)]  # Only 5 items

        result_items, cursor, has_more = build_cursor_response(
            items, limit=10, order_attr="name"
        )

        assert len(result_items) == 5
        assert has_more is False
        assert cursor is None

    def test_build_cursor_response_exact_limit(self):
        """Exact limit count should indicate no more items."""
        items = [FakeItem(i, f"Item {i}") for i in range(10)]  # Exactly 10 items

        result_items, cursor, has_more = build_cursor_response(
            items, limit=10, order_attr="name"
        )

        assert len(result_items) == 10
        assert has_more is False
        assert cursor is None

    def test_build_cursor_response_empty_list(self):
        """Empty list should have no cursor and no more items."""
        result_items, cursor, has_more = build_cursor_response(
            [], limit=10, order_attr="name"
        )

        assert len(result_items) == 0
        assert has_more is False
        assert cursor is None

    def test_build_cursor_response_cursor_contains_last_item_values(self):
        """Cursor should contain values from last item."""
        items = [
            FakeItem(1, "Alpha"),
            FakeItem(2, "Beta"),
            FakeItem(3, "Gamma"),
        ]
        # Simulate having one extra item to indicate has_more
        items.append(FakeItem(4, "Delta"))

        result_items, cursor, has_more = build_cursor_response(
            items, limit=3, order_attr="name"
        )

        assert has_more is True
        # Decode and verify cursor points to last returned item
        cursor_data = decode_cursor(cursor)
        assert cursor_data["v"] == "Gamma"  # Last item in result
        assert cursor_data["id"] == 3

    def test_build_cursor_response_custom_id_attr(self):
        """Should use custom id attribute if specified."""

        class CustomItem:
            def __init__(self, card_id: int, title: str):
                self.card_id = card_id
                self.title = title

        items = [
            CustomItem(100, "First"),
            CustomItem(200, "Second"),
        ]
        items.append(CustomItem(300, "Third"))  # Extra item

        result_items, cursor, has_more = build_cursor_response(
            items, limit=2, order_attr="title", id_attr="card_id"
        )

        cursor_data = decode_cursor(cursor)
        assert cursor_data["v"] == "Second"
        assert cursor_data["id"] == 200


class TestBuildCursorFromItem:
    """Tests for build_cursor_from_item function."""

    def test_build_cursor_from_item(self):
        """Should create cursor from single item."""
        item = FakeItem(42, "Test Card")
        cursor = build_cursor_from_item(item, order_attr="name")

        cursor_data = decode_cursor(cursor)
        assert cursor_data["v"] == "Test Card"
        assert cursor_data["id"] == 42

    def test_build_cursor_from_item_custom_attrs(self):
        """Should use custom attributes."""

        class PriceItem:
            def __init__(self, price_id: int, price: float):
                self.price_id = price_id
                self.price = price

        item = PriceItem(999, 25.50)
        cursor = build_cursor_from_item(item, order_attr="price", id_attr="price_id")

        cursor_data = decode_cursor(cursor)
        assert cursor_data["v"] == 25.50
        assert cursor_data["id"] == 999
