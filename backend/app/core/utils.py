"""
Shared utility functions for the application.
"""
import json
from typing import Any


def parse_setting_value(value: str, value_type: str) -> Any:
    """
    Parse a setting value based on its type.

    Args:
        value: The string value to parse
        value_type: One of "json", "float", "integer", "boolean", or "string"

    Returns:
        The parsed value in the appropriate type
    """
    if value_type == "json":
        return json.loads(value)
    elif value_type == "float":
        return float(value)
    elif value_type == "integer":
        return int(value)
    elif value_type == "boolean":
        return value.lower() == "true"
    return value
