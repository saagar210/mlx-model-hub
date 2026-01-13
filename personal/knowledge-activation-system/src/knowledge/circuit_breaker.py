"""Circuit Breaker Pattern (P26: Reliability)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Callable, TypeVar, Generic, Any

from knowledge.config import get_settings
from knowledge.exceptions import CircuitOpenError
from knowledge.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening
    recovery_timeout: float = 30.0  # Seconds before half-open
    half_open_max_calls: int = 3  # Successful calls to close

    @classmethod
    def from_settings(cls) -> "CircuitBreakerConfig":
        """Create config from application settings."""
        settings = get_settings()
        return cls(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_timeout=settings.circuit_breaker_recovery_timeout,
            half_open_max_calls=settings.circuit_breaker_half_open_max_calls,
        )


@dataclass
class CircuitStats:
    """Statistics for a circuit breaker."""

    name: str
    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: float | None
    last_success_time: float | None


class CircuitBreaker(Generic[T]):
    """
    Circuit breaker for protecting calls to external services.

    States:
    - CLOSED: Normal operation. Failures increment counter.
    - OPEN: All calls rejected. Waiting for recovery timeout.
    - HALF_OPEN: Testing recovery. Success closes circuit, failure reopens.

    Usage:
        cb = CircuitBreaker("ollama")

        try:
            result = await cb.call(async_function, arg1, arg2)
        except CircuitOpenError:
            # Circuit is open, use fallback
            result = default_value
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
        fallback: Callable[..., T] | None = None,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Circuit name for logging/metrics
            config: Configuration (uses defaults if None)
            fallback: Optional fallback function when circuit is open
        """
        self.name = name
        self.config = config or CircuitBreakerConfig.from_settings()
        self.fallback = fallback

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: float | None = None
        self._last_success_time: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing)."""
        return self._state == CircuitState.OPEN

    def get_stats(self) -> CircuitStats:
        """Get circuit statistics."""
        return CircuitStats(
            name=self.name,
            state=self._state,
            failure_count=self._failure_count,
            success_count=self._success_count,
            last_failure_time=self._last_failure_time,
            last_success_time=self._last_success_time,
        )

    async def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Async function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func or fallback

        Raises:
            CircuitOpenError: If circuit is open and no fallback
            Exception: If func raises and not caught
        """
        # Check circuit state
        async with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if we should try half-open
                if self._last_failure_time and (
                    time() - self._last_failure_time > self.config.recovery_timeout
                ):
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info(
                        "circuit_half_open",
                        circuit=self.name,
                        recovery_timeout=self.config.recovery_timeout,
                    )
                else:
                    # Circuit still open
                    logger.debug(
                        "circuit_rejected",
                        circuit=self.name,
                    )
                    if self.fallback:
                        return await self._call_fallback(*args, **kwargs)
                    raise CircuitOpenError(self.name)

        # Execute the call
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure(e)
            raise

    async def _call_fallback(self, *args: Any, **kwargs: Any) -> T:
        """Call the fallback function."""
        if asyncio.iscoroutinefunction(self.fallback):
            return await self.fallback(*args, **kwargs)
        return self.fallback(*args, **kwargs)  # type: ignore

    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            self._success_count += 1
            self._last_success_time = time()

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self.config.half_open_max_calls:
                    # Enough successes, close the circuit
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info(
                        "circuit_closed",
                        circuit=self.name,
                        success_count=self._half_open_calls,
                    )
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success in closed state
                self._failure_count = 0

    async def _on_failure(self, error: Exception) -> None:
        """Handle failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time()

            logger.warning(
                "circuit_failure",
                circuit=self.name,
                failure_count=self._failure_count,
                threshold=self.config.failure_threshold,
                error=str(error),
            )

            if self._state == CircuitState.HALF_OPEN:
                # Failure during half-open reopens circuit
                self._state = CircuitState.OPEN
                logger.warning(
                    "circuit_reopened",
                    circuit=self.name,
                )
            elif self._state == CircuitState.CLOSED:
                # Check if we should open
                if self._failure_count >= self.config.failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.error(
                        "circuit_opened",
                        circuit=self.name,
                        failure_count=self._failure_count,
                    )

    def reset(self) -> None:
        """Reset circuit to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
        logger.info("circuit_reset", circuit=self.name)


# =============================================================================
# Global Circuit Breakers
# =============================================================================


# Circuit breakers for external services
_circuits: dict[str, CircuitBreaker] = {}
_circuits_lock = asyncio.Lock()


async def get_circuit(
    name: str,
    config: CircuitBreakerConfig | None = None,
    fallback: Callable | None = None,
) -> CircuitBreaker:
    """
    Get or create a circuit breaker.

    Args:
        name: Circuit name
        config: Optional configuration
        fallback: Optional fallback function

    Returns:
        CircuitBreaker instance
    """
    async with _circuits_lock:
        if name not in _circuits:
            _circuits[name] = CircuitBreaker(name, config, fallback)
        return _circuits[name]


def get_all_circuits() -> dict[str, CircuitStats]:
    """Get stats for all circuits."""
    return {name: cb.get_stats() for name, cb in _circuits.items()}


async def reset_all_circuits() -> None:
    """Reset all circuits to closed state."""
    async with _circuits_lock:
        for cb in _circuits.values():
            cb.reset()
