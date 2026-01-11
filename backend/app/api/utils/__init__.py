"""
Shared utility functions for API routes.
"""
from app.api.utils.interpolation import interpolate_missing_points
from app.api.utils.error_handling import (
    handle_database_query,
    is_database_connection_error,
    get_empty_market_overview_response,
    get_empty_market_index_response,
    get_empty_top_movers_response,
    get_empty_volume_by_format_response,
)
from app.api.utils.validation import validate_id_list

__all__ = [
    "interpolate_missing_points",
    "handle_database_query",
    "is_database_connection_error",
    "get_empty_market_overview_response",
    "get_empty_market_index_response",
    "get_empty_top_movers_response",
    "get_empty_volume_by_format_response",
    "validate_id_list",
]
