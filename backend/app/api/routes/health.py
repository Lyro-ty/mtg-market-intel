"""
Health check endpoints.
"""
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint.
    
    Returns service status and database connectivity.
    """
    # Check database
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    
    return {
        "status": "healthy" if db_ok else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "api": "ok",
            "database": "ok" if db_ok else "error",
        },
    }


@router.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "MTG Market Intel API",
        "version": "1.0.0",
        "docs": "/docs",
    }

