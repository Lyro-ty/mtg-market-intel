"""OAuth authentication routes for Google and Discord."""
import secrets
from urllib.parse import urlencode
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import RedirectResponse
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.api.deps import get_current_user
from app.services.auth import create_access_token

router = APIRouter()
logger = structlog.get_logger(__name__)

# Redis client for state storage
_redis_client = None


def get_redis():
    """Get Redis client for OAuth state storage."""
    global _redis_client
    if _redis_client is None:
        import redis
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


@router.get("/google/login")
async def google_login():
    """Redirect to Google OAuth login."""
    if not settings.OAUTH_ENABLED:
        raise HTTPException(status_code=400, detail="OAuth is not enabled")

    # Generate state and store in Redis (5 minute TTL)
    state = secrets.token_urlsafe(32)
    redis_client = get_redis()
    redis_client.setex(f"oauth_state:{state}", 300, "valid")

    # Build Google OAuth URL
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    query_string = urlencode(params)

    return RedirectResponse(url=f"{auth_url}?{query_string}")


@router.get("/google/callback")
async def google_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth callback."""
    if not settings.OAUTH_ENABLED:
        raise HTTPException(status_code=400, detail="OAuth is not enabled")

    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter")

    # Verify state from Redis
    redis_client = get_redis()
    stored_state = redis_client.get(f"oauth_state:{state}")
    if not stored_state:
        raise HTTPException(status_code=400, detail="Invalid or expired state. Please try logging in again.")

    # Delete state to prevent reuse
    redis_client.delete(f"oauth_state:{state}")

    # Exchange code for tokens
    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                },
            )

            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to exchange code: {token_response.text}"
                )

            tokens = token_response.json()

            # Get user info
            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )

            if userinfo_response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get user info")

            user_info = userinfo_response.json()

    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"OAuth request failed: {str(e)}")

    email = user_info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email not provided by Google")

    # Find or create user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # Create new user from Google data
        user = User(
            email=email,
            username=user_info.get("name", email.split("@")[0]),
            hashed_password="",  # No password for OAuth users
            is_active=True,
            oauth_provider="google",
            oauth_id=user_info.get("sub"),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif not user.oauth_provider:
        # Link existing user to Google
        user.oauth_provider = "google"
        user.oauth_id = user_info.get("sub")
        await db.commit()

    # Create JWT token
    access_token = create_access_token(user.id)

    # Redirect to frontend with token
    frontend_url = settings.frontend_url
    return RedirectResponse(
        url=f"{frontend_url}/login?token={access_token}",
        status_code=302,
    )


# =============================================================================
# Discord OAuth Routes
# =============================================================================

DISCORD_OAUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"
DISCORD_SCOPES = "identify"


@router.get("/discord/link")
async def discord_link(
    current_user: User = Depends(get_current_user),
):
    """
    Initiate Discord account linking.

    Redirects to Discord OAuth to authorize account linking.
    Requires authentication.
    """
    if not settings.DISCORD_CLIENT_ID:
        raise HTTPException(status_code=400, detail="Discord OAuth is not configured")

    # Generate state with user ID encoded
    state = secrets.token_urlsafe(32)
    redis_client = get_redis()
    # Store user_id with state for callback (5 minute TTL)
    redis_client.setex(f"discord_state:{state}", 300, str(current_user.id))

    params = {
        "client_id": settings.DISCORD_CLIENT_ID,
        "redirect_uri": settings.DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": DISCORD_SCOPES,
        "state": state,
    }

    auth_url = f"{DISCORD_OAUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/discord/callback")
async def discord_callback(
    code: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    error_description: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Discord OAuth callback.

    Links the Discord account to the user who initiated the flow.
    """
    if error:
        logger.warning("Discord OAuth error", error=error, description=error_description)
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?discord_error={error}",
            status_code=302,
        )

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter")

    # Retrieve user_id from state
    redis_client = get_redis()
    user_id_str = redis_client.get(f"discord_state:{state}")
    if not user_id_str:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    # Delete state to prevent reuse
    redis_client.delete(f"discord_state:{state}")

    user_id = int(user_id_str)

    # Exchange code for access token
    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                DISCORD_TOKEN_URL,
                data={
                    "client_id": settings.DISCORD_CLIENT_ID,
                    "client_secret": settings.DISCORD_CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.DISCORD_REDIRECT_URI,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if token_response.status_code != 200:
                logger.error(
                    "Discord token exchange failed",
                    status=token_response.status_code,
                    body=token_response.text,
                )
                return RedirectResponse(
                    url=f"{settings.frontend_url}/settings?discord_error=token_exchange_failed",
                    status_code=302,
                )

            tokens = token_response.json()
            access_token = tokens["access_token"]

            # Get Discord user info
            user_response = await client.get(
                DISCORD_USER_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if user_response.status_code != 200:
                logger.error("Failed to get Discord user info", status=user_response.status_code)
                return RedirectResponse(
                    url=f"{settings.frontend_url}/settings?discord_error=user_fetch_failed",
                    status_code=302,
                )

            discord_user = user_response.json()

    except httpx.RequestError as e:
        logger.error("Discord OAuth request failed", error=str(e))
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?discord_error=request_failed",
            status_code=302,
        )

    discord_id = discord_user["id"]
    discord_username = discord_user.get("username", "")

    # Check if Discord account is already linked to another user
    existing_result = await db.execute(
        select(User).where(User.discord_id == discord_id)
    )
    existing_user = existing_result.scalar_one_or_none()

    if existing_user and existing_user.id != user_id:
        logger.warning(
            "Discord account already linked",
            discord_id=discord_id,
            existing_user_id=existing_user.id,
            requesting_user_id=user_id,
        )
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?discord_error=already_linked",
            status_code=302,
        )

    # Update user with Discord info
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.discord_id = discord_id
    user.discord_username = discord_username
    await db.commit()

    logger.info(
        "Discord account linked",
        user_id=user_id,
        discord_id=discord_id,
        discord_username=discord_username,
    )

    return RedirectResponse(
        url=f"{settings.frontend_url}/settings?discord_linked=true",
        status_code=302,
    )


@router.delete("/discord/unlink")
async def discord_unlink(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Unlink Discord account from user.

    Removes the Discord connection from the authenticated user's account.
    """
    if not current_user.discord_id:
        raise HTTPException(status_code=400, detail="No Discord account linked")

    old_discord_id = current_user.discord_id
    current_user.discord_id = None
    current_user.discord_username = None
    await db.commit()

    logger.info(
        "Discord account unlinked",
        user_id=current_user.id,
        discord_id=old_discord_id,
    )

    return {"message": "Discord account unlinked successfully"}
