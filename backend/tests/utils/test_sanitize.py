"""Tests for input sanitization."""
import pytest
from app.utils.sanitize import sanitize_string, sanitize_email, sanitize_username


def test_sanitize_string_escapes_html():
    result = sanitize_string("<script>alert('xss')</script>")
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_sanitize_string_truncates():
    long_string = "a" * 2000
    result = sanitize_string(long_string, max_length=100)
    assert len(result) == 100


def test_sanitize_string_strips_whitespace():
    result = sanitize_string("  hello  ")
    assert result == "hello"


def test_sanitize_string_handles_none():
    result = sanitize_string(None)
    assert result is None


def test_sanitize_email_valid():
    result = sanitize_email("Test@Example.COM")
    assert result == "test@example.com"


def test_sanitize_email_invalid():
    with pytest.raises(ValueError):
        sanitize_email("not-an-email")


def test_sanitize_username_valid():
    result = sanitize_username("valid_user123")
    assert result == "valid_user123"


def test_sanitize_username_invalid():
    with pytest.raises(ValueError):
        sanitize_username("user with spaces")


def test_sanitize_username_too_short():
    with pytest.raises(ValueError):
        sanitize_username("ab")


def test_sanitize_username_too_long():
    with pytest.raises(ValueError):
        sanitize_username("a" * 51)


def test_sanitize_email_none():
    with pytest.raises(ValueError, match="cannot be None"):
        sanitize_email(None)


def test_sanitize_email_empty():
    with pytest.raises(ValueError, match="cannot be empty"):
        sanitize_email("")


def test_sanitize_username_none():
    with pytest.raises(ValueError, match="cannot be None"):
        sanitize_username(None)


def test_sanitize_username_empty():
    with pytest.raises(ValueError, match="cannot be empty"):
        sanitize_username("")
