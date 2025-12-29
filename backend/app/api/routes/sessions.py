"""Session management endpoints."""
import hashlib
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.session import UserSession

security = HTTPBearer()

router = APIRouter(prefix="/sessions", tags=["Sessions"])


class SessionResponse(BaseModel):
    """Response model for user session."""

    id: int
    device_info: str | None
    ip_address: str | None
    created_at: datetime
    last_active: datetime
    is_current: bool

    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=List[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> List[SessionResponse]:
    """List all active sessions for current user."""
    # Hash current token to identify the current session
    current_token_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()

    result = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == current_user.id)
        .where(UserSession.is_revoked == False)  # noqa: E712
        .where(UserSession.expires_at > datetime.now(timezone.utc))
        .order_by(UserSession.last_active.desc())
    )
    sessions = result.scalars().all()

    return [
        SessionResponse(
            id=s.id,
            device_info=s.device_info,
            ip_address=s.ip_address,
            created_at=s.created_at,
            last_active=s.last_active,
            is_current=(s.token_hash == current_token_hash),
        )
        for s in sessions
    ]


@router.delete("/{session_id}")
async def revoke_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke a specific session."""
    result = await db.execute(
        select(UserSession)
        .where(UserSession.id == session_id)
        .where(UserSession.user_id == current_user.id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.is_revoked = True
    await db.commit()

    return {"message": "Session revoked"}


@router.delete("/")
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke all sessions for current user."""
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == current_user.id)
        .where(UserSession.is_revoked == False)  # noqa: E712
        .values(is_revoked=True)
    )
    await db.commit()

    return {"message": "All sessions revoked"}
