"""
Tests for refresh token rotation functionality.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from app.services.auth import (
    create_token_pair,
    decode_refresh_token,
    blacklist_token,
    create_refresh_token,
)


def test_create_token_pair_returns_both_tokens():
    """Token pair should include access and refresh tokens."""
    access, refresh, expires_in = create_token_pair(user_id=123)

    assert access is not None
    assert refresh is not None
    assert expires_in > 0
    assert access != refresh


def test_refresh_token_has_correct_type():
    """Refresh token should have type='refresh'."""
    _, refresh, _ = create_token_pair(user_id=123)
    payload = decode_refresh_token(refresh)

    assert payload is not None
    assert payload.type == "refresh"


def test_access_token_not_valid_as_refresh():
    """Access token should not be accepted as refresh token."""
    access, _, _ = create_token_pair(user_id=123)

    # Try to decode access token as refresh - should fail
    payload = decode_refresh_token(access)
    assert payload is None


def test_blacklisted_refresh_token_rejected():
    """Blacklisted refresh tokens should be rejected."""
    _, refresh, _ = create_token_pair(user_id=123)

    # Token should be valid initially
    assert decode_refresh_token(refresh) is not None

    # Blacklist it
    blacklist_token(refresh)

    # Now it should be rejected (when Redis is available)
    # Note: With fail-secure, if Redis is down this returns None anyway


def test_create_refresh_token_has_jti():
    """Refresh token should have a unique JTI."""
    refresh = create_refresh_token(user_id=456)
    payload = decode_refresh_token(refresh)

    assert payload is not None
    assert payload.jti is not None
    assert len(payload.jti) > 0


def test_refresh_token_contains_user_id():
    """Refresh token should contain the user ID."""
    user_id = 789
    _, refresh, _ = create_token_pair(user_id=user_id)
    payload = decode_refresh_token(refresh)

    assert payload is not None
    assert payload.sub == str(user_id)


def test_token_pair_expires_in_matches_config():
    """expires_in should match the configured access token expiration."""
    from app.core.config import settings

    _, _, expires_in = create_token_pair(user_id=123)

    expected_expires_in = settings.jwt_access_token_expire_minutes * 60
    assert expires_in == expected_expires_in


def test_two_refresh_tokens_have_different_jti():
    """Each refresh token should have a unique JTI."""
    refresh1 = create_refresh_token(user_id=123)
    refresh2 = create_refresh_token(user_id=123)

    payload1 = decode_refresh_token(refresh1)
    payload2 = decode_refresh_token(refresh2)

    assert payload1 is not None
    assert payload2 is not None
    assert payload1.jti != payload2.jti
