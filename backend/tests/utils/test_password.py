"""Tests for password validation."""
import pytest
from app.utils.password import validate_password_strength, is_common_password


def test_valid_password():
    valid, msg = validate_password_strength("SecurePass123!")
    assert valid is True
    assert msg == ""


def test_password_too_short():
    valid, msg = validate_password_strength("Short1!")
    assert valid is False
    assert "12 characters" in msg


def test_password_no_uppercase():
    valid, msg = validate_password_strength("lowercase123!!")
    assert valid is False
    assert "uppercase" in msg


def test_password_no_lowercase():
    valid, msg = validate_password_strength("UPPERCASE123!!")
    assert valid is False
    assert "lowercase" in msg


def test_password_no_digit():
    valid, msg = validate_password_strength("NoDigitsHere!!")
    assert valid is False
    assert "digit" in msg


def test_password_no_special():
    valid, msg = validate_password_strength("NoSpecialChar1")
    assert valid is False
    assert "special" in msg


def test_common_password():
    assert is_common_password("password123456") is True
    assert is_common_password("SecurePass123!") is False
