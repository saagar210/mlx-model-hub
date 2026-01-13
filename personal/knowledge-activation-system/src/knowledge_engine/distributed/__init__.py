"""Distributed systems infrastructure for horizontal scaling."""

from knowledge_engine.distributed.connection_pool import (
    ConnectionPool,
    PoolConfig,
    PoolMetrics,
)
from knowledge_engine.distributed.task_queue import (
    TaskQueue,
    Task,
    TaskResult,
    TaskPriority,
)
from knowledge_engine.distributed.cache import (
    CacheLayer,
    CacheConfig,
    CacheStats,
)
from knowledge_engine.distributed.sharding import (
    ShardManager,
    ShardConfig,
    ShardKey,
)

__all__ = [
    "ConnectionPool",
    "PoolConfig",
    "PoolMetrics",
    "TaskQueue",
    "Task",
    "TaskResult",
    "TaskPriority",
    "CacheLayer",
    "CacheConfig",
    "CacheStats",
    "ShardManager",
    "ShardConfig",
    "ShardKey",
]
