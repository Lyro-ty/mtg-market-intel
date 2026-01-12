"""
Cursor-based pagination utilities.

Provides efficient pagination for large datasets using
encoded cursors instead of offset/limit.

Cursor-based pagination is O(1) because it uses an indexed WHERE clause,
while offset-based pagination is O(n) - OFFSET 100000 LIMIT 20 must scan
100,000 rows to skip them.
"""
import base64
import json
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel
from sqlalchemy import Select, and_, or_

T = TypeVar("T")


def _json_serialize(obj: Any) -> str:
    """Custom JSON serializer for cursor values."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    return str(obj)


def encode_cursor(data: dict) -> str:
    """Encode cursor data to URL-safe string."""
    json_str = json.dumps(data, sort_keys=True, default=_json_serialize)
    return base64.urlsafe_b64encode(json_str.encode()).decode()


def decode_cursor(cursor: str) -> dict:
    """Decode cursor string to data dict."""
    try:
        json_str = base64.urlsafe_b64decode(cursor.encode()).decode()
        return json.loads(json_str)
    except Exception:
        return {}


class CursorPage(BaseModel, Generic[T]):
    """Paginated response with cursor navigation."""
    items: list[T]
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None
    has_more: bool = False
    total_count: Optional[int] = None  # Only if explicitly requested


def apply_cursor_pagination(
    query: Select,
    cursor: Optional[str],
    limit: int,
    order_column,  # SQLAlchemy column
    id_column,     # For tiebreaker
    descending: bool = True,
) -> Select:
    """
    Apply cursor-based pagination to a SQLAlchemy query.

    Uses (order_column, id) for stable ordering with tiebreaker.

    The tiebreaker (id_column) is needed for stable ordering when
    sort values are equal. Without it, rows with the same sort value
    could appear in different orders on different pages.

    Args:
        query: The SQLAlchemy Select query to paginate
        cursor: Encoded cursor from previous page (None for first page)
        limit: Number of items per page
        order_column: SQLAlchemy column to sort by
        id_column: SQLAlchemy column for tiebreaker (usually primary key)
        descending: Sort direction (True for DESC, False for ASC)

    Returns:
        Modified query with cursor conditions and ordering applied
    """
    if cursor:
        cursor_data = decode_cursor(cursor)
        cursor_value = cursor_data.get("v")
        cursor_id = cursor_data.get("id")

        if cursor_value is not None and cursor_id is not None:
            if descending:
                # For DESC ordering: get rows where (value, id) < cursor
                query = query.where(
                    or_(
                        order_column < cursor_value,
                        and_(
                            order_column == cursor_value,
                            id_column < cursor_id,
                        ),
                    )
                )
            else:
                # For ASC ordering: get rows where (value, id) > cursor
                query = query.where(
                    or_(
                        order_column > cursor_value,
                        and_(
                            order_column == cursor_value,
                            id_column > cursor_id,
                        ),
                    )
                )

    # Apply ordering
    if descending:
        query = query.order_by(order_column.desc(), id_column.desc())
    else:
        query = query.order_by(order_column.asc(), id_column.asc())

    # Fetch one extra to determine has_more
    query = query.limit(limit + 1)

    return query


def build_cursor_response(
    items: list,
    limit: int,
    order_attr: str,
    id_attr: str = "id",
) -> tuple[list, Optional[str], bool]:
    """
    Build cursor response from query results.

    Args:
        items: List of result items (may include extra item for has_more detection)
        limit: Requested page size
        order_attr: Attribute name to use as cursor value
        id_attr: Attribute name for ID (tiebreaker)

    Returns:
        Tuple of (trimmed_items, next_cursor, has_more)
    """
    has_more = len(items) > limit
    items = items[:limit]  # Trim extra item

    next_cursor = None
    if has_more and items:
        last_item = items[-1]
        cursor_data = {
            "v": getattr(last_item, order_attr),
            "id": getattr(last_item, id_attr),
        }
        next_cursor = encode_cursor(cursor_data)

    return items, next_cursor, has_more


def build_cursor_from_item(item: Any, order_attr: str, id_attr: str = "id") -> str:
    """
    Build a cursor from a single item.

    Useful for creating prev_cursor from the first item of a page.

    Args:
        item: The item to build cursor from
        order_attr: Attribute name to use as cursor value
        id_attr: Attribute name for ID (tiebreaker)

    Returns:
        Encoded cursor string
    """
    cursor_data = {
        "v": getattr(item, order_attr),
        "id": getattr(item, id_attr),
    }
    return encode_cursor(cursor_data)
