"""
Authentication API endpoints for user registration, login, and profile management.
"""
from datetime import timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
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
    """
    update_data = updates.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
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
    current_user: CurrentUser,
):
    """
    Logout the current user.
    
    Note: Since we use stateless JWT tokens, the actual token invalidation
    should be handled client-side by removing the stored token.
    For enhanced security, consider implementing a token blacklist.
    """
    logger.info("User logged out", user_id=current_user.id)
    return {"message": "Successfully logged out"}



