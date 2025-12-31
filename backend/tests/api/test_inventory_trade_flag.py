"""
Tests for available_for_trade flag on inventory items.
"""
import pytest


@pytest.mark.asyncio
async def test_create_inventory_item_default_not_for_trade(
    client, auth_headers, test_card
):
    """New inventory items default to not available for trade."""
    response = await client.post(
        "/api/inventory",
        headers=auth_headers,
        json={
            "card_id": test_card.id,
            "quantity": 1,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["available_for_trade"] is False


@pytest.mark.asyncio
async def test_create_inventory_item_available_for_trade(
    client, auth_headers, test_card
):
    """Can create inventory item with available_for_trade=True."""
    response = await client.post(
        "/api/inventory",
        headers=auth_headers,
        json={
            "card_id": test_card.id,
            "quantity": 1,
            "available_for_trade": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["available_for_trade"] is True


@pytest.mark.asyncio
async def test_update_inventory_item_trade_flag(
    client, auth_headers, test_inventory_item
):
    """Can update available_for_trade flag."""
    item_id = test_inventory_item["id"]

    # Update to available for trade
    response = await client.patch(
        f"/api/inventory/{item_id}",
        headers=auth_headers,
        json={"available_for_trade": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["available_for_trade"] is True

    # Update back to not available
    response = await client.patch(
        f"/api/inventory/{item_id}",
        headers=auth_headers,
        json={"available_for_trade": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["available_for_trade"] is False


@pytest.mark.asyncio
async def test_filter_inventory_by_trade_flag(
    client, auth_headers, db_session, test_user, test_card, test_card_2
):
    """Can filter inventory by available_for_trade."""
    from app.models import InventoryItem

    # Create one item for trade, one not
    item_for_trade = InventoryItem(
        user_id=test_user.id,
        card_id=test_card.id,
        quantity=1,
        condition="NEAR_MINT",
        available_for_trade=True,
    )
    item_not_for_trade = InventoryItem(
        user_id=test_user.id,
        card_id=test_card_2.id,
        quantity=1,
        condition="NEAR_MINT",
        available_for_trade=False,
    )
    db_session.add(item_for_trade)
    db_session.add(item_not_for_trade)
    await db_session.commit()

    # Filter for trade items only
    response = await client.get(
        "/api/inventory",
        headers=auth_headers,
        params={"available_for_trade": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["available_for_trade"] is True

    # Filter for non-trade items only
    response = await client.get(
        "/api/inventory",
        headers=auth_headers,
        params={"available_for_trade": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["available_for_trade"] is False
