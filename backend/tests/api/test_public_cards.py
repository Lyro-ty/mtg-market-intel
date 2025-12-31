"""Tests for public card endpoints."""
import pytest
from httpx import AsyncClient

from app.core.hashids import encode_card_id


@pytest.mark.asyncio
async def test_get_card_by_hashid(client: AsyncClient, test_card):
    """Public endpoint returns card by hashid without auth."""
    hashid = encode_card_id(test_card.id)
    response = await client.get(f"/api/cards/public/{hashid}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == test_card.name
    assert data["hashid"] == hashid
    assert "id" not in data  # Don't expose internal ID


@pytest.mark.asyncio
async def test_get_card_invalid_hashid(client: AsyncClient):
    """Invalid hashid returns 404."""
    response = await client.get("/api/cards/public/invalid_hash_xyz")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_card_empty_hashid(client: AsyncClient):
    """Empty hashid returns 404 or redirect."""
    response = await client.get("/api/cards/public/")
    # FastAPI may redirect (307) or return 404/405 for empty path segment
    assert response.status_code in (307, 404, 405)


@pytest.mark.asyncio
async def test_get_card_prices_public(client: AsyncClient, test_card):
    """Price history accessible without auth."""
    hashid = encode_card_id(test_card.id)
    response = await client.get(f"/api/cards/public/{hashid}/prices")
    assert response.status_code == 200
    data = response.json()
    assert "prices" in data
    assert isinstance(data["prices"], list)


@pytest.mark.asyncio
async def test_public_card_contains_expected_fields(client: AsyncClient, test_card):
    """Public card response contains all expected fields."""
    hashid = encode_card_id(test_card.id)
    response = await client.get(f"/api/cards/public/{hashid}")
    assert response.status_code == 200
    data = response.json()

    # Required fields
    assert "hashid" in data
    assert "name" in data
    assert "set_code" in data

    # Optional fields should be present (even if None)
    assert "set_name" in data
    assert "rarity" in data
    assert "mana_cost" in data
    assert "type_line" in data
    assert "oracle_text" in data
    assert "image_url" in data
