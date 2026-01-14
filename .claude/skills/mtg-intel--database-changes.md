---
name: mtg-intel:database-changes
description: Use when creating database migrations, modifying models, or adding new tables
---

# Database Changes Skill for Dualcaster Deals

Follow these patterns when modifying the database schema.

## File Structure

```
backend/
├── alembic/
│   └── versions/
│       └── YYYYMMDD_NNN_{description}.py  # Migration files
├── app/
│   ├── models/
│   │   ├── __init__.py        # Export all models
│   │   └── {feature}.py       # Model definitions
│   └── schemas/
│       └── {feature}.py       # Pydantic schemas (must match!)
```

## Creating a Migration

```bash
# Generate migration from model changes
docker compose exec backend alembic revision --autogenerate -m "add {feature} table"

# Or create empty migration
docker compose exec backend alembic revision -m "add {feature} table"
```

## Migration Pattern

```python
# backend/alembic/versions/YYYYMMDD_NNN_add_{feature}_table.py
"""Add {feature} table.

Revision ID: abc123
Revises: xyz789
Create Date: 2026-01-13 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'abc123'
down_revision = 'xyz789'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        '{feature}s',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for common queries
    op.create_index('ix_{feature}s_user_id', '{feature}s', ['user_id'])
    op.create_index('ix_{feature}s_status', '{feature}s', ['status'])


def downgrade():
    op.drop_index('ix_{feature}s_status')
    op.drop_index('ix_{feature}s_user_id')
    op.drop_table('{feature}s')
```

## Model Pattern

```python
# backend/app/models/{feature}.py
from datetime import datetime
from sqlalchemy import ForeignKey, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class {Feature}(Base):
    __tablename__ = "{feature}s"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.text("now()")
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="{feature}s")

    def __repr__(self) -> str:
        return f"<{Feature}(id={self.id}, name={self.name!r})>"
```

## Register Model

```python
# backend/app/models/__init__.py
from app.models.{feature} import {Feature}

__all__ = [
    # ... existing exports
    "{Feature}",
]
```

## Schema Consistency

**CRITICAL:** Schema field names MUST match model field names!

```python
# backend/app/schemas/{feature}.py
from pydantic import BaseModel

class {Feature}Response(BaseModel):
    id: int           # Must match model
    name: str         # Must match model
    description: str | None  # Must match model

    class Config:
        from_attributes = True
```

## Running Migrations

```bash
# Apply all pending migrations
docker compose exec backend alembic upgrade head

# Or via Makefile
make migrate

# Check current revision
docker compose exec backend alembic current

# View migration history
docker compose exec backend alembic history
```

## Checklist

Before committing:
- [ ] Migration file created with upgrade AND downgrade
- [ ] Model file created with proper types
- [ ] Model exported in models/__init__.py
- [ ] Schema matches model field names exactly
- [ ] Foreign keys have ondelete behavior
- [ ] Indexes created for common query patterns
- [ ] Run `make migrate` to apply
- [ ] Run `make generate-types` to update frontend types
- [ ] Run `make test-backend` to verify

## Common Patterns

### Adding a Column to Existing Table
```python
def upgrade():
    op.add_column('users',
        sa.Column('avatar_url', sa.String(500), nullable=True)
    )

def downgrade():
    op.drop_column('users', 'avatar_url')
```

### Adding an Index
```python
def upgrade():
    op.create_index('ix_cards_set_code', 'cards', ['set_code'])

def downgrade():
    op.drop_index('ix_cards_set_code')
```

### Renaming a Column
```python
def upgrade():
    op.alter_column('users', 'name', new_column_name='display_name')

def downgrade():
    op.alter_column('users', 'display_name', new_column_name='name')
```

### Adding Enum Column
```python
def upgrade():
    # Create enum type first
    status_enum = sa.Enum('draft', 'active', 'archived', name='item_status')
    status_enum.create(op.get_bind(), checkfirst=True)

    op.add_column('items',
        sa.Column('status', status_enum, server_default='draft', nullable=False)
    )

def downgrade():
    op.drop_column('items', 'status')
    sa.Enum(name='item_status').drop(op.get_bind(), checkfirst=True)
```

### Many-to-Many Relationship
```python
def upgrade():
    op.create_table(
        '{feature}_tags',
        sa.Column('{feature}_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['{feature}_id'], ['{feature}s.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('{feature}_id', 'tag_id')
    )
```

## Important Notes

1. **Never modify existing migrations** that have been applied in production
2. **Always test downgrade** to ensure reversibility
3. **Use server_default** for columns with defaults (not just default=)
4. **Add indexes** for foreign keys and commonly filtered columns
5. **Run type generation** after schema changes: `make generate-types`
