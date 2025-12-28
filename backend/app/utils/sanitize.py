"""Input sanitization utilities."""
import re
import html
from typing import Optional


def sanitize_string(value: Optional[str], max_length: int = 1000) -> Optional[str]:
    """
    Sanitize a string input.

    - Strip leading/trailing whitespace
    - HTML encode special characters
    - Truncate to max length (after escaping, respecting entity boundaries)
    """
    if value is None:
        return None

    # Strip whitespace
    value = value.strip()

    # HTML encode to prevent XSS
    value = html.escape(value)

    # Truncate (after escaping to get accurate length)
    if len(value) > max_length:
        value = value[:max_length]
        # Avoid breaking HTML entities (they start with & and end with ;)
        # If we might have cut mid-entity, back up to before the &
        if '&' in value[-6:]:
            last_amp = value.rfind('&')
            # Check if this looks like a truncated entity
            if ';' not in value[last_amp:]:
                value = value[:last_amp]

    return value


def sanitize_email(email: Optional[str]) -> str:
    """Sanitize and validate email format."""
    if email is None:
        raise ValueError("Email cannot be None")

    email = email.strip().lower()

    if not email:
        raise ValueError("Email cannot be empty")

    # Basic email validation
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        raise ValueError("Invalid email format")

    return email


def sanitize_username(username: Optional[str]) -> str:
    """Sanitize username - alphanumeric and underscores only."""
    if username is None:
        raise ValueError("Username cannot be None")

    username = username.strip()

    if not username:
        raise ValueError("Username cannot be empty")

    # Only allow alphanumeric and underscores
    if not re.match(r"^[a-zA-Z0-9_]{3,50}$", username):
        raise ValueError("Username must be 3-50 characters, alphanumeric and underscores only")

    return username
