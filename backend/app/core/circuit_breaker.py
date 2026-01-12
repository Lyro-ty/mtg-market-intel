"""
Circuit breaker pattern for external service calls.

Prevents cascading failures by failing fast when a service
is unhealthy, with automatic recovery attempts.
"""
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import structlog

logger = structlog.get_logger()


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for external service calls.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service unhealthy, fail fast without calling
    - HALF_OPEN: Testing if service recovered

    Usage:
        breaker = CircuitBreaker(name="tcgplayer")

        async with breaker:
            result = await external_api_call()
    """
    name: str
    failure_threshold: int = 5       # Failures before opening
    recovery_timeout: float = 30.0   # Seconds before trying half-open
    half_open_requests: int = 3      # Successful requests to close

    # State
    state: CircuitState = field(default=CircuitState.CLOSED)
    failure_count: int = field(default=0)
    success_count: int = field(default=0)
    last_failure_time: Optional[float] = field(default=None)

    async def __aenter__(self):
        if self.state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info(f"Circuit {self.name} entering half-open state")
            else:
                raise CircuitOpenError(
                    f"Circuit {self.name} is open. "
                    f"Retry after {self._time_until_recovery():.1f}s"
                )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._record_failure()
        else:
            self._record_success()
        return False  # Don't suppress exceptions

    def _should_attempt_recovery(self) -> bool:
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _time_until_recovery(self) -> float:
        if self.last_failure_time is None:
            return 0
        elapsed = time.time() - self.last_failure_time
        return max(0, self.recovery_timeout - elapsed)

    def _record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit {self.name} reopened after half-open failure")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit {self.name} opened after {self.failure_count} failures"
            )

    def _record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_requests:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info(f"Circuit {self.name} closed after successful recovery")
        else:
            self.failure_count = 0

    def reset(self):
        """Manually reset the circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        logger.info(f"Circuit {self.name} manually reset")


class CircuitOpenError(Exception):
    """Raised when circuit is open and request should fail fast."""
    pass


# Global circuit breakers for external services
_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name=name, **kwargs)
    return _breakers[name]


def reset_all_breakers():
    """Reset all circuit breakers. Useful for testing."""
    for breaker in _breakers.values():
        breaker.reset()


def clear_all_breakers():
    """Clear all circuit breakers from the registry. Useful for testing."""
    _breakers.clear()
