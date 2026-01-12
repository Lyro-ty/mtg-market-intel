"""
Celery task error handling with dead letter queue.

Failed tasks are preserved for investigation and manual retry.
"""
import json
from datetime import datetime, timezone
from typing import Any

import structlog
from celery import Task

logger = structlog.get_logger()

# Redis key for dead letter queue
DLQ_KEY = "celery:dead_letter_queue"
# Maximum number of failures to keep in the DLQ
DLQ_MAX_SIZE = 1000


class TaskWithDLQ(Task):
    """
    Base task class that sends failed tasks to dead letter queue.

    Usage:
        @celery_app.task(base=TaskWithDLQ, max_retries=3)
        def my_task():
            ...
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails after all retries."""
        from app.core.config import settings
        import redis

        logger.error(
            "Task failed permanently",
            task_id=task_id,
            task_name=self.name,
            args=args,
            kwargs=kwargs,
            error=str(exc),
        )

        # Add to dead letter queue
        try:
            r = redis.from_url(settings.redis_url)

            dlq_entry = {
                "task_id": task_id,
                "task_name": self.name,
                "args": list(args) if args else [],
                "kwargs": kwargs if kwargs else {},
                "error": str(exc),
                "traceback": str(einfo) if einfo else None,
                "failed_at": datetime.now(timezone.utc).isoformat(),
            }

            r.lpush(DLQ_KEY, json.dumps(dlq_entry))
            # Keep only the most recent failures
            r.ltrim(DLQ_KEY, 0, DLQ_MAX_SIZE - 1)

            logger.info("Task added to DLQ", task_id=task_id, task_name=self.name)

        except Exception as e:
            logger.error("Failed to add task to DLQ", error=str(e), task_id=task_id)

        super().on_failure(exc, task_id, args, kwargs, einfo)


def get_dlq_entries(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    """
    Get entries from dead letter queue.

    Args:
        limit: Maximum number of entries to return
        offset: Number of entries to skip

    Returns:
        List of DLQ entries, newest first
    """
    from app.core.config import settings
    import redis

    r = redis.from_url(settings.redis_url)
    entries = r.lrange(DLQ_KEY, offset, offset + limit - 1)
    return [json.loads(e) for e in entries]


def get_dlq_count() -> int:
    """Get the total number of entries in the DLQ."""
    from app.core.config import settings
    import redis

    r = redis.from_url(settings.redis_url)
    return r.llen(DLQ_KEY)


def retry_dlq_entry(index: int) -> bool:
    """
    Retry a specific DLQ entry by index.

    Args:
        index: Index of the entry to retry (0 = newest)

    Returns:
        True if task was resubmitted successfully, False otherwise
    """
    from app.core.config import settings
    from app.tasks.celery_app import celery_app
    import redis

    r = redis.from_url(settings.redis_url)
    entry_json = r.lindex(DLQ_KEY, index)

    if not entry_json:
        logger.warning("DLQ entry not found", index=index)
        return False

    entry = json.loads(entry_json)
    task = celery_app.tasks.get(entry["task_name"])

    if not task:
        logger.error("Task not found for DLQ retry", task_name=entry["task_name"])
        return False

    # Resubmit task
    task.apply_async(args=entry["args"], kwargs=entry["kwargs"])

    # Remove from DLQ
    r.lrem(DLQ_KEY, 1, entry_json)

    logger.info(
        "DLQ entry retried",
        task_id=entry["task_id"],
        task_name=entry["task_name"],
    )
    return True


def retry_dlq_entry_by_task_id(task_id: str) -> bool:
    """
    Retry a DLQ entry by its original task ID.

    Args:
        task_id: The original task ID to retry

    Returns:
        True if task was resubmitted successfully, False otherwise
    """
    from app.core.config import settings
    from app.tasks.celery_app import celery_app
    import redis

    r = redis.from_url(settings.redis_url)
    entries = r.lrange(DLQ_KEY, 0, DLQ_MAX_SIZE - 1)

    for entry_json in entries:
        entry = json.loads(entry_json)
        if entry.get("task_id") == task_id:
            task = celery_app.tasks.get(entry["task_name"])
            if not task:
                logger.error("Task not found for DLQ retry", task_name=entry["task_name"])
                return False

            # Resubmit task
            task.apply_async(args=entry["args"], kwargs=entry["kwargs"])

            # Remove from DLQ
            r.lrem(DLQ_KEY, 1, entry_json)

            logger.info(
                "DLQ entry retried by task_id",
                task_id=task_id,
                task_name=entry["task_name"],
            )
            return True

    logger.warning("DLQ entry not found by task_id", task_id=task_id)
    return False


def clear_dlq() -> int:
    """
    Clear all entries from DLQ.

    Returns:
        Number of removed entries
    """
    from app.core.config import settings
    import redis

    r = redis.from_url(settings.redis_url)
    count = r.llen(DLQ_KEY)
    r.delete(DLQ_KEY)

    logger.info("DLQ cleared", count=count)
    return count


def remove_dlq_entry(index: int) -> bool:
    """
    Remove a DLQ entry without retrying it.

    Args:
        index: Index of the entry to remove (0 = newest)

    Returns:
        True if entry was removed, False otherwise
    """
    from app.core.config import settings
    import redis

    r = redis.from_url(settings.redis_url)
    entry_json = r.lindex(DLQ_KEY, index)

    if not entry_json:
        logger.warning("DLQ entry not found for removal", index=index)
        return False

    r.lrem(DLQ_KEY, 1, entry_json)

    entry = json.loads(entry_json)
    logger.info(
        "DLQ entry removed",
        task_id=entry.get("task_id"),
        task_name=entry.get("task_name"),
    )
    return True
