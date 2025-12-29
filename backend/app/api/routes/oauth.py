"""Google OAuth authentication routes."""
import secrets
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import RedirectResponse
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.services.auth import create_access_token

router = APIRouter()

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
    query_string = "&".join(f"{k}={v}" for k, v in params.items())

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
