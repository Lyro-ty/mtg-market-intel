"""
Favorites and Private Notes API endpoints.

Allows users to:
- Add/remove other users as favorites for quick access
- Set notification preferences for favorites
- Create private notes about other users
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.models.social import UserFavorite, UserNote
from app.schemas.favorites import (
    FavoriteUserResponse,
    FavoritesListResponse,
    AddFavoriteRequest,
    UserNoteResponse,
    NotesListResponse,
    CreateNoteRequest,
)

router = APIRouter(prefix="/favorites", tags=["Favorites"])
logger = structlog.get_logger(__name__)


# ============ Favorites Endpoints ============


@router.get("", response_model=FavoritesListResponse)
async def get_favorites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's list of favorited users.

    Returns all users the current user has added to favorites,
    ordered by most recently added first.
    """
    result = await db.execute(
        select(UserFavorite)
        .where(UserFavorite.user_id == current_user.id)
        .options(selectinload(UserFavorite.favorited_user))
        .order_by(UserFavorite.created_at.desc())
    )
    favorites = result.scalars().all()

    return FavoritesListResponse(
        favorites=[
            FavoriteUserResponse(
                id=f.id,
                favorited_user_id=f.favorited_user_id,
                username=f.favorited_user.username,
                display_name=f.favorited_user.display_name,
                avatar_url=f.favorited_user.avatar_url,
                frame_tier=f.favorited_user.active_frame_tier or "bronze",
                notify_on_listings=f.notify_on_listings,
                created_at=f.created_at,
            )
            for f in favorites
            if f.favorited_user
        ],
        total=len(favorites),
    )


@router.post("/{user_id}")
async def add_favorite(
    user_id: int,
    request: AddFavoriteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Add a user to favorites.

    Allows setting notification preferences for when this user posts new listings.
    """
    # Cannot favorite yourself
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot favorite yourself")

    # Check user exists
    target_user = await db.get(User, user_id)
    if not target_user or not target_user.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if already favorited
    existing = await db.execute(
        select(UserFavorite).where(
            UserFavorite.user_id == current_user.id,
            UserFavorite.favorited_user_id == user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already in favorites")

    favorite = UserFavorite(
        user_id=current_user.id,
        favorited_user_id=user_id,
        notify_on_listings=request.notify_on_listings,
    )
    db.add(favorite)
    await db.commit()

    logger.info(
        "User added to favorites",
        user_id=current_user.id,
        favorited_user_id=user_id,
        notify_on_listings=request.notify_on_listings,
    )

    return {"status": "ok"}


@router.delete("/{user_id}")
async def remove_favorite(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Remove a user from favorites.
    """
    result = await db.execute(
        delete(UserFavorite).where(
            UserFavorite.user_id == current_user.id,
            UserFavorite.favorited_user_id == user_id,
        )
    )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Favorite not found")

    await db.commit()

    logger.info(
        "User removed from favorites",
        user_id=current_user.id,
        favorited_user_id=user_id,
    )

    return {"status": "ok"}


@router.patch("/{user_id}")
async def update_favorite(
    user_id: int,
    request: AddFavoriteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update favorite settings (e.g., notification preferences).
    """
    result = await db.execute(
        select(UserFavorite).where(
            UserFavorite.user_id == current_user.id,
            UserFavorite.favorited_user_id == user_id,
        )
    )
    favorite = result.scalar_one_or_none()

    if not favorite:
        raise HTTPException(status_code=404, detail="Favorite not found")

    favorite.notify_on_listings = request.notify_on_listings
    await db.commit()

    logger.info(
        "Favorite settings updated",
        user_id=current_user.id,
        favorited_user_id=user_id,
        notify_on_listings=request.notify_on_listings,
    )

    return {"status": "ok"}


# ============ Notes Endpoints ============


@router.get("/notes", response_model=NotesListResponse)
async def get_all_notes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all private notes the current user has created.

    Notes are private and only visible to the user who created them.
    Ordered by most recently updated first.
    """
    result = await db.execute(
        select(UserNote)
        .where(UserNote.user_id == current_user.id)
        .options(selectinload(UserNote.target_user))
        .order_by(UserNote.updated_at.desc())
    )
    notes = result.scalars().all()

    return NotesListResponse(
        notes=[
            UserNoteResponse(
                id=n.id,
                target_user_id=n.target_user_id,
                username=n.target_user.username,
                display_name=n.target_user.display_name,
                content=n.content,
                created_at=n.created_at,
                updated_at=n.updated_at,
            )
            for n in notes
            if n.target_user
        ],
        total=len(notes),
    )


@router.get("/notes/{user_id}", response_model=UserNoteResponse)
async def get_note(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get private note for a specific user.
    """
    result = await db.execute(
        select(UserNote)
        .where(
            UserNote.user_id == current_user.id,
            UserNote.target_user_id == user_id,
        )
        .options(selectinload(UserNote.target_user))
    )
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    return UserNoteResponse(
        id=note.id,
        target_user_id=note.target_user_id,
        username=note.target_user.username,
        display_name=note.target_user.display_name,
        content=note.content,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.put("/notes/{user_id}", response_model=UserNoteResponse)
async def create_or_update_note(
    user_id: int,
    request: CreateNoteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create or update a private note for a user.

    If a note already exists, it will be updated.
    If no note exists, a new one will be created.
    """
    # Check target user exists
    target_user = await db.get(User, user_id)
    if not target_user or not target_user.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    # Check for existing note
    result = await db.execute(
        select(UserNote)
        .where(
            UserNote.user_id == current_user.id,
            UserNote.target_user_id == user_id,
        )
        .options(selectinload(UserNote.target_user))
    )
    note = result.scalar_one_or_none()

    if note:
        # Update existing note
        note.content = request.content
        await db.commit()
        await db.refresh(note)
        logger.info(
            "Note updated",
            user_id=current_user.id,
            target_user_id=user_id,
        )
    else:
        # Create new note
        note = UserNote(
            user_id=current_user.id,
            target_user_id=user_id,
            content=request.content,
        )
        db.add(note)
        await db.commit()
        await db.refresh(note)

        # Load the target_user relationship
        await db.refresh(note, ["target_user"])

        logger.info(
            "Note created",
            user_id=current_user.id,
            target_user_id=user_id,
        )

    return UserNoteResponse(
        id=note.id,
        target_user_id=note.target_user_id,
        username=note.target_user.username,
        display_name=note.target_user.display_name,
        content=note.content,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.delete("/notes/{user_id}")
async def delete_note(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a private note for a user.
    """
    result = await db.execute(
        delete(UserNote).where(
            UserNote.user_id == current_user.id,
            UserNote.target_user_id == user_id,
        )
    )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Note not found")

    await db.commit()

    logger.info(
        "Note deleted",
        user_id=current_user.id,
        target_user_id=user_id,
    )

    return {"status": "ok"}
