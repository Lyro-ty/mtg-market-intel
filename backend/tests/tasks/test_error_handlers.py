"""
Tests for Celery task error handlers and dead letter queue.

Tests verify:
- TaskWithDLQ adds failed tasks to DLQ
- get_dlq_entries retrieves entries
- retry_dlq_entry resubmits and removes from queue
- DLQ is limited to max size
"""
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


class TestTaskWithDLQ:
    """Tests for the TaskWithDLQ base class."""

    def test_task_with_dlq_adds_failed_task_to_dlq(self):
        """Verify TaskWithDLQ.on_failure adds entry to Redis DLQ."""
        from app.tasks.error_handlers import TaskWithDLQ, DLQ_KEY

        # Create a mock task instance
        task = TaskWithDLQ()
        task.name = "test_task"

        # Mock Redis
        mock_redis_instance = MagicMock()

        with patch("redis.from_url", return_value=mock_redis_instance):
            # Call on_failure
            task.on_failure(
                exc=ValueError("Test error"),
                task_id="test-task-id-123",
                args=("arg1", "arg2"),
                kwargs={"key1": "value1"},
                einfo=MagicMock(__str__=lambda self: "Traceback info"),
            )

        # Verify lpush was called with correct key
        mock_redis_instance.lpush.assert_called_once()
        call_args = mock_redis_instance.lpush.call_args
        assert call_args[0][0] == DLQ_KEY

        # Verify the entry contents
        entry = json.loads(call_args[0][1])
        assert entry["task_id"] == "test-task-id-123"
        assert entry["task_name"] == "test_task"
        assert entry["args"] == ["arg1", "arg2"]
        assert entry["kwargs"] == {"key1": "value1"}
        assert entry["error"] == "Test error"
        assert "failed_at" in entry

        # Verify ltrim was called to limit size
        mock_redis_instance.ltrim.assert_called_once()

    def test_task_with_dlq_handles_empty_args(self):
        """Verify TaskWithDLQ handles tasks with no args/kwargs."""
        from app.tasks.error_handlers import TaskWithDLQ

        task = TaskWithDLQ()
        task.name = "test_task_no_args"

        mock_redis_instance = MagicMock()

        with patch("redis.from_url", return_value=mock_redis_instance):
            task.on_failure(
                exc=RuntimeError("No args error"),
                task_id="test-no-args-id",
                args=None,
                kwargs=None,
                einfo=None,
            )

        call_args = mock_redis_instance.lpush.call_args
        entry = json.loads(call_args[0][1])
        assert entry["args"] == []
        assert entry["kwargs"] == {}
        assert entry["traceback"] is None

    def test_task_with_dlq_handles_redis_error_gracefully(self):
        """Verify TaskWithDLQ handles Redis errors without raising."""
        from app.tasks.error_handlers import TaskWithDLQ

        task = TaskWithDLQ()
        task.name = "test_task"

        # Should not raise exception when Redis fails
        with patch("redis.from_url", side_effect=Exception("Redis connection failed")):
            task.on_failure(
                exc=ValueError("Test error"),
                task_id="test-task-id",
                args=(),
                kwargs={},
                einfo=None,
            )


class TestGetDLQEntries:
    """Tests for get_dlq_entries function."""

    def test_get_dlq_entries_returns_parsed_json(self):
        """Verify get_dlq_entries returns parsed JSON entries."""
        from app.tasks.error_handlers import get_dlq_entries, DLQ_KEY

        mock_entries = [
            json.dumps({"task_id": "1", "task_name": "task1"}).encode(),
            json.dumps({"task_id": "2", "task_name": "task2"}).encode(),
        ]

        mock_redis_instance = MagicMock()
        mock_redis_instance.lrange.return_value = mock_entries

        with patch("redis.from_url", return_value=mock_redis_instance):
            entries = get_dlq_entries(limit=10)

        assert len(entries) == 2
        assert entries[0]["task_id"] == "1"
        assert entries[1]["task_id"] == "2"

        mock_redis_instance.lrange.assert_called_once_with(DLQ_KEY, 0, 9)

    def test_get_dlq_entries_respects_offset(self):
        """Verify get_dlq_entries applies offset correctly."""
        from app.tasks.error_handlers import get_dlq_entries, DLQ_KEY

        mock_redis_instance = MagicMock()
        mock_redis_instance.lrange.return_value = []

        with patch("redis.from_url", return_value=mock_redis_instance):
            get_dlq_entries(limit=10, offset=5)

        mock_redis_instance.lrange.assert_called_once_with(DLQ_KEY, 5, 14)

    def test_get_dlq_entries_returns_empty_list_when_no_entries(self):
        """Verify get_dlq_entries returns empty list when DLQ is empty."""
        from app.tasks.error_handlers import get_dlq_entries

        mock_redis_instance = MagicMock()
        mock_redis_instance.lrange.return_value = []

        with patch("redis.from_url", return_value=mock_redis_instance):
            entries = get_dlq_entries()

        assert entries == []


class TestGetDLQCount:
    """Tests for get_dlq_count function."""

    def test_get_dlq_count_returns_queue_length(self):
        """Verify get_dlq_count returns correct count."""
        from app.tasks.error_handlers import get_dlq_count, DLQ_KEY

        mock_redis_instance = MagicMock()
        mock_redis_instance.llen.return_value = 42

        with patch("redis.from_url", return_value=mock_redis_instance):
            count = get_dlq_count()

        assert count == 42
        mock_redis_instance.llen.assert_called_once_with(DLQ_KEY)


class TestRetryDLQEntry:
    """Tests for retry_dlq_entry function."""

    def test_retry_dlq_entry_resubmits_and_removes(self):
        """Verify retry_dlq_entry resubmits task and removes from DLQ."""
        from app.tasks.error_handlers import retry_dlq_entry

        entry = {
            "task_id": "original-task-id",
            "task_name": "app.tasks.test.test_task",
            "args": ["arg1"],
            "kwargs": {"key": "value"},
        }
        entry_json = json.dumps(entry)

        mock_redis_instance = MagicMock()
        mock_redis_instance.lindex.return_value = entry_json.encode()

        mock_task = MagicMock()
        mock_celery = MagicMock()
        mock_celery.tasks.get.return_value = mock_task

        with patch("redis.from_url", return_value=mock_redis_instance):
            with patch("app.tasks.celery_app.celery_app", mock_celery):
                result = retry_dlq_entry(0)

        assert result is True

        # Verify task was resubmitted
        mock_task.apply_async.assert_called_once_with(
            args=["arg1"], kwargs={"key": "value"}
        )

        # Verify entry was removed from DLQ
        mock_redis_instance.lrem.assert_called_once()

    def test_retry_dlq_entry_returns_false_for_missing_entry(self):
        """Verify retry_dlq_entry returns False when entry not found."""
        from app.tasks.error_handlers import retry_dlq_entry

        mock_redis_instance = MagicMock()
        mock_redis_instance.lindex.return_value = None

        with patch("redis.from_url", return_value=mock_redis_instance):
            result = retry_dlq_entry(999)

        assert result is False

    def test_retry_dlq_entry_returns_false_for_unknown_task(self):
        """Verify retry_dlq_entry returns False when task not registered."""
        from app.tasks.error_handlers import retry_dlq_entry

        entry = {
            "task_id": "task-id",
            "task_name": "unknown.task",
            "args": [],
            "kwargs": {},
        }

        mock_redis_instance = MagicMock()
        mock_redis_instance.lindex.return_value = json.dumps(entry).encode()

        mock_celery = MagicMock()
        mock_celery.tasks.get.return_value = None

        with patch("redis.from_url", return_value=mock_redis_instance):
            with patch("app.tasks.celery_app.celery_app", mock_celery):
                result = retry_dlq_entry(0)

        assert result is False


class TestRetryDLQEntryByTaskId:
    """Tests for retry_dlq_entry_by_task_id function."""

    def test_retry_by_task_id_finds_and_resubmits(self):
        """Verify retry_dlq_entry_by_task_id finds entry and resubmits."""
        from app.tasks.error_handlers import retry_dlq_entry_by_task_id

        entries = [
            json.dumps({"task_id": "other-id", "task_name": "task1", "args": [], "kwargs": {}}).encode(),
            json.dumps({"task_id": "target-id", "task_name": "task2", "args": ["a"], "kwargs": {}}).encode(),
        ]

        mock_redis_instance = MagicMock()
        mock_redis_instance.lrange.return_value = entries

        mock_task = MagicMock()
        mock_celery = MagicMock()
        mock_celery.tasks.get.return_value = mock_task

        with patch("redis.from_url", return_value=mock_redis_instance):
            with patch("app.tasks.celery_app.celery_app", mock_celery):
                result = retry_dlq_entry_by_task_id("target-id")

        assert result is True
        mock_task.apply_async.assert_called_once_with(args=["a"], kwargs={})

    def test_retry_by_task_id_returns_false_when_not_found(self):
        """Verify retry_dlq_entry_by_task_id returns False when not found."""
        from app.tasks.error_handlers import retry_dlq_entry_by_task_id

        mock_redis_instance = MagicMock()
        mock_redis_instance.lrange.return_value = []

        with patch("redis.from_url", return_value=mock_redis_instance):
            result = retry_dlq_entry_by_task_id("nonexistent-id")

        assert result is False


class TestClearDLQ:
    """Tests for clear_dlq function."""

    def test_clear_dlq_removes_all_entries(self):
        """Verify clear_dlq removes all entries and returns count."""
        from app.tasks.error_handlers import clear_dlq, DLQ_KEY

        mock_redis_instance = MagicMock()
        mock_redis_instance.llen.return_value = 5

        with patch("redis.from_url", return_value=mock_redis_instance):
            count = clear_dlq()

        assert count == 5
        mock_redis_instance.delete.assert_called_once_with(DLQ_KEY)


class TestRemoveDLQEntry:
    """Tests for remove_dlq_entry function."""

    def test_remove_dlq_entry_removes_without_retry(self):
        """Verify remove_dlq_entry removes entry without resubmitting."""
        from app.tasks.error_handlers import remove_dlq_entry

        entry = {"task_id": "task-id", "task_name": "task"}
        entry_json = json.dumps(entry)

        mock_redis_instance = MagicMock()
        mock_redis_instance.lindex.return_value = entry_json.encode()

        with patch("redis.from_url", return_value=mock_redis_instance):
            result = remove_dlq_entry(0)

        assert result is True
        mock_redis_instance.lrem.assert_called_once()

    def test_remove_dlq_entry_returns_false_when_not_found(self):
        """Verify remove_dlq_entry returns False when entry not found."""
        from app.tasks.error_handlers import remove_dlq_entry

        mock_redis_instance = MagicMock()
        mock_redis_instance.lindex.return_value = None

        with patch("redis.from_url", return_value=mock_redis_instance):
            result = remove_dlq_entry(999)

        assert result is False


class TestDLQMaxSize:
    """Tests for DLQ size limiting."""

    def test_dlq_ltrim_limits_to_max_size(self):
        """Verify DLQ is trimmed to max size after adding entry."""
        from app.tasks.error_handlers import TaskWithDLQ, DLQ_MAX_SIZE

        task = TaskWithDLQ()
        task.name = "test_task"

        mock_redis_instance = MagicMock()

        with patch("redis.from_url", return_value=mock_redis_instance):
            task.on_failure(
                exc=ValueError("Error"),
                task_id="task-id",
                args=(),
                kwargs={},
                einfo=None,
            )

        # Verify ltrim was called with correct bounds (0 to max_size - 1)
        mock_redis_instance.ltrim.assert_called_once()
        ltrim_args = mock_redis_instance.ltrim.call_args[0]
        assert ltrim_args[1] == 0
        assert ltrim_args[2] == DLQ_MAX_SIZE - 1


class TestCeleryAppConfiguration:
    """Tests for Celery app configuration with TaskWithDLQ."""

    def test_celery_app_uses_task_with_dlq(self):
        """Verify Celery app is configured with TaskWithDLQ as base."""
        from app.tasks.celery_app import celery_app
        from app.tasks.error_handlers import TaskWithDLQ

        # Check the task_cls configuration
        assert celery_app.conf.task_cls == TaskWithDLQ

    def test_error_handlers_module_included(self):
        """Verify error_handlers can be imported without circular imports."""
        # This test will fail at import time if there are circular import issues
        from app.tasks.error_handlers import (
            TaskWithDLQ,
            DLQ_KEY,
            get_dlq_entries,
            get_dlq_count,
            retry_dlq_entry,
            retry_dlq_entry_by_task_id,
            clear_dlq,
            remove_dlq_entry,
        )

        assert TaskWithDLQ is not None
        assert DLQ_KEY == "celery:dead_letter_queue"
        assert callable(get_dlq_entries)
        assert callable(get_dlq_count)
        assert callable(retry_dlq_entry)
        assert callable(retry_dlq_entry_by_task_id)
        assert callable(clear_dlq)
        assert callable(remove_dlq_entry)
