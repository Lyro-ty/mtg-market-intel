# backend/tests/test_token_blacklist.py
"""Tests for token blacklist fail-secure behavior."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from app.core.token_blacklist import TokenBlacklist


class TestTokenBlacklistFailSecure:
    """Test that token blacklist fails secure when Redis unavailable."""

    def test_add_returns_false_when_redis_unavailable(self):
        """add() should return False when Redis unavailable."""
        blacklist = TokenBlacklist()

        with patch.object(blacklist, '_get_redis', return_value=None):
            jti = "test-token-123"
            expires = datetime.now(timezone.utc) + timedelta(hours=1)

            result = blacklist.add(jti, expires)
            assert result is False

    def test_is_blacklisted_returns_true_when_redis_unavailable(self):
        """is_blacklisted() should return True (fail secure) when Redis unavailable."""
        blacklist = TokenBlacklist()

        with patch.object(blacklist, '_get_redis', return_value=None):
            result = blacklist.is_blacklisted("any-token")
            # SECURITY: Should return True (assume blacklisted) when can't verify
            assert result is True

    def test_is_blacklisted_returns_true_on_redis_error(self):
        """is_blacklisted() should return True on Redis errors."""
        blacklist = TokenBlacklist()
        mock_redis = MagicMock()
        mock_redis.exists.side_effect = Exception("Connection lost")

        with patch.object(blacklist, '_get_redis', return_value=mock_redis):
            result = blacklist.is_blacklisted("any-token")
            assert result is True

    def test_add_returns_true_for_expired_token(self):
        """add() should return True for already-expired tokens (no action needed)."""
        blacklist = TokenBlacklist()

        # Token expired 1 hour ago
        jti = "expired-token"
        expires = datetime.now(timezone.utc) - timedelta(hours=1)

        result = blacklist.add(jti, expires)
        assert result is True

    def test_add_returns_false_on_redis_error(self):
        """add() should return False when Redis throws an error."""
        blacklist = TokenBlacklist()
        mock_redis = MagicMock()
        mock_redis.setex.side_effect = Exception("Connection lost")

        with patch.object(blacklist, '_get_redis', return_value=mock_redis):
            jti = "test-token"
            expires = datetime.now(timezone.utc) + timedelta(hours=1)

            result = blacklist.add(jti, expires)
            assert result is False


class TestTokenBlacklistNormalOperation:
    """Test normal operation with Redis available."""

    def test_add_and_check_blacklist_with_redis(self):
        """Token should be blacklisted and found when Redis works."""
        blacklist = TokenBlacklist()
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 1  # Token exists in blacklist

        with patch.object(blacklist, '_get_redis', return_value=mock_redis):
            # Add token
            jti = "test-token"
            expires = datetime.now(timezone.utc) + timedelta(hours=1)
            result = blacklist.add(jti, expires)
            assert result is True
            mock_redis.setex.assert_called_once()

            # Check if blacklisted
            result = blacklist.is_blacklisted(jti)
            assert result is True

    def test_is_blacklisted_returns_false_for_non_blacklisted_token(self):
        """is_blacklisted() should return False for tokens not in blacklist."""
        blacklist = TokenBlacklist()
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 0  # Token does not exist

        with patch.object(blacklist, '_get_redis', return_value=mock_redis):
            result = blacklist.is_blacklisted("non-existent-token")
            assert result is False


class TestNoInMemoryFallback:
    """Test that in-memory fallback has been removed."""

    def test_no_local_cache_attribute(self):
        """TokenBlacklist should not have _local_cache attribute."""
        blacklist = TokenBlacklist()
        assert not hasattr(blacklist, '_local_cache'), \
            "SECURITY: _local_cache should be removed - in-memory fallback is a vulnerability"

    def test_no_cleanup_local_cache_method(self):
        """TokenBlacklist should not have _cleanup_local_cache method."""
        blacklist = TokenBlacklist()
        assert not hasattr(blacklist, '_cleanup_local_cache'), \
            "SECURITY: _cleanup_local_cache should be removed with in-memory fallback"
