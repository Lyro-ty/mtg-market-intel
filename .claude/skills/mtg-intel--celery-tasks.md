---
name: mtg-intel:celery-tasks
description: Use when creating or modifying Celery background tasks for ingestion, analytics, or scheduled work
---

# Celery Tasks Skill for Dualcaster Deals

Follow these patterns when developing background tasks.

## File Structure

```
backend/app/tasks/
├── celery_app.py          # Celery configuration & beat schedule
├── error_handlers.py      # Dead letter queue handling
├── {feature}.py           # Your task module
└── utils.py               # Shared utilities (run_async, etc.)
```

## Task Pattern

```python
# backend/app/tasks/{feature}.py
from celery import shared_task
from sqlalchemy import select
from structlog import get_logger

from app.db.session import create_task_session_maker
from app.tasks.utils import run_async, single_instance

logger = get_logger()

@shared_task(bind=True, max_retries=2, default_retry_delay=300)
@single_instance("{feature}_task", timeout=1800)  # Prevent concurrent runs
def {feature}_task(self, batch_size: int = 1000):
    """
    Brief description of what this task does.

    Args:
        batch_size: Number of items to process per batch

    Returns:
        dict with results summary
    """
    return run_async(_run_{feature}_task(batch_size))


async def _run_{feature}_task(batch_size: int) -> dict:
    """Async implementation of the task."""
    session_maker, engine = create_task_session_maker()
    results = {"processed": 0, "errors": 0}

    try:
        async with session_maker() as db:
            # Query items to process
            result = await db.execute(
                select(Model).limit(batch_size)
            )
            items = result.scalars().all()

            for item in items:
                try:
                    # Process item
                    await process_item(db, item)
                    results["processed"] += 1
                except Exception as e:
                    logger.error("item_processing_failed",
                                 item_id=item.id, error=str(e))
                    results["errors"] += 1

            await db.commit()

        logger.info("{feature}_task_complete", **results)
        return results

    except Exception as e:
        logger.error("{feature}_task_failed", error=str(e))
        raise

    finally:
        await engine.dispose()


async def process_item(db, item):
    """Process a single item."""
    # Your processing logic here
    pass
```

## Registration

Add to `backend/app/tasks/celery_app.py`:

```python
# In beat_schedule dict:
app.conf.beat_schedule["{feature}-task"] = {
    "task": "app.tasks.{feature}.{feature}_task",
    "schedule": crontab(minute="*/15"),  # Every 15 min
    # Or: crontab(hour="*/4")  # Every 4 hours
    # Or: crontab(hour="3", minute="0")  # Daily at 3 AM
    "kwargs": {"batch_size": 1000},
}

# In task_routes dict:
"app.tasks.{feature}.*": {"queue": "analytics"},  # Or "ingestion"
```

## Queue Selection

| Queue | Use For |
|-------|---------|
| `ingestion` | Data collection, scraping, imports |
| `analytics` | Metrics, signals, recommendations |
| `default` | General tasks |

## Error Handling

Tasks automatically go to dead letter queue on failure.

```python
# Check DLQ via MCP tool:
# mcp__mtg-intel__analyze_dead_letter_queue

# Or manually:
from app.tasks.error_handlers import get_dlq_stats
stats = get_dlq_stats()  # {"count": 5, "recent": [...]}
```

## Single Instance Locking

Prevents concurrent runs of the same task:

```python
from app.tasks.utils import single_instance

@shared_task(bind=True)
@single_instance("unique_lock_key", timeout=3600)  # 1 hour timeout
def my_task(self):
    # Only one instance runs at a time
    pass
```

## Testing Tasks

```python
# backend/tests/tasks/test_{feature}.py
import pytest
from app.tasks.{feature} import {feature}_task, _run_{feature}_task

@pytest.mark.asyncio
async def test_{feature}_task(db_session, test_data):
    """Test the async task implementation."""
    result = await _run_{feature}_task(batch_size=10)

    assert result["processed"] > 0
    assert result["errors"] == 0

def test_{feature}_task_sync(celery_app, db_session, test_data):
    """Test the Celery task wrapper."""
    result = {feature}_task.delay(batch_size=10)

    assert result.get(timeout=30)["processed"] > 0
```

## Manual Triggering

```bash
# Via Makefile
make trigger-{feature}

# Via Celery CLI
docker compose exec worker celery -A app.tasks.celery_app call app.tasks.{feature}.{feature}_task

# Via MCP tool
# mcp__mtg-intel__trigger_{feature}
```

## Checklist

Before committing:
- [ ] Task file created with shared_task decorator
- [ ] Async implementation with proper session handling
- [ ] single_instance decorator if needed
- [ ] Registered in celery_app.py beat_schedule
- [ ] Queue routing configured
- [ ] Tests written
- [ ] Manual trigger tested
- [ ] Run `make test-backend` to verify

## Common Patterns

### Batched Processing
```python
async def _run_task(batch_size: int):
    session_maker, engine = create_task_session_maker()
    offset = 0

    try:
        while True:
            async with session_maker() as db:
                result = await db.execute(
                    select(Model).offset(offset).limit(batch_size)
                )
                items = result.scalars().all()

                if not items:
                    break

                for item in items:
                    await process_item(db, item)

                await db.commit()
                offset += batch_size

    finally:
        await engine.dispose()
```

### With External API Calls
```python
from app.services.circuit_breaker import circuit_breaker

async def fetch_external_data(item):
    @circuit_breaker("external_api")
    async def _fetch():
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.example.com/{item.id}") as resp:
                return await resp.json()

    return await _fetch()
```

### Progress Logging
```python
async def _run_task(items):
    total = len(items)
    for i, item in enumerate(items):
        await process_item(item)

        if (i + 1) % 100 == 0:
            logger.info("task_progress",
                       processed=i+1, total=total,
                       percent=round((i+1)/total*100, 1))
```
