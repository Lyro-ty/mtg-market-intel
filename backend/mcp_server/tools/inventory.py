"""
Inventory tools for MCP server.

Provides tools to query and manage user inventory.
Write operations are restricted to dev mode + test user only.
"""
from typing import Any

from mcp_server.utils import execute_query, api_client, log_write_operation, require_dev_mode, require_test_user
from mcp_server.config import config


async def list_inventory(
    user_id: int,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """
    List inventory items for a user.

    Args:
        user_id: User ID to list inventory for
        limit: Maximum items to return
        offset: Pagination offset

    Returns:
        Paginated inventory list
    """
    query = """
        SELECT
            i.id,
            i.card_id,
            c.name as card_name,
            c.set_code,
            i.quantity,
            i.condition,
            i.is_foil,
            i.acquisition_price,
            i.acquisition_date,
            i.current_value
        FROM inventory_items i
        JOIN cards c ON i.card_id = c.id
        WHERE i.user_id = :user_id
        ORDER BY c.name
        LIMIT :limit OFFSET :offset
    """

    rows = await execute_query(query, {"user_id": user_id, "limit": limit, "offset": offset})

    # Get total count
    count_query = "SELECT COUNT(*) as count FROM inventory_items WHERE user_id = :user_id"
    count_result = await execute_query(count_query, {"user_id": user_id})
    total = count_result[0]["count"] if count_result else 0

    return {
        "user_id": user_id,
        "items": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def get_inventory_item(item_id: int) -> dict[str, Any]:
    """
    Get a specific inventory item.

    Args:
        item_id: Inventory item ID

    Returns:
        Item details with current value
    """
    query = """
        SELECT
            i.*,
            c.name as card_name,
            c.set_code,
            c.set_name,
            c.rarity,
            c.image_url_small
        FROM inventory_items i
        JOIN cards c ON i.card_id = c.id
        WHERE i.id = :item_id
    """

    rows = await execute_query(query, {"item_id": item_id})
    if not rows:
        return {"error": f"Inventory item {item_id} not found"}

    item = rows[0]

    # Calculate profit/loss using stored current_value
    current_value = float(item.get("current_value") or 0)
    quantity = item.get("quantity", 1)
    acquisition_price = float(item.get("acquisition_price") or 0)

    item["total_cost"] = acquisition_price * quantity
    item["total_value"] = current_value * quantity
    item["profit_loss"] = item["total_value"] - item["total_cost"]

    return item


async def get_portfolio_value(user_id: int) -> dict[str, Any]:
    """
    Get total portfolio value and performance for a user.

    Args:
        user_id: User ID

    Returns:
        Portfolio value, cost, and profit/loss
    """
    query = """
        SELECT
            COUNT(*) as total_items,
            SUM(i.quantity) as total_cards,
            SUM(i.quantity * COALESCE(i.current_value, 0)) as current_value,
            SUM(i.quantity * COALESCE(i.acquisition_price, 0)) as total_cost
        FROM inventory_items i
        WHERE i.user_id = :user_id
    """

    rows = await execute_query(query, {"user_id": user_id})
    if not rows or rows[0]["total_items"] == 0:
        return {
            "user_id": user_id,
            "total_items": 0,
            "total_cards": 0,
            "current_value": 0,
            "total_cost": 0,
            "profit_loss": 0,
            "profit_loss_pct": 0,
        }

    result = rows[0]
    current_value = float(result["current_value"] or 0)
    total_cost = float(result["total_cost"] or 0)
    profit_loss = current_value - total_cost
    profit_loss_pct = (profit_loss / total_cost * 100) if total_cost > 0 else 0

    return {
        "user_id": user_id,
        "total_items": result["total_items"],
        "total_cards": result["total_cards"],
        "current_value": round(current_value, 2),
        "total_cost": round(total_cost, 2),
        "profit_loss": round(profit_loss, 2),
        "profit_loss_pct": round(profit_loss_pct, 2),
    }


async def write_add_inventory_item(
    user_id: int,
    card_id: int,
    quantity: int = 1,
    condition: str = "NEAR_MINT",
    is_foil: bool = False,
    acquisition_price: float | None = None,
) -> dict[str, Any]:
    """
    Add a card to user's inventory.

    RESTRICTED: Only works in dev mode for test user.

    Args:
        user_id: User ID (must match test user)
        card_id: Card to add
        quantity: Number of copies
        condition: Card condition
        is_foil: Whether card is foil
        acquisition_price: Price paid per copy

    Returns:
        Created inventory item
    """
    require_dev_mode("write_add_inventory_item")
    require_test_user("write_add_inventory_item", user_id)

    log_write_operation("write_add_inventory_item", {
        "user_id": user_id,
        "card_id": card_id,
        "quantity": quantity,
        "condition": condition,
        "is_foil": is_foil,
    })

    # Use API to add item
    try:
        result = await api_client.post("/inventory", json={
            "card_id": card_id,
            "quantity": quantity,
            "condition": condition,
            "is_foil": is_foil,
            "acquisition_price": acquisition_price,
        })
        return result
    except Exception as e:
        return {"error": str(e)}


async def write_remove_inventory_item(user_id: int, item_id: int) -> dict[str, Any]:
    """
    Remove an item from user's inventory.

    RESTRICTED: Only works in dev mode for test user.

    Args:
        user_id: User ID (must match test user)
        item_id: Inventory item ID to remove

    Returns:
        Deletion result
    """
    require_dev_mode("write_remove_inventory_item")
    require_test_user("write_remove_inventory_item", user_id)

    log_write_operation("write_remove_inventory_item", {
        "user_id": user_id,
        "item_id": item_id,
    })

    # Verify item belongs to user first
    item = await get_inventory_item(item_id)
    if "error" in item:
        return item
    if item.get("user_id") != user_id:
        return {"error": "Item does not belong to specified user"}

    # This would need a DELETE endpoint - for now return info
    return {
        "note": "DELETE endpoint needed for removal",
        "item_id": item_id,
        "would_delete": item,
    }


async def write_update_inventory_item(
    user_id: int,
    item_id: int,
    quantity: int | None = None,
    condition: str | None = None,
) -> dict[str, Any]:
    """
    Update an inventory item.

    RESTRICTED: Only works in dev mode for test user.

    Args:
        user_id: User ID (must match test user)
        item_id: Inventory item ID
        quantity: New quantity (optional)
        condition: New condition (optional)

    Returns:
        Updated item
    """
    require_dev_mode("write_update_inventory_item")
    require_test_user("write_update_inventory_item", user_id)

    log_write_operation("write_update_inventory_item", {
        "user_id": user_id,
        "item_id": item_id,
        "quantity": quantity,
        "condition": condition,
    })

    # This would need a PATCH endpoint
    return {
        "note": "PATCH endpoint needed for updates",
        "item_id": item_id,
        "updates": {"quantity": quantity, "condition": condition},
    }
