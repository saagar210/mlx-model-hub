#!/usr/bin/env python3
"""Seed development database with sample content (P35).

Usage:
    python scripts/seed_dev.py
    python scripts/seed_dev.py --clear  # Clear existing and reseed
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge.db import Database, get_db, close_db
from knowledge.embeddings import get_embedding_service, close_embedding_service

# Sample content for development
SAMPLE_CONTENT = [
    {
        "title": "FastAPI Dependency Injection",
        "content_type": "note",
        "namespace": "frameworks/fastapi",
        "tags": ["python", "fastapi", "patterns"],
        "chunks": [
            """FastAPI's dependency injection system is one of its most powerful features.
            Dependencies are declared as function parameters and FastAPI automatically
            resolves them. You can use Depends() to inject database connections,
            authentication, and other services.""",
            """Example of a database dependency:
            ```python
            async def get_db():
                db = await Database.connect()
                try:
                    yield db
                finally:
                    await db.close()

            @app.get("/users")
            async def list_users(db = Depends(get_db)):
                return await db.fetch("SELECT * FROM users")
            ```""",
        ],
    },
    {
        "title": "PostgreSQL Connection Pooling",
        "content_type": "note",
        "namespace": "databases",
        "tags": ["postgresql", "performance", "asyncpg"],
        "chunks": [
            """Connection pooling is essential for database-heavy applications.
            asyncpg provides built-in connection pooling through create_pool().
            Configure min_size and max_size based on your workload.""",
            """Best practices for connection pools:
            - Set min_size to handle baseline load
            - Set max_size to prevent overwhelming the database
            - Use connection timeouts to prevent hangs
            - Monitor pool utilization in production""",
        ],
    },
    {
        "title": "Hybrid Search Implementation",
        "content_type": "pattern",
        "namespace": "patterns",
        "tags": ["search", "rag", "python"],
        "chunks": [
            """Hybrid search combines keyword (BM25) and semantic (vector) search
            for better retrieval. The key is using Reciprocal Rank Fusion (RRF)
            to merge results from both methods.""",
            """```python
            def rrf_score(rank: int, k: int = 60) -> float:
                return 1.0 / (k + rank)

            def merge_results(bm25_results, vector_results, k: int = 60):
                scores = {}
                for rank, doc in enumerate(bm25_results):
                    scores[doc.id] = scores.get(doc.id, 0) + rrf_score(rank, k)
                for rank, doc in enumerate(vector_results):
                    scores[doc.id] = scores.get(doc.id, 0) + rrf_score(rank, k)
                return sorted(scores.items(), key=lambda x: x[1], reverse=True)
            ```""",
        ],
    },
    {
        "title": "TypeScript Async Patterns",
        "content_type": "pattern",
        "namespace": "patterns",
        "tags": ["typescript", "async", "patterns"],
        "chunks": [
            """TypeScript async patterns for handling concurrent operations.
            Use Promise.all for parallel execution, Promise.allSettled for
            fault-tolerant parallelism.""",
            """Retry with exponential backoff:
            ```typescript
            async function retry<T>(
              fn: () => Promise<T>,
              maxAttempts: number = 3,
              baseDelay: number = 1000
            ): Promise<T> {
              for (let attempt = 1; attempt <= maxAttempts; attempt++) {
                try {
                  return await fn();
                } catch (error) {
                  if (attempt === maxAttempts) throw error;
                  await sleep(baseDelay * Math.pow(2, attempt - 1));
                }
              }
              throw new Error('Unreachable');
            }
            ```""",
        ],
    },
    {
        "title": "Docker Multi-Stage Builds",
        "content_type": "note",
        "namespace": "devops",
        "tags": ["docker", "optimization", "ci-cd"],
        "chunks": [
            """Multi-stage builds reduce image size by separating build and
            runtime environments. Build dependencies stay in builder stage.""",
            """Example multi-stage Dockerfile:
            ```dockerfile
            # Build stage
            FROM node:20 AS builder
            WORKDIR /app
            COPY package*.json ./
            RUN npm ci
            COPY . .
            RUN npm run build

            # Runtime stage
            FROM node:20-slim
            WORKDIR /app
            COPY --from=builder /app/dist ./dist
            COPY --from=builder /app/node_modules ./node_modules
            CMD ["node", "dist/index.js"]
            ```""",
        ],
    },
]


async def seed_database(clear: bool = False):
    """Seed the development database with sample content."""
    print("Connecting to database...")
    db = await get_db()

    if clear:
        print("Clearing existing content...")
        async with db._pool.acquire() as conn:
            await conn.execute("TRUNCATE content, chunks CASCADE")

    print("Seeding sample content...")
    embedding_service = await get_embedding_service()

    for item in SAMPLE_CONTENT:
        print(f"  Adding: {item['title']}")

        # Insert content
        content_id = await db.insert_content(
            title=item["title"],
            content_type=item["content_type"],
            namespace=item.get("namespace", "default"),
            tags=item.get("tags", []),
        )

        # Insert chunks with embeddings
        for i, chunk_text in enumerate(item["chunks"]):
            # Generate embedding
            embedding = await embedding_service.embed_text(chunk_text)

            async with db._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO chunks (content_id, chunk_index, chunk_text, embedding)
                    VALUES ($1, $2, $3, $4)
                    """,
                    content_id,
                    i,
                    chunk_text,
                    embedding,
                )

    print(f"\nSeeded {len(SAMPLE_CONTENT)} items with {sum(len(i['chunks']) for i in SAMPLE_CONTENT)} chunks")

    await close_db()
    await close_embedding_service()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Seed development database")
    parser.add_argument("--clear", action="store_true", help="Clear existing content first")
    args = parser.parse_args()

    asyncio.run(seed_database(clear=args.clear))


if __name__ == "__main__":
    main()
