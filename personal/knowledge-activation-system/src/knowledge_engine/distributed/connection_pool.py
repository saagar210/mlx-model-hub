"""Advanced connection pooling with health checks and circuit breakers."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class PoolState(str, Enum):
    """Connection pool states."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CLOSED = "closed"


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class PoolConfig:
    """Configuration for connection pool."""

    min_size: int = 5
    max_size: int = 20
    max_idle_time: float = 300.0  # seconds
    max_lifetime: float = 3600.0  # seconds
    acquire_timeout: float = 10.0  # seconds
    health_check_interval: float = 30.0  # seconds
    retry_attempts: int = 3
    retry_delay: float = 1.0  # seconds

    # Circuit breaker settings
    circuit_failure_threshold: int = 5
    circuit_recovery_timeout: float = 30.0  # seconds
    circuit_half_open_max_calls: int = 3


@dataclass
class PoolMetrics:
    """Metrics for connection pool monitoring."""

    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    pending_requests: int = 0
    total_acquired: int = 0
    total_released: int = 0
    total_timeouts: int = 0
    total_errors: int = 0
    avg_acquire_time_ms: float = 0.0
    pool_state: PoolState = PoolState.HEALTHY
    circuit_state: CircuitState = CircuitState.CLOSED


@dataclass
class PooledConnection(Generic[T]):
    """A connection wrapper with metadata."""

    connection: T
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    use_count: int = 0
    is_healthy: bool = True

    @property
    def age(self) -> float:
        return time.time() - self.created_at

    @property
    def idle_time(self) -> float:
        return time.time() - self.last_used_at


class CircuitBreaker:
    """Circuit breaker for connection failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def can_proceed(self) -> bool:
        """Check if request can proceed."""
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                if self._should_attempt_recovery():
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    return True
                return False

            # Half-open state
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

    async def record_success(self) -> None:
        """Record successful operation."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self.half_open_max_calls:
                    self._reset()
            elif self._state == CircuitState.CLOSED:
                self._failure_count = max(0, self._failure_count - 1)

    async def record_failure(self) -> None:
        """Record failed operation."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker opened after {self._failure_count} failures"
                )

    def _should_attempt_recovery(self) -> bool:
        if self._last_failure_time is None:
            return True
        return time.time() - self._last_failure_time >= self.recovery_timeout

    def _reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
        logger.info("Circuit breaker reset to closed state")


class ConnectionPool(Generic[T]):
    """
    Advanced async connection pool with health checks and circuit breaker.

    Features:
    - Automatic connection lifecycle management
    - Health checks with automatic connection replacement
    - Circuit breaker pattern for failure handling
    - Connection warmup and graceful shutdown
    - Comprehensive metrics
    """

    def __init__(
        self,
        factory: Callable[[], Any],
        config: PoolConfig | None = None,
        validator: Callable[[T], Any] | None = None,
        disposer: Callable[[T], Any] | None = None,
    ):
        """
        Initialize connection pool.

        Args:
            factory: Async function to create connections
            config: Pool configuration
            validator: Async function to validate connection health
            disposer: Async function to dispose of connections
        """
        self.factory = factory
        self.config = config or PoolConfig()
        self.validator = validator
        self.disposer = disposer

        self._pool: asyncio.Queue[PooledConnection[T]] = asyncio.Queue(
            maxsize=self.config.max_size
        )
        self._all_connections: set[PooledConnection[T]] = set()
        self._metrics = PoolMetrics()
        self._lock = asyncio.Lock()
        self._closed = False

        self._circuit_breaker = CircuitBreaker(
            failure_threshold=self.config.circuit_failure_threshold,
            recovery_timeout=self.config.circuit_recovery_timeout,
            half_open_max_calls=self.config.circuit_half_open_max_calls,
        )

        self._health_check_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the pool and warm up connections."""
        logger.info(f"Starting connection pool (min={self.config.min_size})")

        # Create minimum connections
        for _ in range(self.config.min_size):
            try:
                conn = await self._create_connection()
                await self._pool.put(conn)
            except Exception as e:
                logger.warning(f"Failed to create initial connection: {e}")

        # Start health check task
        self._health_check_task = asyncio.create_task(self._health_check_loop())

        self._update_metrics()
        logger.info(
            f"Connection pool started with {self._pool.qsize()} connections"
        )

    async def close(self) -> None:
        """Gracefully close the pool."""
        self._closed = True
        self._metrics.pool_state = PoolState.CLOSED

        # Stop health check
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        async with self._lock:
            for pooled_conn in list(self._all_connections):
                await self._dispose_connection(pooled_conn)

        logger.info("Connection pool closed")

    async def acquire(self) -> T:
        """
        Acquire a connection from the pool.

        Returns:
            A connection from the pool

        Raises:
            RuntimeError: If pool is closed
            TimeoutError: If acquire times out
        """
        if self._closed:
            raise RuntimeError("Pool is closed")

        # Check circuit breaker
        if not await self._circuit_breaker.can_proceed():
            self._metrics.total_errors += 1
            raise RuntimeError("Circuit breaker is open")

        start_time = time.time()
        self._metrics.pending_requests += 1

        try:
            # Try to get existing connection
            try:
                pooled_conn = await asyncio.wait_for(
                    self._pool.get(),
                    timeout=self.config.acquire_timeout,
                )
            except asyncio.TimeoutError:
                # Try to create new connection if under max
                async with self._lock:
                    if len(self._all_connections) < self.config.max_size:
                        pooled_conn = await self._create_connection()
                    else:
                        self._metrics.total_timeouts += 1
                        raise TimeoutError("Connection acquire timeout")

            # Validate connection
            if not await self._validate_connection(pooled_conn):
                await self._dispose_connection(pooled_conn)
                pooled_conn = await self._create_connection()

            # Update connection metadata
            pooled_conn.last_used_at = time.time()
            pooled_conn.use_count += 1

            # Update metrics
            self._metrics.total_acquired += 1
            elapsed = (time.time() - start_time) * 1000
            self._metrics.avg_acquire_time_ms = (
                self._metrics.avg_acquire_time_ms * 0.9 + elapsed * 0.1
            )

            await self._circuit_breaker.record_success()
            self._update_metrics()

            return pooled_conn.connection

        except Exception as e:
            await self._circuit_breaker.record_failure()
            self._metrics.total_errors += 1
            raise
        finally:
            self._metrics.pending_requests -= 1

    async def release(self, connection: T) -> None:
        """Release a connection back to the pool."""
        if self._closed:
            return

        # Find the pooled connection
        pooled_conn: PooledConnection[T] | None = None
        for pc in self._all_connections:
            if pc.connection is connection:
                pooled_conn = pc
                break

        if pooled_conn is None:
            logger.warning("Releasing unknown connection")
            return

        # Check if connection should be disposed
        should_dispose = (
            pooled_conn.age > self.config.max_lifetime
            or not pooled_conn.is_healthy
        )

        if should_dispose:
            await self._dispose_connection(pooled_conn)
            # Create replacement if needed
            async with self._lock:
                if len(self._all_connections) < self.config.min_size:
                    try:
                        new_conn = await self._create_connection()
                        await self._pool.put(new_conn)
                    except Exception as e:
                        logger.warning(f"Failed to create replacement: {e}")
        else:
            await self._pool.put(pooled_conn)

        self._metrics.total_released += 1
        self._update_metrics()

    async def _create_connection(self) -> PooledConnection[T]:
        """Create a new pooled connection."""
        for attempt in range(self.config.retry_attempts):
            try:
                connection = await self.factory()
                pooled_conn = PooledConnection(connection=connection)

                async with self._lock:
                    self._all_connections.add(pooled_conn)

                logger.debug(f"Created new connection (total={len(self._all_connections)})")
                return pooled_conn

            except Exception as e:
                if attempt < self.config.retry_attempts - 1:
                    logger.warning(f"Connection creation failed, retrying: {e}")
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    raise

        raise RuntimeError("Failed to create connection after retries")

    async def _dispose_connection(self, pooled_conn: PooledConnection[T]) -> None:
        """Dispose of a connection."""
        try:
            if self.disposer:
                await self.disposer(pooled_conn.connection)
        except Exception as e:
            logger.warning(f"Error disposing connection: {e}")
        finally:
            async with self._lock:
                self._all_connections.discard(pooled_conn)

    async def _validate_connection(self, pooled_conn: PooledConnection[T]) -> bool:
        """Validate a connection is healthy."""
        # Check age and idle time
        if pooled_conn.age > self.config.max_lifetime:
            return False
        if pooled_conn.idle_time > self.config.max_idle_time:
            return False

        # Run custom validator
        if self.validator:
            try:
                await self.validator(pooled_conn.connection)
                pooled_conn.is_healthy = True
                return True
            except Exception:
                pooled_conn.is_healthy = False
                return False

        return pooled_conn.is_healthy

    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while not self._closed:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._run_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")

    async def _run_health_checks(self) -> None:
        """Run health checks on all idle connections."""
        checked = 0
        removed = 0

        # Get all idle connections
        idle_connections: list[PooledConnection[T]] = []
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                idle_connections.append(conn)
            except asyncio.QueueEmpty:
                break

        # Check each connection
        for pooled_conn in idle_connections:
            checked += 1
            if await self._validate_connection(pooled_conn):
                await self._pool.put(pooled_conn)
            else:
                await self._dispose_connection(pooled_conn)
                removed += 1

        # Ensure minimum connections
        async with self._lock:
            while len(self._all_connections) < self.config.min_size:
                try:
                    new_conn = await self._create_connection()
                    await self._pool.put(new_conn)
                except Exception as e:
                    logger.warning(f"Failed to create connection: {e}")
                    break

        if removed > 0:
            logger.info(f"Health check: checked={checked}, removed={removed}")

        self._update_metrics()

    def _update_metrics(self) -> None:
        """Update pool metrics."""
        self._metrics.total_connections = len(self._all_connections)
        self._metrics.idle_connections = self._pool.qsize()
        self._metrics.active_connections = (
            self._metrics.total_connections - self._metrics.idle_connections
        )
        self._metrics.circuit_state = self._circuit_breaker.state

        # Determine pool state
        if self._closed:
            self._metrics.pool_state = PoolState.CLOSED
        elif self._metrics.total_connections == 0:
            self._metrics.pool_state = PoolState.UNHEALTHY
        elif self._metrics.idle_connections < self.config.min_size // 2:
            self._metrics.pool_state = PoolState.DEGRADED
        else:
            self._metrics.pool_state = PoolState.HEALTHY

    @property
    def metrics(self) -> PoolMetrics:
        """Get current pool metrics."""
        return self._metrics

    def __repr__(self) -> str:
        return (
            f"ConnectionPool(total={self._metrics.total_connections}, "
            f"active={self._metrics.active_connections}, "
            f"idle={self._metrics.idle_connections}, "
            f"state={self._metrics.pool_state.value})"
        )
