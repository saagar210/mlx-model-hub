"""Distributed task queue for async job processing."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TaskPriority(int, Enum):
    """Task priority levels."""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass
class Task:
    """A task to be executed."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    max_retries: int = 3
    retry_delay: float = 5.0  # seconds
    timeout: float = 300.0  # seconds
    created_at: float = field(default_factory=time.time)
    scheduled_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Internal state
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    started_at: float | None = None
    completed_at: float | None = None
    error: str | None = None
    result: Any = None

    @property
    def age(self) -> float:
        return time.time() - self.created_at

    @property
    def is_scheduled(self) -> bool:
        if self.scheduled_at is None:
            return False
        return time.time() >= self.scheduled_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "payload": self.payload,
            "priority": self.priority.value,
            "status": self.status.value,
            "attempts": self.attempts,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            payload=data.get("payload", {}),
            priority=TaskPriority(data.get("priority", TaskPriority.NORMAL.value)),
            status=TaskStatus(data.get("status", TaskStatus.PENDING.value)),
            attempts=data.get("attempts", 0),
            max_retries=data.get("max_retries", 3),
            created_at=data.get("created_at", time.time()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TaskResult:
    """Result of task execution."""

    task_id: str
    status: TaskStatus
    result: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0
    attempts: int = 0


class TaskQueue:
    """
    Async task queue with priorities and retries.

    Features:
    - Priority-based scheduling
    - Automatic retries with backoff
    - Task timeout handling
    - In-memory and Redis backends
    - Worker management
    """

    def __init__(
        self,
        max_workers: int = 4,
        redis_url: str | None = None,
        queue_name: str = "tasks",
    ):
        """
        Initialize task queue.

        Args:
            max_workers: Maximum concurrent workers
            redis_url: Optional Redis URL for persistence
            queue_name: Name of the queue
        """
        self.max_workers = max_workers
        self.redis_url = redis_url
        self.queue_name = queue_name

        self._handlers: dict[str, Callable[..., Any]] = {}
        self._queues: dict[TaskPriority, asyncio.PriorityQueue[tuple[float, Task]]] = {
            priority: asyncio.PriorityQueue() for priority in TaskPriority
        }
        self._tasks: dict[str, Task] = {}
        self._workers: list[asyncio.Task[None]] = []
        self._running = False
        self._lock = asyncio.Lock()

        # Redis connection
        self._redis: Any = None

    async def start(self) -> None:
        """Start the task queue and workers."""
        if self._running:
            return

        # Connect to Redis if configured
        if self.redis_url:
            try:
                import redis.asyncio as redis

                self._redis = await redis.from_url(self.redis_url)
                logger.info(f"Connected to Redis: {self.redis_url}")

                # Restore pending tasks from Redis
                await self._restore_tasks()
            except ImportError:
                logger.warning("Redis not available, using in-memory queue")

        self._running = True

        # Start workers
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)

        logger.info(f"Started task queue with {self.max_workers} workers")

    async def stop(self, graceful: bool = True) -> None:
        """Stop the task queue."""
        self._running = False

        if graceful:
            # Wait for workers to finish current tasks
            for worker in self._workers:
                worker.cancel()
                try:
                    await worker
                except asyncio.CancelledError:
                    pass
        else:
            # Cancel immediately
            for worker in self._workers:
                worker.cancel()

        self._workers.clear()

        # Close Redis connection
        if self._redis:
            await self._redis.close()

        logger.info("Task queue stopped")

    def register(
        self,
        name: str,
        handler: Callable[..., Any],
    ) -> None:
        """Register a task handler."""
        self._handlers[name] = handler
        logger.debug(f"Registered handler: {name}")

    def handler(self, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register a task handler."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.register(name, func)
            return func

        return decorator

    async def enqueue(
        self,
        name: str,
        payload: dict[str, Any] | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        delay: float | None = None,
        **kwargs: Any,
    ) -> Task:
        """
        Enqueue a task for execution.

        Args:
            name: Task handler name
            payload: Task payload
            priority: Task priority
            delay: Optional delay in seconds before execution
            **kwargs: Additional task options

        Returns:
            The created task
        """
        task = Task(
            name=name,
            payload=payload or {},
            priority=priority,
            scheduled_at=time.time() + delay if delay else None,
            **kwargs,
        )

        async with self._lock:
            self._tasks[task.id] = task

            # Add to priority queue
            # Use (scheduled_time, created_time, task) for ordering
            queue_time = task.scheduled_at or task.created_at
            await self._queues[priority].put((queue_time, task))

        # Persist to Redis if available
        if self._redis:
            await self._persist_task(task)

        logger.debug(f"Enqueued task: {task.name} (id={task.id}, priority={priority.name})")
        return task

    async def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            return True
        return False

    async def wait_for(self, task_id: str, timeout: float = 60.0) -> TaskResult:
        """Wait for a task to complete."""
        start = time.time()

        while time.time() - start < timeout:
            task = self._tasks.get(task_id)
            if task and task.status in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            ):
                return TaskResult(
                    task_id=task.id,
                    status=task.status,
                    result=task.result,
                    error=task.error,
                    attempts=task.attempts,
                )
            await asyncio.sleep(0.1)

        raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")

    async def _worker_loop(self, worker_id: int) -> None:
        """Worker loop for processing tasks."""
        logger.debug(f"Worker {worker_id} started")

        while self._running:
            try:
                task = await self._get_next_task()
                if task:
                    await self._execute_task(task, worker_id)
                else:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")

        logger.debug(f"Worker {worker_id} stopped")

    async def _get_next_task(self) -> Task | None:
        """Get the next task to execute from priority queues."""
        # Check queues in priority order
        for priority in TaskPriority:
            queue = self._queues[priority]
            if not queue.empty():
                try:
                    _, task = queue.get_nowait()

                    # Skip cancelled tasks
                    if task.status == TaskStatus.CANCELLED:
                        continue

                    # Check if scheduled task is ready
                    if not task.is_scheduled:
                        # Put back in queue
                        await queue.put((task.scheduled_at, task))
                        continue

                    return task
                except asyncio.QueueEmpty:
                    continue

        return None

    async def _execute_task(self, task: Task, worker_id: int) -> None:
        """Execute a single task."""
        handler = self._handlers.get(task.name)
        if not handler:
            task.status = TaskStatus.FAILED
            task.error = f"No handler registered for: {task.name}"
            return

        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        task.attempts += 1

        logger.debug(
            f"Worker {worker_id} executing: {task.name} "
            f"(attempt {task.attempts}/{task.max_retries + 1})"
        )

        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                self._call_handler(handler, task),
                timeout=task.timeout,
            )

            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = time.time()

            logger.debug(f"Task completed: {task.name} (id={task.id})")

        except TimeoutError:
            task.error = f"Task timed out after {task.timeout}s"
            await self._handle_failure(task)

        except Exception as e:
            task.error = str(e)
            await self._handle_failure(task)

        # Update in Redis
        if self._redis:
            await self._persist_task(task)

    async def _call_handler(self, handler: Callable[..., Any], task: Task) -> Any:
        """Call the task handler."""
        if asyncio.iscoroutinefunction(handler):
            return await handler(task.payload)
        else:
            return handler(task.payload)

    async def _handle_failure(self, task: Task) -> None:
        """Handle task failure with retry logic."""
        if task.attempts <= task.max_retries:
            # Schedule retry
            task.status = TaskStatus.RETRYING
            delay = task.retry_delay * (2 ** (task.attempts - 1))  # Exponential backoff
            task.scheduled_at = time.time() + delay

            # Re-enqueue
            await self._queues[task.priority].put((task.scheduled_at, task))

            logger.warning(
                f"Task {task.name} failed, retrying in {delay:.1f}s "
                f"(attempt {task.attempts}/{task.max_retries + 1}): {task.error}"
            )
        else:
            task.status = TaskStatus.FAILED
            task.completed_at = time.time()
            logger.error(f"Task {task.name} failed permanently: {task.error}")

    async def _persist_task(self, task: Task) -> None:
        """Persist task to Redis."""
        if not self._redis:
            return

        key = f"{self.queue_name}:task:{task.id}"
        await self._redis.set(key, json.dumps(task.to_dict()))

        # Add to set of all tasks
        await self._redis.sadd(f"{self.queue_name}:tasks", task.id)

    async def _restore_tasks(self) -> None:
        """Restore pending tasks from Redis."""
        if not self._redis:
            return

        task_ids = await self._redis.smembers(f"{self.queue_name}:tasks")

        restored = 0
        for task_id in task_ids:
            key = f"{self.queue_name}:task:{task_id.decode()}"
            data = await self._redis.get(key)
            if data:
                task_data = json.loads(data)
                task = Task.from_dict(task_data)

                # Only restore pending/retrying tasks
                if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
                    self._tasks[task.id] = task
                    queue_time = task.scheduled_at or task.created_at
                    await self._queues[task.priority].put((queue_time, task))
                    restored += 1

        if restored > 0:
            logger.info(f"Restored {restored} tasks from Redis")

    @property
    def pending_count(self) -> int:
        """Get total pending task count."""
        return sum(q.qsize() for q in self._queues.values())

    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        status_counts = dict.fromkeys(TaskStatus, 0)
        for task in self._tasks.values():
            status_counts[task.status] += 1

        return {
            "total_tasks": len(self._tasks),
            "pending": self.pending_count,
            "workers": len(self._workers),
            "handlers": list(self._handlers.keys()),
            "status_counts": {s.value: c for s, c in status_counts.items()},
        }
