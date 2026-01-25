"""Neo4j graph database adapter."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from knowledge_engine.config import Settings, get_settings

logger = logging.getLogger(__name__)


class Neo4jStore:
    """Neo4j graph database adapter with connection pooling and retry logic."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize Neo4j connection."""
        self._settings = settings or get_settings()
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """Establish connection to Neo4j."""
        if self._driver is not None:
            return

        self._driver = AsyncGraphDatabase.driver(
            self._settings.neo4j_uri,
            auth=(
                self._settings.neo4j_user,
                self._settings.neo4j_password.get_secret_value(),
            ),
            max_connection_pool_size=self._settings.neo4j_max_connection_pool_size,
        )
        # Verify connectivity
        await self._driver.verify_connectivity()
        logger.info("Connected to Neo4j at %s", self._settings.neo4j_uri)

    async def close(self) -> None:
        """Close Neo4j connection."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            logger.info("Disconnected from Neo4j")

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Get a Neo4j session with automatic cleanup."""
        if self._driver is None:
            await self.connect()
        assert self._driver is not None

        session = self._driver.session(database=self._settings.neo4j_database)
        try:
            yield session
        finally:
            await session.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def execute(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query with retry logic."""
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    async def create_entity(
        self,
        entity_type: str,
        name: str,
        properties: dict[str, Any] | None = None,
        namespace: str = "default",
    ) -> str:
        """Create or merge an entity node."""
        props = properties or {}
        props["name"] = name
        props["namespace"] = namespace

        query = f"""
        MERGE (e:{entity_type} {{name: $name, namespace: $namespace}})
        ON CREATE SET e += $props, e.created_at = datetime()
        ON MATCH SET e += $props, e.updated_at = datetime()
        RETURN elementId(e) as id
        """
        result = await self.execute(query, {"name": name, "namespace": namespace, "props": props})
        return result[0]["id"] if result else ""

    async def create_relation(
        self,
        from_name: str,
        from_type: str,
        to_name: str,
        to_type: str,
        relation_type: str,
        properties: dict[str, Any] | None = None,
        namespace: str = "default",
    ) -> None:
        """Create a relationship between two entities."""
        props = properties or {}
        props["namespace"] = namespace

        query = f"""
        MATCH (a:{from_type} {{name: $from_name, namespace: $namespace}})
        MATCH (b:{to_type} {{name: $to_name, namespace: $namespace}})
        MERGE (a)-[r:{relation_type}]->(b)
        ON CREATE SET r += $props, r.created_at = datetime()
        ON MATCH SET r += $props
        """
        await self.execute(
            query,
            {
                "from_name": from_name,
                "to_name": to_name,
                "namespace": namespace,
                "props": props,
            },
        )

    async def traverse(
        self,
        start_entity: str,
        entity_type: str | None = None,
        relation_types: list[str] | None = None,
        hops: int = 2,
        namespace: str = "default",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Traverse the graph from a starting entity."""
        type_filter = f":{entity_type}" if entity_type else ""
        rel_filter = f":{('|'.join(relation_types))}" if relation_types else ""

        query = f"""
        MATCH path = (start{type_filter} {{name: $name, namespace: $namespace}})
                     -[{rel_filter}*1..{hops}]-(related)
        WHERE related.namespace = $namespace
        WITH related, length(path) as distance,
             [r in relationships(path) | type(r)] as relations
        RETURN DISTINCT related.name as name,
               labels(related)[0] as type,
               distance,
               relations
        ORDER BY distance
        LIMIT $limit
        """
        return await self.execute(
            query,
            {"name": start_entity, "namespace": namespace, "limit": limit},
        )

    async def find_entities_by_embedding(
        self,
        embedding: list[float],
        entity_type: str | None = None,
        namespace: str = "default",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find entities by vector similarity (requires Neo4j 5.11+ vector index)."""
        type_filter = f":{entity_type}" if entity_type else ""

        query = f"""
        CALL db.index.vector.queryNodes('entity_embeddings', $limit, $embedding)
        YIELD node, score
        WHERE node.namespace = $namespace
        {"AND node:" + entity_type if entity_type else ""}
        RETURN node.name as name,
               labels(node)[0] as type,
               node as properties,
               score
        LIMIT $limit
        """
        return await self.execute(
            query,
            {"embedding": embedding, "namespace": namespace, "limit": limit},
        )

    async def get_subgraph(
        self,
        entity_names: list[str],
        namespace: str = "default",
        include_relations: bool = True,
    ) -> dict[str, Any]:
        """Get a subgraph containing specified entities and their relations."""
        query = """
        MATCH (n)
        WHERE n.name IN $names AND n.namespace = $namespace
        OPTIONAL MATCH (n)-[r]-(m)
        WHERE m.namespace = $namespace AND m.name IN $names
        RETURN collect(DISTINCT n) as nodes,
               collect(DISTINCT r) as relations
        """
        result = await self.execute(query, {"names": entity_names, "namespace": namespace})
        if result:
            return {"nodes": result[0]["nodes"], "relations": result[0]["relations"]}
        return {"nodes": [], "relations": []}

    async def ensure_indexes(self, namespace: str = "default") -> None:
        """Create necessary indexes for performance."""
        indexes = [
            "CREATE INDEX entity_name IF NOT EXISTS FOR (n:Entity) ON (n.name)",
            "CREATE INDEX entity_namespace IF NOT EXISTS FOR (n:Entity) ON (n.namespace)",
            "CREATE INDEX concept_name IF NOT EXISTS FOR (n:Concept) ON (n.name)",
            "CREATE INDEX document_id IF NOT EXISTS FOR (n:Document) ON (n.document_id)",
        ]
        for index_query in indexes:
            try:
                await self.execute(index_query)
            except Exception as e:
                logger.warning("Index creation warning: %s", e)

    async def health_check(self) -> bool:
        """Check Neo4j connection health."""
        try:
            result = await self.execute("RETURN 1 as health")
            return bool(result and result[0]["health"] == 1)
        except Exception as e:
            logger.error("Neo4j health check failed: %s", e)
            return False
