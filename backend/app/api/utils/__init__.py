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
from app.api.utils.ownership import (
    verify_ownership,
    verify_ownership_optional,
    check_ownership,
    require_ownership,
)
from app.api.utils.file_validation import (
    detect_dangerous_content,
    validate_csv_structure,
    validate_import_file,
)
from app.api.utils.pagination import (
    encode_cursor,
    decode_cursor,
    CursorPage,
    apply_cursor_pagination,
    build_cursor_response,
    build_cursor_from_item,
)

__all__ = [
    "interpolate_missing_points",
    "handle_database_query",
    "is_database_connection_error",
    "get_empty_market_overview_response",
    "get_empty_market_index_response",
    "get_empty_top_movers_response",
    "get_empty_volume_by_format_response",
    "validate_id_list",
    "verify_ownership",
    "verify_ownership_optional",
    "check_ownership",
    "require_ownership",
    "detect_dangerous_content",
    "validate_csv_structure",
    "validate_import_file",
    # Cursor pagination
    "encode_cursor",
    "decode_cursor",
    "CursorPage",
    "apply_cursor_pagination",
    "build_cursor_response",
    "build_cursor_from_item",
]
