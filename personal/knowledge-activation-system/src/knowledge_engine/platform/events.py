"""Event bus for pub/sub messaging within the application."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class Event:
    """An event that can be published and subscribed to."""

    type: str
    data: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp,
            "source": self.source,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=data["type"],
            data=data.get("data", {}),
            timestamp=data.get("timestamp", time.time()),
            source=data.get("source", ""),
            metadata=data.get("metadata", {}),
        )


# Type alias for event handlers
EventHandler = Callable[[Event], Any]


class EventBus:
    """
    Asynchronous event bus for pub/sub messaging.

    Features:
    - Async event publishing
    - Pattern-based subscriptions
    - Event history
    - Dead letter handling
    """

    def __init__(
        self,
        max_history: int = 1000,
        enable_history: bool = True,
    ):
        """
        Initialize event bus.

        Args:
            max_history: Maximum events to keep in history
            enable_history: Whether to keep event history
        """
        self.max_history = max_history
        self.enable_history = enable_history

        self._handlers: dict[str, list[EventHandler]] = {}
        self._pattern_handlers: list[tuple[str, EventHandler]] = []
        self._history: list[Event] = []
        self._dead_letters: list[tuple[Event, str]] = []
        self._lock = asyncio.Lock()

        # Metrics
        self._published_count = 0
        self._delivered_count = 0
        self._error_count = 0

    def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> Callable[[], None]:
        """
        Subscribe to an event type.

        Args:
            event_type: Event type to subscribe to (supports * wildcards)
            handler: Handler function to call

        Returns:
            Unsubscribe function
        """
        if "*" in event_type:
            # Pattern subscription
            self._pattern_handlers.append((event_type, handler))

            def unsubscribe() -> None:
                self._pattern_handlers.remove((event_type, handler))

        else:
            # Exact subscription
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)

            def unsubscribe() -> None:
                if event_type in self._handlers:
                    self._handlers[event_type].remove(handler)

        logger.debug(f"Subscribed to event: {event_type}")
        return unsubscribe

    async def publish(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        source: str = "",
        **metadata: Any,
    ) -> Event:
        """
        Publish an event.

        Args:
            event_type: Type of event
            data: Event data
            source: Event source identifier
            **metadata: Additional metadata

        Returns:
            Published event
        """
        event = Event(
            type=event_type,
            data=data or {},
            source=source,
            metadata=metadata,
        )

        await self._dispatch(event)
        return event

    async def publish_event(self, event: Event) -> None:
        """Publish a pre-constructed event."""
        await self._dispatch(event)

    async def _dispatch(self, event: Event) -> None:
        """Dispatch event to all matching handlers."""
        self._published_count += 1

        # Store in history
        if self.enable_history:
            async with self._lock:
                self._history.append(event)
                if len(self._history) > self.max_history:
                    self._history.pop(0)

        # Get matching handlers
        handlers = self._get_matching_handlers(event.type)

        if not handlers:
            logger.debug(f"No handlers for event: {event.type}")
            return

        # Dispatch to handlers
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
                self._delivered_count += 1
            except Exception as e:
                self._error_count += 1
                logger.error(f"Event handler error for {event.type}: {e}")
                self._dead_letters.append((event, str(e)))

    def _get_matching_handlers(self, event_type: str) -> list[EventHandler]:
        """Get all handlers matching an event type."""
        handlers: list[EventHandler] = []

        # Exact matches
        if event_type in self._handlers:
            handlers.extend(self._handlers[event_type])

        # Pattern matches
        for pattern, handler in self._pattern_handlers:
            if self._match_pattern(pattern, event_type):
                handlers.append(handler)

        return handlers

    def _match_pattern(self, pattern: str, event_type: str) -> bool:
        """Check if event type matches a pattern."""
        pattern_parts = pattern.split(".")
        type_parts = event_type.split(".")

        for i, part in enumerate(pattern_parts):
            if part == "*":
                continue
            if part == "**":
                return True  # Match rest
            if i >= len(type_parts) or type_parts[i] != part:
                return False

        return len(pattern_parts) == len(type_parts)

    def get_history(
        self,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Get event history, optionally filtered by type."""
        events = self._history
        if event_type:
            events = [e for e in events if e.type == event_type]
        return list(reversed(events[-limit:]))

    def get_dead_letters(self, limit: int = 100) -> list[tuple[Event, str]]:
        """Get events that failed to process."""
        return list(reversed(self._dead_letters[-limit:]))

    def clear_history(self) -> None:
        """Clear event history."""
        self._history.clear()

    def clear_dead_letters(self) -> None:
        """Clear dead letter queue."""
        self._dead_letters.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get event bus statistics."""
        return {
            "published": self._published_count,
            "delivered": self._delivered_count,
            "errors": self._error_count,
            "history_size": len(self._history),
            "dead_letters": len(self._dead_letters),
            "handlers": sum(len(h) for h in self._handlers.values()),
            "pattern_handlers": len(self._pattern_handlers),
        }


# Decorator for subscribing methods
def subscribe(
    event_type: str,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to mark a method as an event handler.

    Usage:
        class MyService:
            @subscribe("document.created")
            async def on_document_created(self, event: Event):
                print(f"Document created: {event.data}")
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if not hasattr(func, "_event_subscriptions"):
            func._event_subscriptions = []
        func._event_subscriptions.append(event_type)
        return func

    return decorator


# Global event bus instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get or create the global event bus."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def set_event_bus(bus: EventBus) -> None:
    """Set the global event bus."""
    global _event_bus
    _event_bus = bus


# Common event types
class EventTypes:
    """Standard event type constants."""

    # Document events
    DOCUMENT_CREATED = "document.created"
    DOCUMENT_UPDATED = "document.updated"
    DOCUMENT_DELETED = "document.deleted"
    DOCUMENT_INGESTED = "document.ingested"

    # Chunk events
    CHUNK_CREATED = "chunk.created"
    CHUNK_EMBEDDED = "chunk.embedded"

    # Search events
    SEARCH_PERFORMED = "search.performed"
    QUERY_ANSWERED = "query.answered"

    # Memory events
    MEMORY_STORED = "memory.stored"
    MEMORY_RECALLED = "memory.recalled"

    # Review events
    REVIEW_COMPLETED = "review.completed"
    CARD_REVIEWED = "card.reviewed"

    # System events
    SYSTEM_STARTED = "system.started"
    SYSTEM_SHUTDOWN = "system.shutdown"
    HEALTH_CHECK = "system.health_check"
