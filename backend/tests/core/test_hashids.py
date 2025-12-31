"""Tests for hashids encoding utility."""
import pytest
from app.core.hashids import encode_id, decode_id, encode_card_id, decode_card_id


def test_encode_decode_roundtrip():
    """Encoding then decoding returns original ID."""
    original_id = 12345
    encoded = encode_id(original_id)
    decoded = decode_id(encoded)
    assert decoded == original_id


def test_encode_produces_string():
    """Encoded ID is a non-empty string."""
    encoded = encode_id(1)
    assert isinstance(encoded, str)
    assert len(encoded) >= 6  # Minimum length for obfuscation


def test_decode_invalid_returns_none():
    """Invalid hashid returns None, not error."""
    result = decode_id("invalid_hashid_xyz")
    assert result is None


def test_card_id_uses_different_salt():
    """Card IDs use different salt than user IDs."""
    card_encoded = encode_card_id(100)
    user_encoded = encode_id(100)
    assert card_encoded != user_encoded


def test_decode_wrong_type_returns_none():
    """Decoding card hash as user hash returns None."""
    card_hash = encode_card_id(100)
    result = decode_id(card_hash)  # Using user decoder
    assert result is None


def test_decode_empty_string_returns_none():
    """Decoding empty string returns None."""
    assert decode_id("") is None
    assert decode_card_id("") is None


def test_encode_large_id():
    """Large IDs encode and decode correctly."""
    large_id = 999999999
    encoded = encode_id(large_id)
    decoded = decode_id(encoded)
    assert decoded == large_id


def test_card_roundtrip():
    """Card ID encode/decode roundtrip works."""
    card_id = 42
    encoded = encode_card_id(card_id)
    decoded = decode_card_id(encoded)
    assert decoded == card_id
