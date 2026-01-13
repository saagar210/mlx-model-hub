"""Load testing with Locust (P29).

Run with:
    locust -f tests/load/locustfile.py --host http://localhost:8000

For headless mode:
    locust -f tests/load/locustfile.py --host http://localhost:8000 \
        --users 50 --spawn-rate 5 --run-time 60s --headless
"""

from __future__ import annotations

import random

from locust import HttpUser, between, task

# Sample queries for realistic load patterns
SAMPLE_QUERIES = [
    "machine learning basics",
    "python programming",
    "database optimization",
    "API design patterns",
    "kubernetes deployment",
    "docker containers",
    "FastAPI tutorial",
    "PostgreSQL indexes",
    "vector embeddings",
    "search algorithms",
    "software architecture",
    "microservices patterns",
    "REST API best practices",
    "async programming Python",
    "database connection pooling",
]

# Content types for creation tests
CONTENT_TYPES = ["note", "bookmark", "youtube", "file"]


class KASSearchUser(HttpUser):
    """Simulates a user performing search operations."""

    wait_time = between(1, 3)

    @task(10)
    def search_basic(self):
        """Basic search query."""
        query = random.choice(SAMPLE_QUERIES)
        self.client.post(
            "/search",
            json={"query": query, "limit": 10},
            name="/search",
        )

    @task(3)
    def search_with_rerank(self):
        """Search with reranking enabled."""
        query = random.choice(SAMPLE_QUERIES)
        self.client.post(
            "/search",
            json={"query": query, "limit": 10, "rerank": True},
            name="/search (rerank)",
        )

    @task(5)
    def search_bm25_only(self):
        """BM25-only search."""
        query = random.choice(SAMPLE_QUERIES)
        self.client.post(
            "/search",
            json={"query": query, "limit": 10, "mode": "bm25"},
            name="/search (bm25)",
        )

    @task(2)
    def search_vector_only(self):
        """Vector-only search."""
        query = random.choice(SAMPLE_QUERIES)
        self.client.post(
            "/search",
            json={"query": query, "limit": 10, "mode": "vector"},
            name="/search (vector)",
        )


class KASContentUser(HttpUser):
    """Simulates a user performing content operations."""

    wait_time = between(2, 5)

    @task(5)
    def list_content(self):
        """List content with pagination."""
        self.client.get(
            "/api/v1/content",
            params={"limit": 20, "offset": 0},
            name="/api/v1/content (list)",
        )

    @task(2)
    def create_content(self):
        """Create new content."""
        self.client.post(
            "/api/v1/content",
            json={
                "title": f"Load Test Content {random.randint(1000, 9999)}",
                "content_type": random.choice(CONTENT_TYPES),
                "namespace": "loadtest",
                "chunks": [
                    {"text": f"Test chunk {i} with random content"} for i in range(3)
                ],
            },
            name="/api/v1/content (create)",
        )


class KASBatchUser(HttpUser):
    """Simulates a user performing batch operations."""

    wait_time = between(3, 8)

    @task(1)
    def batch_search(self):
        """Batch search with multiple queries."""
        queries = random.sample(SAMPLE_QUERIES, k=min(5, len(SAMPLE_QUERIES)))
        self.client.post(
            "/api/v1/batch/search",
            json={
                "queries": [{"query": q, "limit": 5} for q in queries],
            },
            name="/api/v1/batch/search",
        )


class KASHealthCheckUser(HttpUser):
    """Simulates monitoring/health check requests."""

    wait_time = between(5, 10)

    @task(1)
    def health_check(self):
        """Health endpoint check."""
        self.client.get("/health", name="/health")

    @task(1)
    def ready_check(self):
        """Readiness check."""
        self.client.get("/health/ready", name="/health/ready")


class KASMixedUser(HttpUser):
    """Simulates a typical user with mixed operations."""

    wait_time = between(1, 5)

    @task(10)
    def search(self):
        """Search operation (most common)."""
        self.client.post(
            "/search",
            json={"query": random.choice(SAMPLE_QUERIES), "limit": 10},
        )

    @task(3)
    def list_content(self):
        """Browse content."""
        self.client.get("/api/v1/content", params={"limit": 10})

    @task(1)
    def health(self):
        """Occasional health check."""
        self.client.get("/health")
