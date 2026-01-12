"""
Tests for Celery task backpressure utilities.

Tests the single_instance decorator and queue depth checking.
"""
import pytest
from unittest.mock import MagicMock, patch

from app.tasks.utils import single_instance, check_queue_depth


def test_single_instance_blocks_concurrent():
    """Second call should be skipped while first is running."""
    mock_redis = MagicMock()
    mock_redis.set.side_effect = [True, False]  # First succeeds, second fails

    @single_instance("test_lock", redis_url="redis://fake")
    def my_task():
        return "executed"

    with patch("redis.Redis.from_url", return_value=mock_redis):
        result1 = my_task()
        result2 = my_task()

    assert result1 == "executed"
    assert result2["status"] == "skipped"


def test_single_instance_releases_lock():
    """Lock should be released after task completes."""
    mock_redis = MagicMock()
    mock_redis.set.return_value = True

    @single_instance("test_lock", redis_url="redis://fake")
    def my_task():
        return "done"

    with patch("redis.Redis.from_url", return_value=mock_redis):
        my_task()

    mock_redis.delete.assert_called_once_with("celery_lock:test_lock")


def test_single_instance_releases_lock_on_exception():
    """Lock should be released even if task raises an exception."""
    mock_redis = MagicMock()
    mock_redis.set.return_value = True

    @single_instance("test_lock", redis_url="redis://fake")
    def my_task():
        raise ValueError("Task failed!")

    with patch("redis.Redis.from_url", return_value=mock_redis):
        with pytest.raises(ValueError, match="Task failed!"):
            my_task()

    # Lock should still be released
    mock_redis.delete.assert_called_once_with("celery_lock:test_lock")


def test_single_instance_uses_custom_timeout():
    """Custom timeout should be passed to Redis set command."""
    mock_redis = MagicMock()
    mock_redis.set.return_value = True

    @single_instance("test_lock", timeout=600, redis_url="redis://fake")
    def my_task():
        return "done"

    with patch("redis.Redis.from_url", return_value=mock_redis):
        my_task()

    # Verify timeout was passed correctly
    mock_redis.set.assert_called_once_with(
        "celery_lock:test_lock", "1", nx=True, ex=600
    )


def test_single_instance_skipped_result_format():
    """Skipped tasks should return a consistent result format."""
    mock_redis = MagicMock()
    mock_redis.set.return_value = False  # Lock not acquired

    @single_instance("test_lock", redis_url="redis://fake")
    def my_task():
        return "executed"

    with patch("redis.Redis.from_url", return_value=mock_redis):
        result = my_task()

    assert result == {"status": "skipped", "reason": "previous_running"}


def test_check_queue_depth_acceptable():
    """Should return True when queue depth is below max."""
    mock_redis = MagicMock()
    mock_redis.llen.return_value = 50

    with patch("redis.Redis.from_url", return_value=mock_redis):
        result = check_queue_depth("test_queue", max_depth=100)

    assert result is True
    mock_redis.llen.assert_called_once_with("test_queue")


def test_check_queue_depth_exceeded():
    """Should return False when queue depth exceeds max."""
    mock_redis = MagicMock()
    mock_redis.llen.return_value = 150

    with patch("redis.Redis.from_url", return_value=mock_redis):
        result = check_queue_depth("test_queue", max_depth=100)

    assert result is False


def test_check_queue_depth_at_limit():
    """Should return True when queue depth is exactly at max."""
    mock_redis = MagicMock()
    mock_redis.llen.return_value = 100

    with patch("redis.Redis.from_url", return_value=mock_redis):
        result = check_queue_depth("test_queue", max_depth=100)

    assert result is True


def test_check_queue_depth_empty():
    """Should return True when queue is empty."""
    mock_redis = MagicMock()
    mock_redis.llen.return_value = 0

    with patch("redis.Redis.from_url", return_value=mock_redis):
        result = check_queue_depth("test_queue", max_depth=100)

    assert result is True


def test_single_instance_preserves_function_name():
    """Decorator should preserve the original function's name."""
    @single_instance("test_lock", redis_url="redis://fake")
    def my_custom_task():
        return "done"

    assert my_custom_task.__name__ == "my_custom_task"
