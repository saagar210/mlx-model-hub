"""Storage adapters for Knowledge Engine."""

from knowledge_engine.storage.qdrant import QdrantStore
from knowledge_engine.storage.postgres import PostgresStore

__all__ = ["QdrantStore", "PostgresStore"]

# Neo4j is optional - only import if available
try:
    from knowledge_engine.storage.neo4j import Neo4jStore
    __all__.append("Neo4jStore")
except ImportError:
    Neo4jStore = None  # type: ignore
