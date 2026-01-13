"""Performance profiling tools for async code."""

from __future__ import annotations

import asyncio
import cProfile
import functools
import io
import logging
import pstats
import time
import tracemalloc
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class MemorySnapshot:
    """Memory allocation snapshot."""

    timestamp: float = field(default_factory=time.time)
    current_bytes: int = 0
    peak_bytes: int = 0
    traced_objects: int = 0
    top_allocations: list[tuple[str, int]] = field(default_factory=list)

    @property
    def current_mb(self) -> float:
        return self.current_bytes / 1024 / 1024

    @property
    def peak_mb(self) -> float:
        return self.peak_bytes / 1024 / 1024


@dataclass
class ProfileResult:
    """Result of profiling a code block."""

    name: str
    duration_ms: float
    calls: int = 1
    memory_delta_bytes: int = 0
    cpu_time_ms: float = 0.0
    memory_start: MemorySnapshot | None = None
    memory_end: MemorySnapshot | None = None
    call_stats: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def memory_delta_mb(self) -> float:
        return self.memory_delta_bytes / 1024 / 1024

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "duration_ms": self.duration_ms,
            "calls": self.calls,
            "memory_delta_mb": self.memory_delta_mb,
            "cpu_time_ms": self.cpu_time_ms,
            "call_stats": self.call_stats,
            "metadata": self.metadata,
        }


class Profiler:
    """
    Performance profiler for async code.

    Features:
    - Execution time profiling
    - Memory allocation tracking
    - CPU profiling
    - Call statistics
    """

    def __init__(
        self,
        track_memory: bool = True,
        track_cpu: bool = False,
        enabled: bool = True,
    ):
        """
        Initialize profiler.

        Args:
            track_memory: Whether to track memory allocations
            track_cpu: Whether to track CPU usage
            enabled: Whether profiling is enabled
        """
        self.track_memory = track_memory
        self.track_cpu = track_cpu
        self.enabled = enabled

        self._results: list[ProfileResult] = []
        self._memory_tracking_started = False

    @asynccontextmanager
    async def profile(
        self,
        name: str,
        **metadata: Any,
    ) -> AsyncIterator[ProfileResult]:
        """
        Profile a code block.

        Usage:
            async with profiler.profile("my_operation") as result:
                await some_async_operation()
            print(f"Duration: {result.duration_ms}ms")
        """
        if not self.enabled:
            result = ProfileResult(name=name, duration_ms=0, metadata=metadata)
            yield result
            return

        # Start memory tracking
        memory_start: MemorySnapshot | None = None
        if self.track_memory:
            memory_start = self._take_memory_snapshot()

        # Start CPU profiler
        cpu_profiler: cProfile.Profile | None = None
        if self.track_cpu:
            cpu_profiler = cProfile.Profile()
            cpu_profiler.enable()

        start_time = time.perf_counter()

        result = ProfileResult(
            name=name,
            duration_ms=0,
            memory_start=memory_start,
            metadata=metadata,
        )

        try:
            yield result
        finally:
            # Record duration
            result.duration_ms = (time.perf_counter() - start_time) * 1000

            # Stop CPU profiler
            if cpu_profiler:
                cpu_profiler.disable()
                result.call_stats = self._get_call_stats(cpu_profiler)
                result.cpu_time_ms = self._get_cpu_time(cpu_profiler)

            # End memory tracking
            if self.track_memory:
                result.memory_end = self._take_memory_snapshot()
                if result.memory_start and result.memory_end:
                    result.memory_delta_bytes = (
                        result.memory_end.current_bytes
                        - result.memory_start.current_bytes
                    )

            self._results.append(result)

    def _take_memory_snapshot(self) -> MemorySnapshot:
        """Take a memory allocation snapshot."""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            self._memory_tracking_started = True

        current, peak = tracemalloc.get_traced_memory()

        # Get top allocations
        top_allocations: list[tuple[str, int]] = []
        try:
            snapshot = tracemalloc.take_snapshot()
            stats = snapshot.statistics("lineno")[:10]
            top_allocations = [
                (str(stat.traceback), stat.size) for stat in stats
            ]
        except Exception:
            pass

        return MemorySnapshot(
            current_bytes=current,
            peak_bytes=peak,
            traced_objects=len(snapshot.traces) if snapshot else 0,
            top_allocations=top_allocations,
        )

    def _get_call_stats(self, profiler: cProfile.Profile) -> dict[str, Any]:
        """Extract call statistics from profiler."""
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats("cumulative")

        # Get top functions
        top_funcs: list[dict[str, Any]] = []
        for func, data in list(stats.stats.items())[:10]:
            cc, nc, tt, ct, callers = data
            top_funcs.append(
                {
                    "function": f"{func[0]}:{func[1]}:{func[2]}",
                    "calls": nc,
                    "total_time_ms": tt * 1000,
                    "cumulative_time_ms": ct * 1000,
                }
            )

        return {
            "total_calls": stats.total_calls,
            "primitive_calls": stats.prim_calls,
            "top_functions": top_funcs,
        }

    def _get_cpu_time(self, profiler: cProfile.Profile) -> float:
        """Get total CPU time from profiler."""
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        return stats.total_tt * 1000

    def get_results(
        self,
        name: str | None = None,
        limit: int = 100,
    ) -> list[ProfileResult]:
        """Get profiling results, optionally filtered by name."""
        results = self._results
        if name:
            results = [r for r in results if r.name == name]
        return list(reversed(results[-limit:]))

    def get_aggregate_stats(
        self,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Get aggregate statistics for a named operation."""
        results = self.get_results(name)
        if not results:
            return {}

        durations = [r.duration_ms for r in results]
        memory_deltas = [r.memory_delta_bytes for r in results]

        def percentile(data: list[float], p: float) -> float:
            sorted_data = sorted(data)
            idx = int(len(sorted_data) * p / 100)
            return sorted_data[min(idx, len(sorted_data) - 1)]

        return {
            "count": len(results),
            "duration": {
                "avg_ms": sum(durations) / len(durations),
                "min_ms": min(durations),
                "max_ms": max(durations),
                "p50_ms": percentile(durations, 50),
                "p95_ms": percentile(durations, 95),
                "p99_ms": percentile(durations, 99),
            },
            "memory": {
                "avg_delta_mb": sum(memory_deltas) / len(memory_deltas) / 1024 / 1024,
                "max_delta_mb": max(memory_deltas) / 1024 / 1024,
            },
        }

    def clear(self) -> None:
        """Clear all profiling results."""
        self._results.clear()
        if self._memory_tracking_started:
            tracemalloc.stop()
            self._memory_tracking_started = False

    def report(self, name: str | None = None) -> str:
        """Generate a profiling report."""
        stats = self.get_aggregate_stats(name)
        if not stats:
            return "No profiling data available"

        lines = [
            f"Profiling Report{f' for {name}' if name else ''}",
            "=" * 50,
            f"Total calls: {stats['count']}",
            "",
            "Duration:",
            f"  Average: {stats['duration']['avg_ms']:.2f}ms",
            f"  Min: {stats['duration']['min_ms']:.2f}ms",
            f"  Max: {stats['duration']['max_ms']:.2f}ms",
            f"  P50: {stats['duration']['p50_ms']:.2f}ms",
            f"  P95: {stats['duration']['p95_ms']:.2f}ms",
            f"  P99: {stats['duration']['p99_ms']:.2f}ms",
            "",
            "Memory:",
            f"  Avg delta: {stats['memory']['avg_delta_mb']:.2f}MB",
            f"  Max delta: {stats['memory']['max_delta_mb']:.2f}MB",
        ]

        return "\n".join(lines)


# Decorator for profiling functions
def profile_async(
    name: str | None = None,
    profiler: Profiler | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to profile an async function.

    Usage:
        @profile_async("search_operation")
        async def search(query: str) -> list:
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        func_name = name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            prof = profiler or get_profiler()
            async with prof.profile(func_name):
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)

        return wrapper

    return decorator


# Global profiler instance
_profiler: Profiler | None = None


def get_profiler() -> Profiler:
    """Get or create the global profiler."""
    global _profiler
    if _profiler is None:
        _profiler = Profiler()
    return _profiler


def set_profiler(profiler: Profiler) -> None:
    """Set the global profiler."""
    global _profiler
    _profiler = profiler
