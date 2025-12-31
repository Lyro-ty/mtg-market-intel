"""
Tests for profile API endpoints.
"""
import pytest


@pytest.mark.asyncio
async def test_get_my_profile(client, auth_headers, test_user):
    """Test getting own profile."""
    response = await client.get("/api/profile/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == test_user.id
    assert data["email"] == test_user.email
    assert data["username"] == test_user.username
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_my_profile_unauthenticated(client):
    """Test getting profile without auth fails."""
    response = await client.get("/api/profile/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_my_profile(client, auth_headers, test_user):
    """Test updating own profile."""
    update_data = {
        "display_name": "Test Display Name",
        "bio": "This is my bio",
        "location": "New York, NY",
    }

    response = await client.patch(
        "/api/profile/me",
        headers=auth_headers,
        json=update_data,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["display_name"] == "Test Display Name"
    assert data["bio"] == "This is my bio"
    assert data["location"] == "New York, NY"
    assert data["last_active_at"] is not None


@pytest.mark.asyncio
async def test_update_my_profile_partial(client, auth_headers, test_user):
    """Test partial profile update only changes specified fields."""
    # First set display_name
    await client.patch(
        "/api/profile/me",
        headers=auth_headers,
        json={"display_name": "Original Name"},
    )

    # Then update only bio - display_name should remain
    response = await client.patch(
        "/api/profile/me",
        headers=auth_headers,
        json={"bio": "New bio only"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["display_name"] == "Original Name"
    assert data["bio"] == "New bio only"


@pytest.mark.asyncio
async def test_get_public_profile(client, test_user, db_session):
    """Test getting a user's public profile by username."""
    # First set some profile data
    test_user.display_name = "Public Display"
    test_user.bio = "Public bio"
    await db_session.commit()
    await db_session.refresh(test_user)

    response = await client.get(f"/api/profile/{test_user.username}")

    assert response.status_code == 200
    data = response.json()

    assert data["username"] == test_user.username
    assert data["display_name"] == "Public Display"
    assert data["bio"] == "Public bio"
    # Public profile should NOT expose email or id
    assert "email" not in data
    assert "id" not in data


@pytest.mark.asyncio
async def test_get_public_profile_not_found(client):
    """Test getting non-existent user returns 404."""
    response = await client.get("/api/profile/nonexistentuser12345")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_public_profile_inactive_user(client, test_user, db_session):
    """Test inactive users are not visible in public profiles."""
    test_user.is_active = False
    await db_session.commit()

    response = await client.get(f"/api/profile/{test_user.username}")

    assert response.status_code == 404
