"""Input sanitization utilities."""
import re
import html
from typing import Optional


def sanitize_string(value: Optional[str], max_length: int = 1000) -> Optional[str]:
    """
    Sanitize a string input.

    - HTML encode special characters
    - Truncate to max length
    - Strip leading/trailing whitespace
    """
    if value is None:
        return None

    # Strip whitespace
    value = value.strip()

    # Truncate
    if len(value) > max_length:
        value = value[:max_length]

    # HTML encode to prevent XSS
    value = html.escape(value)

    return value


def sanitize_email(email: str) -> str:
    """Sanitize and validate email format."""
    email = email.strip().lower()

    # Basic email validation
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        raise ValueError("Invalid email format")

    return email


def sanitize_username(username: str) -> str:
    """Sanitize username - alphanumeric and underscores only."""
    username = username.strip()

    # Only allow alphanumeric and underscores
    if not re.match(r"^[a-zA-Z0-9_]{3,50}$", username):
        raise ValueError("Username must be 3-50 characters, alphanumeric and underscores only")

    return username
