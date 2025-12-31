"""
Hashids encoding for public-facing URLs.

Uses different salts for different entity types to prevent
cross-type decoding attacks.
"""
from hashids import Hashids
from app.core.config import settings

# Minimum length for obfuscation
MIN_LENGTH = 8

# Different hashids instances for different entity types
# Use distinctly different salts to ensure different encoding for each type
_user_hasher = Hashids(salt=f"user_id_{settings.secret_key}", min_length=MIN_LENGTH)
_card_hasher = Hashids(salt=f"card_id_{settings.secret_key}", min_length=MIN_LENGTH)


def encode_id(id: int) -> str:
    """Encode a generic ID (users, etc.)."""
    return _user_hasher.encode(id)


def decode_id(hashid: str) -> int | None:
    """Decode a generic hashid. Returns None if invalid."""
    if not hashid:
        return None
    try:
        result = _user_hasher.decode(hashid)
        return result[0] if result else None
    except Exception:
        return None


def encode_card_id(id: int) -> str:
    """Encode a card ID."""
    return _card_hasher.encode(id)


def decode_card_id(hashid: str) -> int | None:
    """Decode a card hashid. Returns None if invalid."""
    if not hashid:
        return None
    try:
        result = _card_hasher.decode(hashid)
        return result[0] if result else None
    except Exception:
        return None
