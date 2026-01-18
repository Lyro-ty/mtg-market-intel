"""
Tests for the achievements API.

Tests:
- GET /achievements - requires auth, returns achievements list
- GET /achievements/users/{user_id} - public endpoint, returns unlocked achievements
- GET /achievements/frames - requires auth, returns frame tiers
- POST /achievements/frames/active - requires auth, sets active frame
"""
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient

from app.models.achievement import AchievementDefinition, UserAchievement, UserFrame


@pytest.mark.asyncio
async def test_get_achievements_unauthorized(client: AsyncClient):
    """Test that unauthenticated users can't access achievements."""
    response = await client.get("/api/achievements")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_achievements_authenticated(client: AsyncClient, auth_headers: dict):
    """Test that authenticated users can get achievements list."""
    response = await client.get("/api/achievements", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "achievements" in data
    assert "total_unlocked" in data
    assert "total_discovery_points" in data


@pytest.mark.asyncio
async def test_get_achievements_with_data(
    client: AsyncClient,
    auth_headers: dict,
    db_session,
    test_user,
):
    """Test achievements list with actual achievement definitions."""
    # Create an achievement definition
    definition = AchievementDefinition(
        key="first_trade",
        name="First Trade",
        description="Complete your first trade",
        category="trade",
        discovery_points=10,
        is_hidden=False,
    )
    db_session.add(definition)
    await db_session.commit()
    await db_session.refresh(definition)

    response = await client.get("/api/achievements", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert len(data["achievements"]) >= 1
    achievement = next(
        (a for a in data["achievements"] if a["achievement"]["key"] == "first_trade"),
        None,
    )
    assert achievement is not None
    assert achievement["achievement"]["name"] == "First Trade"
    assert achievement["unlocked"] is False


@pytest.mark.asyncio
async def test_get_achievements_shows_unlocked(
    client: AsyncClient,
    auth_headers: dict,
    db_session,
    test_user,
):
    """Test that unlocked achievements are shown with progress."""
    # Create an achievement definition
    definition = AchievementDefinition(
        key="veteran_trader",
        name="Veteran Trader",
        description="Complete 100 trades",
        category="trade",
        discovery_points=50,
        is_hidden=False,
    )
    db_session.add(definition)
    await db_session.commit()
    await db_session.refresh(definition)

    # Mark it as unlocked for the user
    user_achievement = UserAchievement(
        user_id=test_user.id,
        achievement_id=definition.id,
        unlocked_at=datetime.now(timezone.utc),
        progress={"current": 100, "target": 100},
    )
    db_session.add(user_achievement)
    await db_session.commit()

    response = await client.get("/api/achievements", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    achievement = next(
        (a for a in data["achievements"] if a["achievement"]["key"] == "veteran_trader"),
        None,
    )
    assert achievement is not None
    assert achievement["unlocked"] is True
    assert achievement["unlocked_at"] is not None
    assert achievement["progress"]["current"] == 100

    # Verify totals include this achievement
    assert data["total_unlocked"] >= 1
    assert data["total_discovery_points"] >= 50


@pytest.mark.asyncio
async def test_get_achievements_hides_hidden_unearned(
    client: AsyncClient,
    auth_headers: dict,
    db_session,
    test_user,
):
    """Test that hidden achievements are not shown until unlocked."""
    # Create a hidden achievement
    hidden_def = AchievementDefinition(
        key="secret_achievement",
        name="Secret Achievement",
        description="???",
        category="special",
        discovery_points=100,
        is_hidden=True,
    )
    db_session.add(hidden_def)
    await db_session.commit()

    response = await client.get("/api/achievements", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    # Hidden achievement should not appear
    achievement = next(
        (a for a in data["achievements"] if a["achievement"]["key"] == "secret_achievement"),
        None,
    )
    assert achievement is None


@pytest.mark.asyncio
async def test_get_user_achievements(
    client: AsyncClient,
    db_session,
    test_user,
):
    """Test getting achievements for a specific user (public endpoint)."""
    # Create and unlock an achievement
    definition = AchievementDefinition(
        key="collector",
        name="Collector",
        description="Add 50 cards to your collection",
        category="portfolio",
        discovery_points=25,
        is_hidden=False,
    )
    db_session.add(definition)
    await db_session.commit()
    await db_session.refresh(definition)

    user_achievement = UserAchievement(
        user_id=test_user.id,
        achievement_id=definition.id,
        unlocked_at=datetime.now(timezone.utc),
    )
    db_session.add(user_achievement)
    await db_session.commit()

    # Request without auth (public endpoint)
    response = await client.get(f"/api/achievements/users/{test_user.id}")
    assert response.status_code == 200
    data = response.json()

    assert len(data["achievements"]) >= 1
    assert data["total_unlocked"] >= 1


@pytest.mark.asyncio
async def test_get_user_achievements_not_found(client: AsyncClient):
    """Test that requesting achievements for non-existent user returns 404."""
    response = await client.get("/api/achievements/users/999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_frames_unauthorized(client: AsyncClient):
    """Test that unauthenticated users can't access frames."""
    response = await client.get("/api/achievements/frames")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_frames_authenticated(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test that authenticated users can get their frames."""
    response = await client.get("/api/achievements/frames", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert "frames" in data
    assert "active_frame" in data
    assert len(data["frames"]) == 5  # bronze, silver, gold, platinum, legendary


@pytest.mark.asyncio
async def test_get_frames_shows_unlocked(
    client: AsyncClient,
    auth_headers: dict,
    db_session,
    test_user,
):
    """Test that unlocked frames are marked correctly."""
    # Create an unlocked frame for the user
    user_frame = UserFrame(
        user_id=test_user.id,
        frame_tier="silver",
        is_active=False,
    )
    db_session.add(user_frame)
    await db_session.commit()

    response = await client.get("/api/achievements/frames", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    silver_frame = next(
        (f for f in data["frames"] if f["tier"] == "silver"),
        None,
    )
    assert silver_frame is not None
    assert silver_frame["unlocked"] is True
    assert silver_frame["unlocked_at"] is not None


@pytest.mark.asyncio
async def test_set_active_frame_unauthorized(client: AsyncClient):
    """Test that unauthenticated users can't set active frame."""
    response = await client.post(
        "/api/achievements/frames/active",
        json={"frame_tier": "gold"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_set_active_frame_not_unlocked(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test that setting a frame that's not unlocked fails."""
    response = await client.post(
        "/api/achievements/frames/active",
        json={"frame_tier": "legendary"},
        headers=auth_headers,
    )
    assert response.status_code == 403
    assert "not been unlocked" in response.json()["detail"]


@pytest.mark.asyncio
async def test_set_active_frame_invalid_tier(
    client: AsyncClient,
    auth_headers: dict,
):
    """Test that setting an invalid frame tier fails."""
    response = await client.post(
        "/api/achievements/frames/active",
        json={"frame_tier": "mythic"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Invalid frame tier" in response.json()["detail"]


@pytest.mark.asyncio
async def test_set_active_frame_success(
    client: AsyncClient,
    auth_headers: dict,
    db_session,
    test_user,
):
    """Test successfully setting an active frame."""
    # Unlock the gold frame for the user
    user_frame = UserFrame(
        user_id=test_user.id,
        frame_tier="gold",
        is_active=False,
    )
    db_session.add(user_frame)
    await db_session.commit()

    response = await client.post(
        "/api/achievements/frames/active",
        json={"frame_tier": "gold"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["active_frame"] == "gold"
    gold_frame = next(
        (f for f in data["frames"] if f["tier"] == "gold"),
        None,
    )
    assert gold_frame is not None
    assert gold_frame["is_active"] is True


@pytest.mark.asyncio
async def test_set_active_frame_case_insensitive(
    client: AsyncClient,
    auth_headers: dict,
    db_session,
    test_user,
):
    """Test that frame tier is case-insensitive."""
    # Unlock the silver frame
    user_frame = UserFrame(
        user_id=test_user.id,
        frame_tier="silver",
        is_active=False,
    )
    db_session.add(user_frame)
    await db_session.commit()

    response = await client.post(
        "/api/achievements/frames/active",
        json={"frame_tier": "SILVER"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["active_frame"] == "silver"
