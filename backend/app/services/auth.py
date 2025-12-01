"""
Authentication service for user management, password hashing, and JWT tokens.

Security measures implemented:
- bcrypt password hashing (cost factor 12)
- JWT tokens with expiration
- Account lockout after failed attempts
- Timing-attack resistant password comparison
- Email normalization
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.config import settings
from app.models.user import User
from app.schemas.auth import TokenPayload, UserRegister

logger = structlog.get_logger()

# Password hashing context with explicit bcrypt configuration
# Cost factor 12 provides good security while maintaining performance
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12
)

# JWT settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


def normalize_email(email: str) -> str:
    """Normalize email address for consistent comparison."""
    return email.lower().strip()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.
    
    Uses constant-time comparison to prevent timing attacks.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(user_id: int, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    now = datetime.now(timezone.utc)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "type": "access",
    }
    
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[TokenPayload]:
    """
    Decode and validate a JWT access token.
    
    Validates:
    - Token signature
    - Token expiration
    - Token type (must be "access")
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)
        
        # Validate token type
        if token_data.type != "access":
            logger.warning("Invalid token type", token_type=token_data.type)
            return None
        
        return token_data
    except JWTError as e:
        logger.warning("JWT decode error", error=str(e))
        return None


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get a user by email address (case-insensitive)."""
    normalized_email = normalize_email(email)
    result = await db.execute(
        select(User).where(User.email == normalized_email)
    )
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Get a user by username."""
    result = await db.execute(
        select(User).where(User.username == username)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Get a user by ID."""
    return await db.get(User, user_id)


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    """
    Authenticate a user with email and password.
    
    Security measures:
    - Constant-time password comparison via bcrypt
    - Performs dummy hash comparison when user doesn't exist (prevents timing attacks)
    - Account lockout after 5 failed attempts
    """
    user = await get_user_by_email(db, email)
    
    if not user:
        # Perform dummy hash to prevent timing attacks
        # This ensures the response time is similar whether user exists or not
        pwd_context.hash("dummy_password_for_timing_attack_prevention")
        logger.info("Authentication failed: user not found", email=email)
        return None
    
    # Check if account is locked
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        logger.warning("Authentication failed: account locked", email=email)
        return None
    
    if not verify_password(password, user.hashed_password):
        # Increment failed login attempts
        user.failed_login_attempts += 1
        
        # Lock account after 5 failed attempts for 30 minutes
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
            logger.warning("Account locked due to failed attempts", email=email)
        
        await db.commit()
        logger.info("Authentication failed: invalid password", email=email)
        return None
    
    if not user.is_active:
        logger.info("Authentication failed: user inactive", email=email)
        return None
    
    # Reset failed login attempts on successful login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    
    logger.info("User authenticated successfully", email=email)
    return user


async def create_user(db: AsyncSession, user_data: UserRegister) -> User:
    """
    Create a new user with secure password hashing.
    
    Email is normalized to lowercase for consistent lookups.
    """
    hashed_password = get_password_hash(user_data.password)
    
    user = User(
        email=normalize_email(user_data.email),
        username=user_data.username.strip(),
        hashed_password=hashed_password,
        display_name=user_data.display_name.strip() if user_data.display_name else None,
        is_active=True,
        is_verified=False,
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    logger.info("User created successfully", email=user.email, username=user.username)
    return user


async def update_password(db: AsyncSession, user: User, new_password: str) -> None:
    """Update a user's password."""
    user.hashed_password = get_password_hash(new_password)
    await db.commit()
    logger.info("Password updated", user_id=user.id)

