"""
Authentication API endpoints for user registration, login, and profile management.
"""
from datetime import timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.schemas.auth import (
    PasswordChange,
    Token,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdate,
)
from app.services.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    authenticate_user,
    blacklist_token,
    create_access_token,
    create_user,
    get_user_by_email,
    get_user_by_username,
    update_password,
    verify_password,
)

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
    - **password**: Minimum 8 characters with uppercase, lowercase, and digit
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
    
    # Create user
    user = await create_user(db, user_data)
    
    logger.info("New user registered", email=user.email, username=user.username)
    
    return user


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """
    Login with email and password to receive an access token.
    
    The token should be included in the Authorization header as:
    `Authorization: Bearer <token>`
    """
    user = await authenticate_user(db, credentials.email, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(user.id)
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
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



