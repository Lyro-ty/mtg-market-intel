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


# Social trading field tests

@pytest.mark.asyncio
async def test_get_my_profile_with_social_fields(client, auth_headers, test_user, db_session):
    """Test getting own profile includes social trading fields."""
    # Set social trading fields
    test_user.tagline = "MTG Collector"
    test_user.card_type = "collector"
    test_user.city = "Seattle"
    test_user.country = "USA"
    test_user.shipping_preference = "domestic"
    await db_session.commit()
    await db_session.refresh(test_user)

    response = await client.get("/api/profile/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert data["tagline"] == "MTG Collector"
    assert data["card_type"] == "collector"
    assert data["city"] == "Seattle"
    assert data["country"] == "USA"
    assert data["shipping_preference"] == "domestic"
    assert data["active_frame_tier"] == "bronze"
    assert data["discovery_score"] == 100
    assert data["show_in_directory"] is True
    assert data["show_in_search"] is True
    assert data["show_online_status"] is True
    assert data["show_portfolio_tier"] is True


@pytest.mark.asyncio
async def test_update_social_trading_fields(client, auth_headers, test_user):
    """Test updating social trading fields."""
    update_data = {
        "tagline": "Vintage Trader",
        "card_type": "trader",
        "city": "Boston",
        "country": "USA",
        "shipping_preference": "international",
    }

    response = await client.patch(
        "/api/profile/me",
        headers=auth_headers,
        json=update_data,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["tagline"] == "Vintage Trader"
    assert data["card_type"] == "trader"
    assert data["city"] == "Boston"
    assert data["country"] == "USA"
    assert data["shipping_preference"] == "international"


@pytest.mark.asyncio
async def test_update_privacy_settings(client, auth_headers, test_user):
    """Test updating privacy settings."""
    update_data = {
        "show_in_directory": False,
        "show_in_search": False,
        "show_online_status": False,
        "show_portfolio_tier": False,
    }

    response = await client.patch(
        "/api/profile/me",
        headers=auth_headers,
        json=update_data,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["show_in_directory"] is False
    assert data["show_in_search"] is False
    assert data["show_online_status"] is False
    assert data["show_portfolio_tier"] is False


@pytest.mark.asyncio
async def test_public_profile_respects_privacy_settings(client, test_user, db_session):
    """Test public profile respects show_in_directory privacy setting."""
    # Set location data and privacy
    test_user.city = "Private City"
    test_user.country = "Private Country"
    test_user.show_in_directory = False
    await db_session.commit()
    await db_session.refresh(test_user)

    response = await client.get(f"/api/profile/{test_user.username}")

    assert response.status_code == 200
    data = response.json()

    # City and country should be hidden when show_in_directory is False
    assert data["city"] is None
    assert data["country"] is None


@pytest.mark.asyncio
async def test_public_profile_shows_location_when_allowed(client, test_user, db_session):
    """Test public profile shows location when show_in_directory is True."""
    # Set location data with privacy enabled
    test_user.city = "Public City"
    test_user.country = "Public Country"
    test_user.show_in_directory = True
    await db_session.commit()
    await db_session.refresh(test_user)

    response = await client.get(f"/api/profile/{test_user.username}")

    assert response.status_code == 200
    data = response.json()

    assert data["city"] == "Public City"
    assert data["country"] == "Public Country"


@pytest.mark.asyncio
async def test_public_profile_includes_social_trading_fields(client, test_user, db_session):
    """Test public profile includes public social trading fields."""
    test_user.tagline = "Commander Enthusiast"
    test_user.card_type = "brewer"
    test_user.shipping_preference = "local"
    test_user.active_frame_tier = "silver"
    await db_session.commit()
    await db_session.refresh(test_user)

    response = await client.get(f"/api/profile/{test_user.username}")

    assert response.status_code == 200
    data = response.json()

    assert data["tagline"] == "Commander Enthusiast"
    assert data["card_type"] == "brewer"
    assert data["shipping_preference"] == "local"
    assert data["active_frame_tier"] == "silver"
    # Discovery score should NOT be in public profile
    assert "discovery_score" not in data


@pytest.mark.asyncio
async def test_card_type_validation(client, auth_headers, test_user):
    """Test card_type only accepts valid values."""
    update_data = {
        "card_type": "invalid_type",
    }

    response = await client.patch(
        "/api/profile/me",
        headers=auth_headers,
        json=update_data,
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_shipping_preference_validation(client, auth_headers, test_user):
    """Test shipping_preference only accepts valid values."""
    update_data = {
        "shipping_preference": "invalid_preference",
    }

    response = await client.patch(
        "/api/profile/me",
        headers=auth_headers,
        json=update_data,
    )

    assert response.status_code == 422  # Validation error
