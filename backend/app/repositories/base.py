"""
Base repository class with common database operations.

This module provides the foundation for all repository classes,
implementing common patterns like CRUD operations and query building.
"""
from typing import Any, Generic, TypeVar, Type, Sequence
from datetime import datetime

from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

# Type variable for generic repository
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Base repository implementing common database operations.

    Provides type-safe CRUD operations and query building utilities
    that can be reused across all repositories.

    Usage:
        class UserRepository(BaseRepository[User]):
            def __init__(self, db: AsyncSession):
                super().__init__(User, db)

            async def find_by_email(self, email: str) -> User | None:
                return await self.find_one_by(email=email)
    """

    def __init__(self, model: Type[ModelType], db: AsyncSession):
        """
        Initialize the repository.

        Args:
            model: SQLAlchemy model class this repository manages
            db: Async database session
        """
        self.model = model
        self.db = db

    async def get_by_id(self, id: int) -> ModelType | None:
        """
        Get a single record by its primary key.

        Args:
            id: Primary key value

        Returns:
            Model instance or None if not found
        """
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
        order_desc: bool = False,
    ) -> Sequence[ModelType]:
        """
        Get all records with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum records to return
            order_by: Column name to order by
            order_desc: If True, order descending

        Returns:
            Sequence of model instances
        """
        query = select(self.model)

        if order_by and hasattr(self.model, order_by):
            column = getattr(self.model, order_by)
            query = query.order_by(column.desc() if order_desc else column)

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def find_one_by(self, **kwargs: Any) -> ModelType | None:
        """
        Find a single record by arbitrary column values.

        Args:
            **kwargs: Column name/value pairs to filter by

        Returns:
            Model instance or None if not found
        """
        query = select(self.model)
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def find_by(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        **kwargs: Any,
    ) -> Sequence[ModelType]:
        """
        Find records by arbitrary column values.

        Args:
            skip: Number of records to skip
            limit: Maximum records to return
            **kwargs: Column name/value pairs to filter by

        Returns:
            Sequence of model instances
        """
        query = select(self.model)
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def count(self, **kwargs: Any) -> int:
        """
        Count records, optionally filtered by column values.

        Args:
            **kwargs: Column name/value pairs to filter by

        Returns:
            Number of matching records
        """
        query = select(func.count()).select_from(self.model)
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def exists(self, **kwargs: Any) -> bool:
        """
        Check if any record exists matching the criteria.

        Args:
            **kwargs: Column name/value pairs to filter by

        Returns:
            True if at least one matching record exists
        """
        return await self.count(**kwargs) > 0

    async def create(self, **kwargs: Any) -> ModelType:
        """
        Create a new record.

        Args:
            **kwargs: Column name/value pairs for the new record

        Returns:
            Created model instance
        """
        instance = self.model(**kwargs)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def update(self, id: int, **kwargs: Any) -> ModelType | None:
        """
        Update a record by ID.

        Args:
            id: Primary key of record to update
            **kwargs: Column name/value pairs to update

        Returns:
            Updated model instance or None if not found
        """
        instance = await self.get_by_id(id)
        if instance is None:
            return None

        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        if hasattr(instance, "updated_at"):
            instance.updated_at = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def delete(self, id: int) -> bool:
        """
        Delete a record by ID.

        Args:
            id: Primary key of record to delete

        Returns:
            True if record was deleted, False if not found
        """
        instance = await self.get_by_id(id)
        if instance is None:
            return False

        await self.db.delete(instance)
        await self.db.flush()
        return True

    async def bulk_create(self, items: list[dict[str, Any]]) -> list[ModelType]:
        """
        Create multiple records in a batch.

        Args:
            items: List of dictionaries with column values

        Returns:
            List of created model instances
        """
        instances = [self.model(**item) for item in items]
        self.db.add_all(instances)
        await self.db.flush()
        return instances

    async def bulk_delete(self, **kwargs: Any) -> int:
        """
        Delete multiple records matching criteria.

        Args:
            **kwargs: Column name/value pairs to filter by

        Returns:
            Number of deleted records
        """
        query = delete(self.model)
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)
        result = await self.db.execute(query)
        await self.db.flush()
        return result.rowcount
