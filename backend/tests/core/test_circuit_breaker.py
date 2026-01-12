"""Tests for circuit breaker pattern implementation."""
import time

import pytest

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    clear_all_breakers,
    get_circuit_breaker,
    reset_all_breakers,
)


@pytest.fixture(autouse=True)
def cleanup_breakers():
    """Clean up circuit breakers before and after each test."""
    clear_all_breakers()
    yield
    clear_all_breakers()


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    @pytest.mark.asyncio
    async def test_closed_state_allows_requests(self):
        """Circuit in CLOSED state allows requests through."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        async with breaker:
            pass  # Simulates successful request

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_failure_increments_count(self):
        """Failures increment the failure counter."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("Test error")

        assert breaker.failure_count == 1
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self):
        """Circuit opens after reaching failure threshold."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        # Cause 3 failures
        for _ in range(3):
            with pytest.raises(ValueError):
                async with breaker:
                    raise ValueError("Test error")

        assert breaker.failure_count == 3
        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_circuit_fails_fast(self):
        """Open circuit raises CircuitOpenError immediately."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=60.0,  # Long timeout to ensure it stays open
        )

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                async with breaker:
                    raise ValueError("Test error")

        assert breaker.state == CircuitState.OPEN

        # Next request should fail fast
        with pytest.raises(CircuitOpenError) as exc_info:
            async with breaker:
                pass  # Should not reach here

        assert "Circuit test is open" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_circuit_enters_half_open_after_timeout(self):
        """Circuit enters HALF_OPEN state after recovery timeout."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=0.1,  # 100ms for fast test
        )

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                async with breaker:
                    raise ValueError("Test error")

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Next request should enter half-open
        async with breaker:
            pass  # Successful request in half-open

        assert breaker.state == CircuitState.HALF_OPEN or breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(self):
        """Successful requests in HALF_OPEN close the circuit."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=0.05,
            half_open_requests=2,
        )

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                async with breaker:
                    raise ValueError("Test error")

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.1)

        # Make enough successful requests to close circuit
        for _ in range(2):
            async with breaker:
                pass

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self):
        """Failure in HALF_OPEN reopens the circuit."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=0.05,
            half_open_requests=3,
        )

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                async with breaker:
                    raise ValueError("Test error")

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.1)

        # Enter half-open with successful request
        async with breaker:
            pass

        assert breaker.state == CircuitState.HALF_OPEN

        # Fail in half-open - should reopen
        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("Failure in half-open")

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self):
        """Successful request in CLOSED state resets failure count."""
        breaker = CircuitBreaker(name="test", failure_threshold=5)

        # Cause some failures (but not enough to open)
        for _ in range(3):
            with pytest.raises(ValueError):
                async with breaker:
                    raise ValueError("Test error")

        assert breaker.failure_count == 3
        assert breaker.state == CircuitState.CLOSED

        # Successful request resets count
        async with breaker:
            pass

        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    def test_reset_manually(self):
        """Manual reset returns circuit to CLOSED state."""
        breaker = CircuitBreaker(name="test", failure_threshold=2)
        breaker.state = CircuitState.OPEN
        breaker.failure_count = 5
        breaker.last_failure_time = time.time()

        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 0
        assert breaker.last_failure_time is None


class TestCircuitBreakerRegistry:
    """Tests for circuit breaker registry functions."""

    def test_get_circuit_breaker_creates_new(self):
        """get_circuit_breaker creates new breaker if not exists."""
        breaker = get_circuit_breaker("new_service")

        assert breaker.name == "new_service"
        assert breaker.state == CircuitState.CLOSED

    def test_get_circuit_breaker_returns_existing(self):
        """get_circuit_breaker returns existing breaker."""
        breaker1 = get_circuit_breaker("same_service")
        breaker2 = get_circuit_breaker("same_service")

        assert breaker1 is breaker2

    def test_get_circuit_breaker_with_custom_config(self):
        """get_circuit_breaker uses custom configuration."""
        breaker = get_circuit_breaker(
            "custom_service",
            failure_threshold=10,
            recovery_timeout=120.0,
            half_open_requests=5,
        )

        assert breaker.failure_threshold == 10
        assert breaker.recovery_timeout == 120.0
        assert breaker.half_open_requests == 5

    def test_reset_all_breakers(self):
        """reset_all_breakers resets all registered breakers."""
        breaker1 = get_circuit_breaker("service1")
        breaker2 = get_circuit_breaker("service2")

        # Modify states
        breaker1.state = CircuitState.OPEN
        breaker1.failure_count = 5
        breaker2.state = CircuitState.HALF_OPEN
        breaker2.failure_count = 3

        reset_all_breakers()

        assert breaker1.state == CircuitState.CLOSED
        assert breaker1.failure_count == 0
        assert breaker2.state == CircuitState.CLOSED
        assert breaker2.failure_count == 0

    def test_clear_all_breakers(self):
        """clear_all_breakers removes all registered breakers."""
        breaker1 = get_circuit_breaker("service1")
        get_circuit_breaker("service2")

        clear_all_breakers()

        # Getting same name should create new instance
        breaker3 = get_circuit_breaker("service1")
        assert breaker3 is not breaker1


class TestCircuitBreakerTiming:
    """Tests for circuit breaker timing behavior."""

    def test_time_until_recovery(self):
        """_time_until_recovery returns correct remaining time."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=1,
            recovery_timeout=10.0,
        )

        breaker.last_failure_time = time.time()

        remaining = breaker._time_until_recovery()
        assert 9.0 < remaining <= 10.0

    def test_time_until_recovery_no_failure(self):
        """_time_until_recovery returns 0 when no failure recorded."""
        breaker = CircuitBreaker(name="test")

        assert breaker._time_until_recovery() == 0

    def test_should_attempt_recovery_false_before_timeout(self):
        """_should_attempt_recovery returns False before timeout."""
        breaker = CircuitBreaker(
            name="test",
            recovery_timeout=60.0,
        )
        breaker.last_failure_time = time.time()

        assert breaker._should_attempt_recovery() is False

    def test_should_attempt_recovery_true_after_timeout(self):
        """_should_attempt_recovery returns True after timeout."""
        breaker = CircuitBreaker(
            name="test",
            recovery_timeout=0.01,  # 10ms
        )
        breaker.last_failure_time = time.time()

        time.sleep(0.02)

        assert breaker._should_attempt_recovery() is True

    def test_should_attempt_recovery_true_no_failure(self):
        """_should_attempt_recovery returns True when no failure time."""
        breaker = CircuitBreaker(name="test")

        assert breaker._should_attempt_recovery() is True
