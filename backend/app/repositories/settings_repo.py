"""
Settings repository for user preferences and app configuration.

This repository handles user-specific settings stored as key-value
pairs with Redis caching for fast access.
"""
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import AppSettings
from app.repositories.cache_repo import CacheRepository


class SettingsRepository:
    """
    Repository for user settings operations.

    Settings are stored in the database with Redis caching
    for fast reads of frequently accessed values.
    """

    def __init__(self, db: AsyncSession, cache: CacheRepository | None = None):
        """
        Initialize the settings repository.

        Args:
            db: Async database session
            cache: Optional cache repository for Redis caching
        """
        self.db = db
        self.cache = cache

    async def get(
        self,
        user_id: int,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Get a user setting.

        Tries cache first, falls back to database.

        Args:
            user_id: User ID
            key: Setting key
            default: Default value if not found

        Returns:
            Setting value or default
        """
        # Try cache first
        if self.cache:
            cached = await self.cache.get("settings", str(user_id), key)
            if cached is not None:
                return cached

        # Query database
        stmt = select(AppSettings).where(
            AppSettings.user_id == user_id,
            AppSettings.key == key,
        )
        result = await self.db.execute(stmt)
        setting = result.scalar_one_or_none()

        value = setting.value if setting else default

        # Cache the result
        if self.cache and value is not None:
            await self.cache.set(
                "settings", str(user_id), key,
                value=value,
                ttl=timedelta(hours=1),
            )

        return value

    async def set(
        self,
        user_id: int,
        key: str,
        value: Any,
    ) -> None:
        """
        Set a user setting.

        Uses upsert to handle both create and update.
        Invalidates cache after update.

        Args:
            user_id: User ID
            key: Setting key
            value: Setting value
        """
        # Upsert the setting
        stmt = insert(AppSettings).values(
            user_id=user_id,
            key=key,
            value=value,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "key"],
            set_={"value": value},
        )
        await self.db.execute(stmt)
        await self.db.flush()

        # Invalidate cache
        if self.cache:
            await self.cache.delete("settings", str(user_id), key)

    async def delete(
        self,
        user_id: int,
        key: str,
    ) -> bool:
        """
        Delete a user setting.

        Args:
            user_id: User ID
            key: Setting key

        Returns:
            True if setting was deleted
        """
        stmt = select(AppSettings).where(
            AppSettings.user_id == user_id,
            AppSettings.key == key,
        )
        result = await self.db.execute(stmt)
        setting = result.scalar_one_or_none()

        if setting:
            await self.db.delete(setting)
            await self.db.flush()

            # Invalidate cache
            if self.cache:
                await self.cache.delete("settings", str(user_id), key)
            return True

        return False

    async def get_all(self, user_id: int) -> dict[str, Any]:
        """
        Get all settings for a user.

        Args:
            user_id: User ID

        Returns:
            Dictionary of key-value pairs
        """
        stmt = select(AppSettings).where(AppSettings.user_id == user_id)
        result = await self.db.execute(stmt)
        settings = result.scalars().all()

        return {s.key: s.value for s in settings}

    async def set_many(
        self,
        user_id: int,
        settings: dict[str, Any],
    ) -> None:
        """
        Set multiple settings at once.

        Args:
            user_id: User ID
            settings: Dictionary of key-value pairs
        """
        for key, value in settings.items():
            await self.set(user_id, key, value)

    async def delete_all(self, user_id: int) -> int:
        """
        Delete all settings for a user.

        Args:
            user_id: User ID

        Returns:
            Number of settings deleted
        """
        stmt = select(AppSettings).where(AppSettings.user_id == user_id)
        result = await self.db.execute(stmt)
        settings = result.scalars().all()

        count = 0
        for setting in settings:
            await self.db.delete(setting)
            count += 1

        await self.db.flush()

        # Invalidate all cached settings
        if self.cache:
            await self.cache.invalidate_pattern(f"settings:{user_id}:*")

        return count

    # Convenience methods for common settings
    async def get_currency_preference(self, user_id: int) -> str:
        """Get user's preferred currency."""
        return await self.get(user_id, "currency", default="USD")

    async def set_currency_preference(self, user_id: int, currency: str) -> None:
        """Set user's preferred currency."""
        await self.set(user_id, "currency", currency)

    async def get_theme(self, user_id: int) -> str:
        """Get user's theme preference."""
        return await self.get(user_id, "theme", default="system")

    async def set_theme(self, user_id: int, theme: str) -> None:
        """Set user's theme preference."""
        await self.set(user_id, "theme", theme)

    async def get_notification_settings(self, user_id: int) -> dict[str, bool]:
        """Get user's notification preferences."""
        return await self.get(user_id, "notifications", default={
            "price_alerts": True,
            "recommendations": True,
            "news": False,
        })

    async def set_notification_settings(
        self,
        user_id: int,
        settings: dict[str, bool],
    ) -> None:
        """Set user's notification preferences."""
        await self.set(user_id, "notifications", settings)
