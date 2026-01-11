"""
Authentication API endpoints for user registration, login, and profile management.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.schemas.auth import (
    PasswordChange,
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdate,
)
from app.services.auth import (
    authenticate_user,
    blacklist_token,
    create_token_pair,
    create_user,
    decode_refresh_token,
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
    update_password,
    verify_password,
)
from app.utils.password import validate_password_strength, is_common_password

router = APIRouter()
logger = structlog.get_logger()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user account.
    
    - **email**: Valid email address (must be unique)
    - **username**: 3-50 characters, alphanumeric with underscores/hyphens (must be unique)
    - **password**: Minimum 12 characters with uppercase, lowercase, digit, and special character
    - **display_name**: Optional display name
    """
    # Check if email already exists
    existing_user = await get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Check if username already exists
    existing_username = await get_user_by_username(db, user_data.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    # Validate password strength
    is_valid, error_msg = validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    if is_common_password(user_data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is too common. Please choose a more secure password.",
        )

    # Create user
    user = await create_user(db, user_data)
    
    logger.info("New user registered", email=user.email, username=user.username)
    
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """
    Login with email and password to receive access and refresh tokens.

    The access token should be included in the Authorization header as:
    `Authorization: Bearer <token>`

    Use the refresh token with the /refresh endpoint to get new tokens
    when the access token expires.
    """
    user = await authenticate_user(db, credentials.email, credentials.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, refresh_token, expires_in = create_token_pair(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Exchange a refresh token for a new access/refresh token pair."""
    token_data = decode_refresh_token(request.refresh_token)

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = int(token_data.sub)
    user = await get_user_by_id(db, user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Blacklist the old refresh token (rotation)
    blacklist_token(request.refresh_token)

    # Create new token pair
    access_token, refresh_token, expires_in = create_token_pair(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: CurrentUser,
):
    """
    Get the current authenticated user's profile.
    """
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    updates: UserUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Update the current user's profile.
    
    Only allows updating whitelisted fields (display_name).
    Security-sensitive fields (is_admin, is_active, email, etc.) cannot be updated via this endpoint.
    """
    update_data = updates.model_dump(exclude_unset=True)
    
    # Whitelist of allowed fields for security
    allowed_fields = {"display_name"}
    
    for field, value in update_data.items():
        if field not in allowed_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Field '{field}' is not allowed to be updated via this endpoint"
            )
        setattr(current_user, field, value)
    
    await db.commit()
    await db.refresh(current_user)
    
    return current_user


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Change the current user's password.
    
    Requires the current password for verification.
    """
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Validate new password strength
    is_valid, error_msg = validate_password_strength(password_data.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    if is_common_password(password_data.new_password):
        raise HTTPException(status_code=400, detail="Password is too common. Please choose a more secure password.")

    await update_password(db, current_user, password_data.new_password)
    
    return {"message": "Password updated successfully"}


@router.post("/logout")
async def logout(
    request: Request,
    current_user: CurrentUser,
):
    """
    Logout the current user and invalidate their token.

    The token is added to a blacklist to prevent further use until expiration.
    """
    # Get token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remove "Bearer " prefix
        if blacklist_token(token):
            logger.info("User logged out, token blacklisted", user_id=current_user.id)
        else:
            logger.warning("User logged out, but token blacklisting failed", user_id=current_user.id)
    else:
        logger.info("User logged out (no token to blacklist)", user_id=current_user.id)

    return {"message": "Successfully logged out"}



