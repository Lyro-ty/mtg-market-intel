---
name: mtg-intel:api-development
description: Use when creating or modifying backend API routes, schemas, or endpoints
---

# API Development Skill for Dualcaster Deals

Follow these patterns when developing backend API routes.

## File Structure

Every new endpoint needs these files:
```
backend/app/
├── api/routes/{feature}.py      # Route handlers
├── schemas/{feature}.py         # Pydantic request/response models
├── models/{feature}.py          # SQLAlchemy models (if new table)
└── tests/api/test_{feature}.py  # pytest tests
```

## Route Pattern

```python
# backend/app/api/routes/{feature}.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import User
from app.schemas.{feature} import {Feature}Response, {Feature}Create

router = APIRouter(prefix="/{feature}", tags=["{feature}"])

@router.get("/{id}", response_model={Feature}Response)
async def get_{feature}(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single {feature} by ID."""
    result = await db.execute(
        select({Feature}).where({Feature}.id == id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="{Feature} not found")

    # IMPORTANT: Check ownership if user-scoped
    if item.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return item

@router.post("/", response_model={Feature}Response, status_code=201)
async def create_{feature}(
    data: {Feature}Create,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new {feature}."""
    item = {Feature}(**data.model_dump(), user_id=current_user.id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item
```

## Schema Pattern

```python
# backend/app/schemas/{feature}.py
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field

class {Feature}Base(BaseModel):
    """Shared fields."""
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None

class {Feature}Create({Feature}Base):
    """Request body for creation."""
    pass

class {Feature}Update(BaseModel):
    """Partial update - all fields optional."""
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None

class {Feature}Response({Feature}Base):
    """Response model - includes id and timestamps."""
    id: int
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True
```

## Test Pattern

```python
# backend/tests/api/test_{feature}.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_{feature}(client: AsyncClient, auth_headers, test_{feature}):
    """GET /{feature}/{id} returns the item."""
    response = await client.get(
        f"/api/{feature}/{test_{feature}.id}",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_{feature}.id
    assert data["name"] == test_{feature}.name

@pytest.mark.asyncio
async def test_get_{feature}_not_found(client: AsyncClient, auth_headers):
    """GET /{feature}/999999 returns 404."""
    response = await client.get("/api/{feature}/999999", headers=auth_headers)
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_create_{feature}(client: AsyncClient, auth_headers):
    """POST /{feature}/ creates a new item."""
    response = await client.post(
        "/api/{feature}/",
        headers=auth_headers,
        json={"name": "Test Item", "description": "Test description"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Item"
    assert "id" in data
```

## Registration

Add to `backend/app/api/__init__.py`:

```python
from app.api.routes import {feature}

api_router.include_router({feature}.router)
```

## Checklist

Before committing:
- [ ] Route file created with proper imports
- [ ] Schema file created with Base/Create/Update/Response models
- [ ] Tests written and passing
- [ ] Route registered in api/__init__.py
- [ ] Run `make generate-types` to update frontend types
- [ ] Run `make lint` to check formatting
- [ ] Run `make test-backend` to verify tests pass

## Common Patterns

### Pagination (cursor-based)
```python
@router.get("/", response_model=list[{Feature}Response])
async def list_{feature}s(
    cursor: int | None = Query(None, description="Last ID from previous page"),
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select({Feature}).where({Feature}.user_id == current_user.id)
    if cursor:
        query = query.where({Feature}.id > cursor)
    query = query.order_by({Feature}.id).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
```

### Filtering
```python
@router.get("/", response_model=list[{Feature}Response])
async def list_{feature}s(
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select({Feature})
    if status:
        query = query.where({Feature}.status == status)
    result = await db.execute(query)
    return result.scalars().all()
```

### Eager Loading (prevent N+1)
```python
from sqlalchemy.orm import selectinload

query = select({Feature}).options(
    selectinload({Feature}.related_items)
)
```
