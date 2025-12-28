"""Google OAuth authentication routes."""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.services.auth import create_access_token

router = APIRouter()

# Initialize OAuth client
oauth = OAuth()

if settings.OAUTH_ENABLED and settings.GOOGLE_CLIENT_ID:
    oauth.register(
        name="google",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


@router.get("/google/login")
async def google_login(request: Request):
    """Redirect to Google OAuth login."""
    if not settings.OAUTH_ENABLED:
        raise HTTPException(status_code=400, detail="OAuth is not enabled")

    redirect_uri = settings.GOOGLE_REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Google OAuth callback."""
    if not settings.OAUTH_ENABLED:
        raise HTTPException(status_code=400, detail="OAuth is not enabled")

    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {str(e)}")

    user_info = token.get("userinfo")
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to get user info")

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
