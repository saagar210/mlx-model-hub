"""Sharding strategies for distributed data partitioning."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ShardingStrategy(str, Enum):
    """Sharding strategies."""

    HASH = "hash"  # Consistent hashing
    RANGE = "range"  # Range-based
    ROUND_ROBIN = "round_robin"  # Sequential distribution
    NAMESPACE = "namespace"  # Namespace-based


class ShardState(str, Enum):
    """Shard health states."""

    ACTIVE = "active"
    READONLY = "readonly"
    DRAINING = "draining"
    OFFLINE = "offline"


@dataclass
class ShardConfig:
    """Configuration for a shard."""

    id: str
    host: str
    port: int
    database: str
    weight: int = 1  # For weighted distribution
    state: ShardState = ShardState.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.host}:{self.port}/{self.database}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "weight": self.weight,
            "state": self.state.value,
            "metadata": self.metadata,
        }


@dataclass
class ShardKey:
    """A sharding key with routing information."""

    value: str
    shard_id: str
    partition: int | None = None

    @classmethod
    def from_string(cls, value: str, num_shards: int) -> ShardKey:
        """Create a shard key with calculated partition."""
        partition = cls._hash_to_partition(value, num_shards)
        return cls(value=value, shard_id="", partition=partition)

    @staticmethod
    def _hash_to_partition(value: str, num_partitions: int) -> int:
        """Hash value to partition number."""
        hash_value = int(hashlib.md5(value.encode()).hexdigest(), 16)
        return hash_value % num_partitions


class ConsistentHash:
    """
    Consistent hashing ring for shard distribution.

    Uses virtual nodes for better distribution.
    """

    def __init__(self, virtual_nodes: int = 150):
        self.virtual_nodes = virtual_nodes
        self._ring: dict[int, str] = {}
        self._sorted_keys: list[int] = []
        self._nodes: set[str] = set()

    def add_node(self, node_id: str, weight: int = 1) -> None:
        """Add a node to the hash ring."""
        if node_id in self._nodes:
            return

        self._nodes.add(node_id)

        # Add virtual nodes based on weight
        for i in range(self.virtual_nodes * weight):
            key = self._hash(f"{node_id}:{i}")
            self._ring[key] = node_id

        self._sorted_keys = sorted(self._ring.keys())
        logger.debug(f"Added node {node_id} with {self.virtual_nodes * weight} vnodes")

    def remove_node(self, node_id: str) -> None:
        """Remove a node from the hash ring."""
        if node_id not in self._nodes:
            return

        self._nodes.discard(node_id)

        # Remove virtual nodes
        keys_to_remove = [k for k, v in self._ring.items() if v == node_id]
        for key in keys_to_remove:
            del self._ring[key]

        self._sorted_keys = sorted(self._ring.keys())
        logger.debug(f"Removed node {node_id}")

    def get_node(self, key: str) -> str | None:
        """Get the node responsible for a key."""
        if not self._ring:
            return None

        hash_key = self._hash(key)

        # Binary search for the first node >= hash_key
        idx = self._bisect_left(hash_key)
        if idx >= len(self._sorted_keys):
            idx = 0

        return self._ring[self._sorted_keys[idx]]

    def get_nodes(self, key: str, count: int = 1) -> list[str]:
        """Get multiple nodes for a key (for replication)."""
        if not self._ring:
            return []

        nodes = []
        seen = set()
        hash_key = self._hash(key)
        idx = self._bisect_left(hash_key)

        while len(nodes) < count and len(seen) < len(self._nodes):
            if idx >= len(self._sorted_keys):
                idx = 0

            node = self._ring[self._sorted_keys[idx]]
            if node not in seen:
                nodes.append(node)
                seen.add(node)

            idx += 1

        return nodes

    def _hash(self, key: str) -> int:
        """Hash a key to an integer."""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def _bisect_left(self, x: int) -> int:
        """Binary search for insertion point."""
        lo, hi = 0, len(self._sorted_keys)
        while lo < hi:
            mid = (lo + hi) // 2
            if self._sorted_keys[mid] < x:
                lo = mid + 1
            else:
                hi = mid
        return lo


class ShardManager:
    """
    Manages shard routing and operations.

    Features:
    - Multiple sharding strategies
    - Consistent hashing for distribution
    - Shard health tracking
    - Rebalancing support
    """

    def __init__(
        self,
        strategy: ShardingStrategy = ShardingStrategy.HASH,
        replication_factor: int = 1,
    ):
        """
        Initialize shard manager.

        Args:
            strategy: Sharding strategy to use
            replication_factor: Number of replicas per key
        """
        self.strategy = strategy
        self.replication_factor = replication_factor

        self._shards: dict[str, ShardConfig] = {}
        self._hash_ring = ConsistentHash()
        self._namespace_map: dict[str, str] = {}
        self._round_robin_counter = 0

    def add_shard(self, config: ShardConfig) -> None:
        """Add a shard to the cluster."""
        self._shards[config.id] = config

        if self.strategy == ShardingStrategy.HASH:
            self._hash_ring.add_node(config.id, config.weight)

        logger.info(f"Added shard: {config.id} ({config.host}:{config.port})")

    def remove_shard(self, shard_id: str) -> None:
        """Remove a shard from the cluster."""
        if shard_id not in self._shards:
            return

        del self._shards[shard_id]
        self._hash_ring.remove_node(shard_id)

        # Remove namespace mappings
        self._namespace_map = {
            ns: sid for ns, sid in self._namespace_map.items() if sid != shard_id
        }

        logger.info(f"Removed shard: {shard_id}")

    def set_shard_state(self, shard_id: str, state: ShardState) -> None:
        """Update shard state."""
        if shard_id in self._shards:
            self._shards[shard_id].state = state
            logger.info(f"Shard {shard_id} state changed to {state.value}")

    def get_shard(self, key: str, namespace: str | None = None) -> ShardConfig | None:
        """
        Get the shard responsible for a key.

        Args:
            key: The key to route
            namespace: Optional namespace for namespace-based sharding
        """
        if not self._shards:
            return None

        shard_id: str | None = None

        if self.strategy == ShardingStrategy.HASH:
            shard_id = self._hash_ring.get_node(key)

        elif self.strategy == ShardingStrategy.NAMESPACE:
            if namespace and namespace in self._namespace_map:
                shard_id = self._namespace_map[namespace]
            else:
                # Fallback to hash
                shard_id = self._hash_ring.get_node(namespace or key)

        elif self.strategy == ShardingStrategy.ROUND_ROBIN:
            active_shards = [
                s for s in self._shards.values() if s.state == ShardState.ACTIVE
            ]
            if active_shards:
                shard = active_shards[
                    self._round_robin_counter % len(active_shards)
                ]
                self._round_robin_counter += 1
                shard_id = shard.id

        elif self.strategy == ShardingStrategy.RANGE:
            # Range sharding requires explicit range configuration
            shard_id = self._get_range_shard(key)

        if shard_id:
            shard = self._shards.get(shard_id)
            if shard and shard.state != ShardState.OFFLINE:
                return shard

        # Fallback to first active shard
        for shard in self._shards.values():
            if shard.state == ShardState.ACTIVE:
                return shard

        return None

    def get_shards(
        self, key: str, count: int | None = None
    ) -> list[ShardConfig]:
        """
        Get multiple shards for a key (for replication).

        Args:
            key: The key to route
            count: Number of shards to return (defaults to replication_factor)
        """
        count = count or self.replication_factor

        if self.strategy == ShardingStrategy.HASH:
            shard_ids = self._hash_ring.get_nodes(key, count)
            return [
                self._shards[sid]
                for sid in shard_ids
                if sid in self._shards
                and self._shards[sid].state != ShardState.OFFLINE
            ]

        # For other strategies, return single shard
        shard = self.get_shard(key)
        return [shard] if shard else []

    def assign_namespace(self, namespace: str, shard_id: str) -> None:
        """Assign a namespace to a specific shard."""
        if shard_id in self._shards:
            self._namespace_map[namespace] = shard_id
            logger.info(f"Assigned namespace '{namespace}' to shard {shard_id}")

    def get_all_shards(
        self, include_inactive: bool = False
    ) -> list[ShardConfig]:
        """Get all shards."""
        if include_inactive:
            return list(self._shards.values())
        return [
            s for s in self._shards.values() if s.state != ShardState.OFFLINE
        ]

    def get_active_shards(self) -> list[ShardConfig]:
        """Get only active shards."""
        return [
            s for s in self._shards.values() if s.state == ShardState.ACTIVE
        ]

    def _get_range_shard(self, key: str) -> str | None:
        """Get shard based on range (for RANGE strategy)."""
        # Simple implementation: use first character ranges
        # In production, you'd want configurable ranges
        if not self._shards:
            return None

        shards = list(self._shards.keys())
        key_hash = hash(key) % len(shards)
        return shards[key_hash]

    def calculate_distribution(self) -> dict[str, int]:
        """Calculate key distribution across shards (for testing)."""
        distribution: dict[str, int] = {sid: 0 for sid in self._shards}

        # Sample distribution with random keys
        for i in range(10000):
            key = f"test_key_{i}"
            shard = self.get_shard(key)
            if shard:
                distribution[shard.id] += 1

        return distribution

    def get_stats(self) -> dict[str, Any]:
        """Get shard cluster statistics."""
        state_counts = {state: 0 for state in ShardState}
        for shard in self._shards.values():
            state_counts[shard.state] += 1

        return {
            "total_shards": len(self._shards),
            "active_shards": state_counts[ShardState.ACTIVE],
            "readonly_shards": state_counts[ShardState.READONLY],
            "draining_shards": state_counts[ShardState.DRAINING],
            "offline_shards": state_counts[ShardState.OFFLINE],
            "strategy": self.strategy.value,
            "replication_factor": self.replication_factor,
            "namespaces": len(self._namespace_map),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize shard manager state."""
        return {
            "strategy": self.strategy.value,
            "replication_factor": self.replication_factor,
            "shards": [s.to_dict() for s in self._shards.values()],
            "namespace_map": self._namespace_map,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShardManager:
        """Deserialize shard manager state."""
        manager = cls(
            strategy=ShardingStrategy(data.get("strategy", "hash")),
            replication_factor=data.get("replication_factor", 1),
        )

        for shard_data in data.get("shards", []):
            config = ShardConfig(
                id=shard_data["id"],
                host=shard_data["host"],
                port=shard_data["port"],
                database=shard_data["database"],
                weight=shard_data.get("weight", 1),
                state=ShardState(shard_data.get("state", "active")),
                metadata=shard_data.get("metadata", {}),
            )
            manager.add_shard(config)

        manager._namespace_map = data.get("namespace_map", {})
        return manager
