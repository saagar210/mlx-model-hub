"""Query debugging and tracing tools."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TraceEventType(str, Enum):
    """Types of trace events."""

    QUERY_START = "query_start"
    QUERY_END = "query_end"
    EMBEDDING_START = "embedding_start"
    EMBEDDING_END = "embedding_end"
    SEARCH_START = "search_start"
    SEARCH_END = "search_end"
    RERANK_START = "rerank_start"
    RERANK_END = "rerank_end"
    LLM_START = "llm_start"
    LLM_END = "llm_end"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    ERROR = "error"
    CUSTOM = "custom"


@dataclass
class TraceEvent:
    """A single trace event."""

    type: TraceEventType
    name: str
    timestamp: float = field(default_factory=time.time)
    duration_ms: float | None = None
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    parent_id: str | None = None
    span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "name": self.name,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "data": self.data,
            "error": self.error,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
        }


@dataclass
class QueryTrace:
    """Complete trace of a query execution."""

    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query_text: str = ""
    events: list[TraceEvent] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    result: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return (time.time() - self.start_time) * 1000

    @property
    def is_complete(self) -> bool:
        return self.end_time is not None

    def add_event(self, event: TraceEvent) -> None:
        """Add an event to the trace."""
        self.events.append(event)

    def get_timeline(self) -> list[dict[str, Any]]:
        """Get events as a timeline."""
        return [e.to_dict() for e in sorted(self.events, key=lambda e: e.timestamp)]

    def get_breakdown(self) -> dict[str, float]:
        """Get time breakdown by event type."""
        breakdown: dict[str, float] = {}
        for event in self.events:
            if event.duration_ms:
                key = event.type.value
                breakdown[key] = breakdown.get(key, 0) + event.duration_ms
        return breakdown

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query_text": self.query_text,
            "duration_ms": self.duration_ms,
            "events": self.get_timeline(),
            "breakdown": self.get_breakdown(),
            "error": self.error,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        status = "error" if self.error else "ok"
        return (
            f"QueryTrace(id={self.query_id[:8]}, "
            f"duration={self.duration_ms:.1f}ms, "
            f"events={len(self.events)}, "
            f"status={status})"
        )


class DebugSession:
    """
    A debugging session for capturing query traces.

    Usage:
        async with debugger.session() as session:
            result = await engine.search("query")
            trace = session.current_trace
    """

    def __init__(self, debugger: QueryDebugger):
        self.debugger = debugger
        self.traces: list[QueryTrace] = []
        self.current_trace: QueryTrace | None = None
        self._active = False

    async def start(self) -> None:
        """Start the debug session."""
        self._active = True
        self.debugger._register_session(self)

    async def stop(self) -> None:
        """Stop the debug session."""
        self._active = False
        self.debugger._unregister_session(self)

    def start_trace(self, query_text: str, **metadata: Any) -> QueryTrace:
        """Start a new trace."""
        self.current_trace = QueryTrace(
            query_text=query_text,
            metadata=metadata,
        )
        self.traces.append(self.current_trace)
        return self.current_trace

    def end_trace(
        self,
        result: Any = None,
        error: str | None = None,
    ) -> QueryTrace | None:
        """End the current trace."""
        if self.current_trace:
            self.current_trace.end_time = time.time()
            self.current_trace.result = result
            self.current_trace.error = error
            trace = self.current_trace
            self.current_trace = None
            return trace
        return None

    @asynccontextmanager
    async def trace_span(
        self,
        event_type: TraceEventType,
        name: str,
        **data: Any,
    ) -> AsyncIterator[TraceEvent]:
        """Context manager for tracing a span."""
        start_time = time.time()
        event = TraceEvent(
            type=event_type,
            name=name,
            timestamp=start_time,
            data=data,
        )

        try:
            yield event
        except Exception as e:
            event.error = str(e)
            raise
        finally:
            event.duration_ms = (time.time() - start_time) * 1000
            if self.current_trace:
                self.current_trace.add_event(event)

    def get_summary(self) -> dict[str, Any]:
        """Get session summary."""
        total_duration = sum(t.duration_ms for t in self.traces)
        errors = sum(1 for t in self.traces if t.error)

        return {
            "total_traces": len(self.traces),
            "total_duration_ms": total_duration,
            "avg_duration_ms": total_duration / len(self.traces) if self.traces else 0,
            "errors": errors,
            "success_rate": (len(self.traces) - errors) / len(self.traces)
            if self.traces
            else 1.0,
        }


class QueryDebugger:
    """
    Query debugging toolkit.

    Features:
    - Trace capture and analysis
    - Query explain plans
    - Performance profiling
    - Debug sessions
    """

    def __init__(
        self,
        enabled: bool = True,
        max_traces: int = 100,
        log_traces: bool = False,
    ):
        """
        Initialize debugger.

        Args:
            enabled: Whether debugging is enabled
            max_traces: Maximum traces to keep in memory
            log_traces: Whether to log traces
        """
        self.enabled = enabled
        self.max_traces = max_traces
        self.log_traces = log_traces

        self._traces: list[QueryTrace] = []
        self._sessions: list[DebugSession] = []
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[DebugSession]:
        """Create a debug session."""
        session = DebugSession(self)
        await session.start()
        try:
            yield session
        finally:
            await session.stop()

    def _register_session(self, session: DebugSession) -> None:
        """Register a debug session."""
        self._sessions.append(session)

    def _unregister_session(self, session: DebugSession) -> None:
        """Unregister a debug session."""
        if session in self._sessions:
            self._sessions.remove(session)

    async def record_trace(self, trace: QueryTrace) -> None:
        """Record a completed trace."""
        if not self.enabled:
            return

        async with self._lock:
            self._traces.append(trace)
            if len(self._traces) > self.max_traces:
                self._traces.pop(0)

        if self.log_traces:
            logger.info(
                f"Query trace: {trace.query_text[:50]}... "
                f"duration={trace.duration_ms:.1f}ms"
            )

    def get_recent_traces(self, limit: int = 10) -> list[QueryTrace]:
        """Get recent traces."""
        return list(reversed(self._traces[-limit:]))

    def get_slow_queries(
        self,
        threshold_ms: float = 1000,
        limit: int = 10,
    ) -> list[QueryTrace]:
        """Get slow queries above threshold."""
        slow = [t for t in self._traces if t.duration_ms >= threshold_ms]
        return sorted(slow, key=lambda t: t.duration_ms, reverse=True)[:limit]

    def get_error_traces(self, limit: int = 10) -> list[QueryTrace]:
        """Get traces that ended in error."""
        errors = [t for t in self._traces if t.error]
        return list(reversed(errors[-limit:]))

    def get_stats(self) -> dict[str, Any]:
        """Get debugging statistics."""
        if not self._traces:
            return {
                "total_traces": 0,
                "avg_duration_ms": 0,
                "p50_ms": 0,
                "p95_ms": 0,
                "p99_ms": 0,
                "error_rate": 0,
            }

        durations = sorted([t.duration_ms for t in self._traces])
        errors = sum(1 for t in self._traces if t.error)

        def percentile(data: list[float], p: float) -> float:
            idx = int(len(data) * p / 100)
            return data[min(idx, len(data) - 1)]

        return {
            "total_traces": len(self._traces),
            "avg_duration_ms": sum(durations) / len(durations),
            "p50_ms": percentile(durations, 50),
            "p95_ms": percentile(durations, 95),
            "p99_ms": percentile(durations, 99),
            "min_ms": min(durations),
            "max_ms": max(durations),
            "error_rate": errors / len(self._traces),
            "active_sessions": len(self._sessions),
        }

    def clear(self) -> None:
        """Clear all traces."""
        self._traces.clear()

    def export_traces(self, format: str = "json") -> str:
        """Export traces to JSON or other formats."""
        import json

        data = {
            "stats": self.get_stats(),
            "traces": [t.to_dict() for t in self._traces],
        }

        if format == "json":
            return json.dumps(data, indent=2, default=str)

        raise ValueError(f"Unsupported format: {format}")


# Global debugger instance
_debugger: QueryDebugger | None = None


def get_debugger() -> QueryDebugger:
    """Get or create the global debugger."""
    global _debugger
    if _debugger is None:
        _debugger = QueryDebugger()
    return _debugger


def set_debugger(debugger: QueryDebugger) -> None:
    """Set the global debugger."""
    global _debugger
    _debugger = debugger
