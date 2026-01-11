"""
Authentication service for user management, password hashing, and JWT tokens.

Security measures implemented:
- bcrypt password hashing (cost factor 12)
- JWT tokens with expiration and unique JTI
- Token blacklist for secure logout
- Account lockout after failed attempts
- Timing-attack resistant password comparison
- Email normalization
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.config import settings
from app.core.token_blacklist import get_token_blacklist
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
ACCESS_TOKEN_EXPIRE_MINUTES = settings.jwt_access_token_expire_minutes


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
    """
    Create a JWT access token with unique JTI for blacklist support.

    Args:
        user_id: User ID to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token
    """
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # Generate unique JTI for blacklist support
    jti = str(uuid.uuid4())

    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "jti": jti,  # JWT ID for blacklist
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
    - Token not in blacklist
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)

        # Validate token type
        if token_data.type != "access":
            logger.warning("Invalid token type", token_type=token_data.type)
            return None

        # Check if token is blacklisted
        if token_data.jti:
            blacklist = get_token_blacklist()
            if blacklist.is_blacklisted(token_data.jti):
                logger.warning("Token is blacklisted", jti=token_data.jti)
                return None

        return token_data
    except JWTError as e:
        logger.warning("JWT decode error", error=str(e))
        return None


def blacklist_token(token: str) -> bool:
    """
    Add a token to the blacklist.

    Args:
        token: JWT token to blacklist

    Returns:
        True if token was successfully blacklisted
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        exp = payload.get("exp")

        if not jti or not exp:
            logger.warning("Token missing JTI or exp claim")
            return False

        # Convert exp to datetime
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)

        blacklist = get_token_blacklist()
        return blacklist.add(jti, expires_at)
    except JWTError as e:
        logger.warning("Failed to blacklist token", error=str(e))
        return False


def create_refresh_token(user_id: int) -> str:
    """Create a refresh token for token rotation."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)
    jti = str(uuid.uuid4())

    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "jti": jti,
        "type": "refresh",
    }

    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_refresh_token(token: str) -> Optional[TokenPayload]:
    """Decode and validate a refresh token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)

        if token_data.type != "refresh":
            logger.warning("Token is not a refresh token", token_type=token_data.type)
            return None

        # Check blacklist
        if token_data.jti:
            blacklist = get_token_blacklist()
            if blacklist.is_blacklisted(token_data.jti):
                logger.warning("Refresh token is blacklisted", jti=token_data.jti)
                return None

        return token_data
    except JWTError as e:
        logger.warning("Refresh token decode error", error=str(e))
        return None


def create_token_pair(user_id: int) -> tuple[str, str, int]:
    """Create an access/refresh token pair."""
    access_token = create_access_token(
        user_id,
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    refresh_token = create_refresh_token(user_id)
    expires_in = settings.jwt_access_token_expire_minutes * 60

    return access_token, refresh_token, expires_in


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

