# Implementation Plan Review & Expansion
# Developer Memory & Context Suite

**Review Date:** January 12, 2026
**Reviewer:** Claude (Opus 4.5)
**Status:** Comprehensive Review Complete

---

## Table of Contents

1. [Executive Summary of Review](#1-executive-summary-of-review)
2. [Critical Risks & Mitigations](#2-critical-risks--mitigations)
3. [Improvements Identified](#3-improvements-identified)
4. [Items to Remove or Simplify](#4-items-to-remove-or-simplify)
5. [Expanded Technical Specifications](#5-expanded-technical-specifications)
6. [Dependency Audit](#6-dependency-audit)
7. [KAS Code Reuse Analysis](#7-kas-code-reuse-analysis)
8. [Revised Architecture](#8-revised-architecture)
9. [Updated Task Breakdown](#9-updated-task-breakdown)

---

## 1. Executive Summary of Review

### Overall Assessment: **SOLID with Required Modifications**

The implementation plan is comprehensive but requires refinements based on:
- Latest 2025 best practices from web research
- Existing KAS codebase patterns that should be reused
- Performance considerations for local-first architecture
- MCP SDK known issues and workarounds

### Key Findings

| Category | Finding | Impact |
|----------|---------|--------|
| **Reuse Opportunity** | KAS has production-ready db.py, search.py, embeddings.py | Save 3-4 days |
| **Risk: Watchdog** | macOS kqueue has scalability issues | Medium - need mitigation |
| **Risk: MCP stdio** | Known error handling issues in SDK | High - need workarounds |
| **Improvement** | Use sentence-transformers directly for speed | 2x faster embeddings |
| **Improvement** | Use HNSW exclusively (not IVFFlat) | Better recall, worth memory cost |
| **Simplification** | Remove browser extension from Phase 1 | Reduces scope 20% |
| **Simplification** | Consolidate to single database | Eliminate sync complexity |

---

## 2. Critical Risks & Mitigations

### RISK-001: MCP Server stdio Error Handling (HIGH)

**Description:** The MCP Python SDK has known issues where exceptions in `@app.call_tool` handlers are not correctly translated to JSON-RPC errors. The client doesn't detect server crashes.

**Source:** [GitHub Issue #396](https://github.com/modelcontextprotocol/python-sdk/issues/396)

**Impact:** Server errors appear as successful responses with error text in content. Client hangs indefinitely if server crashes.

**Mitigation:**
```python
# Wrap all tool handlers with explicit error handling
from mcp.types import McpError

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        # ... tool logic
    except Exception as e:
        # Log to stderr (not stdout - would corrupt protocol)
        import sys
        print(f"Tool error: {e}", file=sys.stderr)

        # Return explicit error response
        return [TextContent(
            type="text",
            text=f"ERROR: {type(e).__name__}: {str(e)}"
        )]
```

**Alternative:** Consider Streamable HTTP transport for production (has auto-reconnection).

---

### RISK-002: Watchdog Performance on macOS (MEDIUM)

**Description:** Watchdog uses kqueue on macOS which requires file descriptors for each watched file. Deep directory trees cause performance issues.

**Source:** [watchdog PyPI](https://pypi.org/project/watchdog/), [Medium Alternative](https://medium.com/@efpa97_ltep_technologies/an-easy-filewatcher-for-python-no-side-effects-quick-setup-watchdog-alternative-c10e49c03071)

**Impact:** Monitoring `~/claude-code` (potentially thousands of files) could exhaust file descriptors.

**Mitigations:**
1. **Git-based detection (RECOMMENDED):** Poll `.git/HEAD` files instead of watching entire trees
2. **Polling fallback:** Use `watchdog.observers.polling.PollingObserver` with 5-10s interval
3. **Limit scope:** Only watch `.git` directories, not entire repos

**Recommended Implementation:**
```python
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
import platform

def create_observer():
    """Create platform-appropriate observer."""
    if platform.system() == "Darwin":
        # Use polling on macOS to avoid kqueue issues
        return PollingObserver(timeout=5)
    return Observer()

# Only watch .git directories
for repo in repos:
    handler = GitCommitHandler(repo)
    observer.schedule(handler, str(repo / ".git"), recursive=False)
```

---

### RISK-003: Ollama Embedding Speed (MEDIUM)

**Description:** Using Ollama's REST API for embeddings is ~2x slower than direct sentence-transformers.

**Source:** [Ollama Issue #7400](https://github.com/ollama/ollama/issues/7400)

**Impact:** Batch embedding operations (indexing, bulk import) will be slow.

**Mitigations:**
1. **Direct sentence-transformers for batch operations:**
```python
from sentence_transformers import SentenceTransformer

class HybridEmbedder:
    """Use sentence-transformers for batches, Ollama for single queries."""

    def __init__(self):
        self.batch_model = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5")
        self.batch_model.to("mps")  # Apple Silicon

    async def embed_single(self, text: str) -> list[float]:
        """Use Ollama for single queries (simpler, no model loading)."""
        return await ollama_embed(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Use sentence-transformers for speed."""
        return self.batch_model.encode(texts, normalize_embeddings=True).tolist()
```

2. **Pre-compute embeddings during ingestion** (not at query time)

---

### RISK-004: Entity Extraction Accuracy (MEDIUM)

**Description:** LLM-based entity extraction with local models (qwen2.5-coder:7b) may have inconsistent accuracy.

**Impact:** Low-quality entities degrade knowledge graph usefulness.

**Mitigations:**
1. **Confidence thresholds:** Only store entities with confidence > 0.7
2. **Entity validation:** Use pattern matching to verify extracted function/class names exist
3. **Deferred extraction:** Mark memories for re-extraction if accuracy improves
4. **Fallback to regex:** For code patterns, use regex as ground truth

```python
class EntityExtractor:
    async def extract(self, content: str, memory_type: str) -> EntityExtractionResult:
        # LLM extraction
        llm_result = await self._llm_extract(content, memory_type)

        # Validate code entities
        if memory_type in ("commit", "error"):
            llm_result = self._validate_code_entities(content, llm_result)

        # Filter by confidence
        llm_result.entities = [
            e for e in llm_result.entities
            if e.confidence >= 0.7
        ]

        return llm_result

    def _validate_code_entities(self, content: str, result: EntityExtractionResult):
        """Verify extracted entities exist in content."""
        import re

        for entity in result.entities:
            if entity.entity_type in ("function", "class", "method"):
                # Check if name appears in content
                pattern = rf"\b{re.escape(entity.name)}\b"
                if not re.search(pattern, content):
                    entity.confidence *= 0.5  # Penalize unverified

        return result
```

---

### RISK-005: Database Migration Conflicts (LOW)

**Description:** Running migrations on existing KAS database could conflict with KAS operations.

**Impact:** Database corruption or KAS downtime.

**Mitigation:** **Use same database but separate schema:**
```sql
-- Create dedicated schema
CREATE SCHEMA IF NOT EXISTS devmemory;

-- All DevMemory tables in separate schema
CREATE TABLE devmemory.memories (...);
CREATE TABLE devmemory.entities (...);

-- KAS tables remain in public schema
-- No conflicts, single connection pool
```

---

### RISK-006: Large Repository Indexing (MEDIUM)

**Description:** Repositories with >10k files could cause memory issues during CodeMCP indexing.

**Impact:** OOM errors, incomplete indexing.

**Mitigations:**
1. **Streaming processing:** Process files one at a time, don't load all into memory
2. **Incremental indexing:** Only index changed files
3. **File limits:** Cap at 5000 files per repo, warn user
4. **Language filtering:** Only index Python/JS/TS by default

```python
class BatchIndexer:
    MAX_FILES = 5000

    async def index_repo(self, repo_path: Path) -> IndexResult:
        files = list(self._discover_files(repo_path))

        if len(files) > self.MAX_FILES:
            logger.warning(f"Repo has {len(files)} files, limiting to {self.MAX_FILES}")
            files = files[:self.MAX_FILES]

        # Stream processing
        for file in files:
            await self._index_file(file)
            # Yield control to prevent blocking
            await asyncio.sleep(0)
```

---

## 3. Improvements Identified

### IMPROVEMENT-001: Reuse KAS Database Module

**Current Plan:** Write new db.py from scratch

**Better Approach:** Import and extend existing KAS db.py

**Justification:** KAS has production-tested:
- asyncpg connection pooling with proper lifecycle
- pgvector registration
- Transaction context managers
- Error handling patterns

**Implementation:**
```python
# devmemory/db/connection.py
from knowledge.db import Database as KASDatabase
from knowledge.config import Settings

class DevMemoryDatabase(KASDatabase):
    """Extend KAS database with DevMemory-specific queries."""

    async def insert_memory(self, memory: DevMemory) -> UUID:
        """Insert a new memory."""
        async with self.acquire() as conn:
            return await conn.fetchval("""
                INSERT INTO devmemory.memories (memory_type, content, ...)
                VALUES ($1, $2, ...)
                RETURNING id
            """, memory.memory_type, memory.content, ...)
```

**Savings:** 2-3 days of db layer development

---

### IMPROVEMENT-002: Use Sentence-Transformers for Batch Embeddings

**Current Plan:** All embeddings via Ollama REST API

**Better Approach:** Hybrid approach - sentence-transformers for batch, Ollama for single

**Source:** [Ollama Issue #7400](https://github.com/ollama/ollama/issues/7400) shows 2x speed improvement

**Justification:**
- sentence-transformers 3.4.1 already installed
- MPS (Apple Silicon) support built-in
- Same nomic-embed-text-v1.5 model available

**Implementation:**
```python
# shared/embeddings.py
from sentence_transformers import SentenceTransformer
import torch

class HybridEmbeddingService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._st_model: SentenceTransformer | None = None
        self._ollama_client: httpx.AsyncClient | None = None

    def _load_st_model(self):
        if self._st_model is None:
            self._st_model = SentenceTransformer(
                "nomic-ai/nomic-embed-text-v1.5",
                trust_remote_code=True,
            )
            # Use MPS on Apple Silicon
            if torch.backends.mps.is_available():
                self._st_model.to("mps")
        return self._st_model

    async def embed_single(self, text: str) -> list[float]:
        """Single text - use Ollama (simpler, already running)."""
        # ... existing Ollama implementation
        pass

    def embed_batch_sync(self, texts: list[str]) -> list[list[float]]:
        """Batch texts - use sentence-transformers (2x faster)."""
        model = self._load_st_model()
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 100,
        )
        return embeddings.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Async wrapper for batch embedding."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embed_batch_sync, texts)
```

**Performance Gain:** 2x faster batch embeddings

---

### IMPROVEMENT-003: Use HNSW Index Exclusively

**Current Plan:** Mentions HNSW but doesn't enforce it

**Better Approach:** Mandate HNSW, document memory requirements

**Source:** [Medium Comparison](https://medium.com/@bavalpreetsinghh/pgvector-hnsw-vs-ivfflat-a-comprehensive-study-21ce0aaab931)

**Justification:**
- 15x faster queries than IVFFlat
- No rebuild needed when data changes
- Better recall for similar memory cost
- pgvector 0.8.0 has iterative scan improvements

**Implementation:**
```sql
-- Use HNSW with optimized parameters
CREATE INDEX idx_memories_embedding ON devmemory.memories
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Set search parameters for quality
SET hnsw.ef_search = 100;  -- Higher = better recall, slower
```

**Memory Impact:** ~3x more than IVFFlat, but worth it for query speed

---

### IMPROVEMENT-004: Use mxbai-rerank-large-v2 (Not base-v1)

**Current Plan:** Uses mxbai-rerank-base-v1

**Better Approach:** Use mxbai-rerank-large-v2 (current SOTA)

**Source:** [Rerankers Comparison](https://medium.com/@markshipman4273/the-best-rerankers-24d9582a3495), [ZeroEntropy Guide](https://www.zeroentropy.dev/articles/ultimate-guide-to-choosing-the-best-reranking-model-in-2025)

**Justification:**
- MXBai V2 is current open-source SOTA
- Better multilingual support
- Handles code and JSON well
- Long context window

**Implementation:**
```python
# config.py
class DevMemorySettings(BaseSettings):
    rerank_model: str = Field(
        default="mixedbread-ai/mxbai-rerank-large-v2",  # Updated
        env="DEVMEMORY_RERANK_MODEL"
    )
```

**Note:** Model is 1.5GB vs 100MB for base. Lazy load on first rerank request.

---

### IMPROVEMENT-005: FastAPI Lifespan for Resource Management

**Current Plan:** Uses global singletons

**Better Approach:** Use FastAPI lifespan context manager

**Source:** [FastAPI Docs](https://fastapi.tiangolo.com/advanced/events/), [Best Practices 2025](https://orchestrator.dev/blog/2025-1-30-fastapi-production-patterns/)

**Justification:**
- Proper startup/shutdown lifecycle
- Resources tied to app lifecycle
- Better testability
- Cleaner than global state

**Implementation:**
```python
# server.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    app.state.db = await Database.create()
    await app.state.db.connect()

    app.state.embedder = HybridEmbeddingService()

    app.state.reranker = None  # Lazy load (large model)

    yield  # App is running

    # Shutdown
    await app.state.db.disconnect()
    await app.state.embedder.close()
    if app.state.reranker:
        del app.state.reranker  # Free memory

app = FastAPI(lifespan=lifespan)

# Access in routes
@app.get("/search")
async def search(query: str, request: Request):
    db = request.app.state.db
    embedder = request.app.state.embedder
    # ...
```

---

### IMPROVEMENT-006: Alembic Async Migrations

**Current Plan:** Doesn't specify async migration support

**Better Approach:** Use async Alembic with proper naming conventions

**Source:** [Alembic Cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html), [DEV Community Guide](https://dev.to/matib/alembic-with-async-sqlalchemy-1ga)

**Implementation:**
```python
# alembic/env.py
from sqlalchemy.ext.asyncio import create_async_engine

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    """Run migrations in 'online' mode with async engine."""
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
```

**Naming Convention (Critical for autogenerate):**
```python
# models.py
from sqlalchemy import MetaData

# Consistent naming for auto-generated migrations
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=naming_convention)
```

---

### IMPROVEMENT-007: Use Instructor's Ollama Mode Correctly

**Current Plan:** Uses generic instructor.from_ollama

**Better Approach:** Use JSON mode with proper model specification

**Source:** [Instructor Docs](https://python.useinstructor.com/blog/2024/03/07/open-source-local-structured-output-pydantic-json-openai/)

**Implementation:**
```python
import instructor
from ollama import Client

# Correct initialization for Ollama
client = instructor.from_ollama(
    Client(host="http://localhost:11434"),
    mode=instructor.Mode.JSON,  # Important: use JSON mode
)

# Usage with retries
result = client.chat.completions.create(
    model="qwen2.5-coder:7b",
    messages=[{"role": "user", "content": prompt}],
    response_model=EntityExtractionResult,
    max_retries=3,  # Automatic retry on validation failure
    temperature=0.1,  # Lower = more consistent
)
```

---

## 4. Items to Remove or Simplify

### REMOVE-001: Browser Extension (Phase 1)

**Current Plan:** Includes BrowserExtension in capture layer

**Decision:** Remove from Phase 1, defer to Phase 4+

**Justification:**
- Adds significant complexity (cross-browser, security)
- Not core to MVP value proposition
- Manual capture + CLI covers most use cases
- Focus resources on core functionality

**Impact:** Reduces Phase 1 scope by ~20%

---

### REMOVE-002: Terminal ZSH Hook (Week 1)

**Current Plan:** Terminal hook for error capture in Week 1

**Decision:** Move to Week 3 or defer

**Justification:**
- Requires shell configuration (user friction)
- Error patterns vary widely
- Manual note capture works as fallback
- Focus on git capture first

**Revised Week 1:** Project setup, db, CLI, git capture only

---

### REMOVE-003: ContextLens Dashboard TUI

**Current Plan:** Rich TUI dashboard with live updates

**Decision:** Simplify to static output first

**Justification:**
- TUI adds complexity (key handling, state management)
- Static Rich tables provide same information
- Iterate to TUI in Phase 4 based on feedback

**Simplified Implementation:**
```python
# contextlens/cli.py
@app.command()
def analyze(
    query: str,
    path: Path = Path("."),
    budget: int = 100000,
):
    """Analyze context relevance for a query."""
    results = asyncio.run(_analyze(query, path, budget))

    # Static output (no TUI)
    console.print(f"\n[bold]Context Analysis: {query}[/bold]\n")

    table = Table(title=f"Files by Relevance (budget: {budget:,} tokens)")
    table.add_column("Include", width=3)
    table.add_column("File")
    table.add_column("Tokens", justify="right")
    table.add_column("Score", justify="right")

    total_included = 0
    for r in results[:30]:
        checkbox = "✓" if r.include else "✗"
        style = "green" if r.include else "dim"
        table.add_row(
            checkbox,
            r.filepath,
            f"{r.token_count:,}",
            f"{r.final_score:.2f}",
            style=style,
        )
        if r.include:
            total_included += r.token_count

    console.print(table)
    console.print(f"\n[green]Included: {total_included:,} tokens[/green]")
```

---

### REMOVE-004: Separate Database for DevMemory

**Current Plan:** Ambiguous - mentions both shared and separate DB

**Decision:** Use single database with schema separation

**Justification:**
- Single connection pool
- No sync complexity
- Shared transactions possible
- Easier backup/restore

**Implementation:**
```sql
-- Single database, multiple schemas
CREATE SCHEMA devmemory;
CREATE SCHEMA codemcp;

-- KAS tables stay in public schema
-- DevMemory tables in devmemory schema
-- CodeMCP tables in codemcp schema
```

---

### SIMPLIFY-001: Entity Types

**Current Plan:** 11 entity types

**Decision:** Reduce to 7 core types for MVP

**Current:**
```
function, class, method, package, module, file,
error_type, concept, tool, command, api_endpoint
```

**Simplified:**
```
function, class, package, error, concept, file, tool
```

**Rationale:**
- `method` → merged into `function` (add is_method flag)
- `module` → merged into `package`
- `command` → merged into `tool`
- `api_endpoint` → deferred (rare in dev memory context)

---

### SIMPLIFY-002: Relationship Types

**Current Plan:** 10 relationship types

**Decision:** Reduce to 5 for MVP

**Current:**
```
uses, fixes, causes, related_to, depends_on,
imports, extends, implements, calls, contains
```

**Simplified:**
```
uses, fixes, causes, related_to, depends_on
```

**Rationale:**
- Code-specific relationships (imports, extends, implements, calls, contains) belong in CodeMCP, not DevMemory
- DevMemory focuses on conceptual relationships

---

## 5. Expanded Technical Specifications

### 5.1 Database Connection Architecture

```python
# shared/db.py
"""Shared database infrastructure for all suite components."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from pgvector.asyncpg import register_vector

from shared.config import Settings

class DatabasePool:
    """Shared connection pool for entire suite."""

    _instance: DatabasePool | None = None

    def __init__(self, settings: Settings):
        self.settings = settings
        self._pool: asyncpg.Pool | None = None
        self._lock = asyncio.Lock()

    @classmethod
    async def get_instance(cls, settings: Settings | None = None) -> DatabasePool:
        """Get or create singleton pool."""
        if cls._instance is None:
            if settings is None:
                raise ValueError("Settings required for first initialization")
            cls._instance = cls(settings)
            await cls._instance.connect()
        return cls._instance

    async def connect(self) -> None:
        """Initialize connection pool."""
        async with self._lock:
            if self._pool is not None:
                return

            self._pool = await asyncpg.create_pool(
                self.settings.database_url,
                min_size=self.settings.db_pool_min,      # Default: 2
                max_size=self.settings.db_pool_max,      # Default: 10
                max_queries=50000,                        # Recycle after 50k queries
                max_inactive_connection_lifetime=300.0,   # 5 min idle timeout
                command_timeout=self.settings.db_timeout, # Default: 60s
                init=self._init_connection,
            )

    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        """Initialize each connection."""
        await register_vector(conn)
        # Set search path for schema isolation
        await conn.execute("SET search_path TO devmemory, codemcp, public")

    async def disconnect(self) -> None:
        """Close pool gracefully."""
        async with self._lock:
            if self._pool:
                await self._pool.close()
                self._pool = None

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Acquire connection from pool."""
        if self._pool is None:
            raise RuntimeError("Pool not initialized")
        async with self._pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Acquire connection with transaction."""
        async with self.acquire() as conn:
            async with conn.transaction():
                yield conn
```

### 5.2 Embedding Service Architecture

```python
# shared/embeddings.py
"""Hybrid embedding service optimized for different use cases."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

import httpx
import numpy as np
from sentence_transformers import SentenceTransformer

from shared.config import Settings

@dataclass
class EmbeddingResult:
    """Result of embedding operation."""
    vector: list[float]
    model: str
    dimensions: int
    tokens_used: int | None = None

class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""
    async def embed(self, text: str) -> EmbeddingResult: ...
    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]: ...

class OllamaProvider:
    """Ollama-based embeddings (good for single queries)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.settings.ollama_url,
                timeout=httpx.Timeout(30.0),
            )
        return self._client

    async def embed(self, text: str) -> EmbeddingResult:
        client = await self._get_client()
        response = await client.post(
            "/api/embeddings",
            json={"model": self.settings.embedding_model, "prompt": text},
        )
        response.raise_for_status()
        data = response.json()

        return EmbeddingResult(
            vector=data["embedding"],
            model=self.settings.embedding_model,
            dimensions=len(data["embedding"]),
        )

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """Sequential batch (Ollama doesn't support true batching)."""
        return [await self.embed(text) for text in texts]

class SentenceTransformerProvider:
    """sentence-transformers provider (faster for batches)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._model: SentenceTransformer | None = None

    def _load_model(self) -> SentenceTransformer:
        if self._model is None:
            import torch

            self._model = SentenceTransformer(
                "nomic-ai/nomic-embed-text-v1.5",
                trust_remote_code=True,
            )

            # Use MPS on Apple Silicon
            if torch.backends.mps.is_available():
                self._model.to("mps")

        return self._model

    async def embed(self, text: str) -> EmbeddingResult:
        """Single embedding (run in thread to not block)."""
        loop = asyncio.get_event_loop()
        vector = await loop.run_in_executor(
            None, self._embed_sync, text
        )
        return EmbeddingResult(
            vector=vector,
            model="nomic-embed-text-v1.5",
            dimensions=len(vector),
        )

    def _embed_sync(self, text: str) -> list[float]:
        model = self._load_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """Batch embedding (main use case)."""
        loop = asyncio.get_event_loop()
        vectors = await loop.run_in_executor(
            None, self._embed_batch_sync, texts
        )
        return [
            EmbeddingResult(
                vector=v,
                model="nomic-embed-text-v1.5",
                dimensions=len(v),
            )
            for v in vectors
        ]

    def _embed_batch_sync(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 100,
            batch_size=32,
        )
        return embeddings.tolist()

class HybridEmbeddingService:
    """
    Hybrid embedding service that routes to optimal provider.

    - Single queries: Ollama (simpler, no model loading)
    - Batch queries: sentence-transformers (2x faster)
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._ollama = OllamaProvider(settings)
        self._st: SentenceTransformerProvider | None = None

    def _get_st(self) -> SentenceTransformerProvider:
        """Lazy load sentence-transformers provider."""
        if self._st is None:
            self._st = SentenceTransformerProvider(self.settings)
        return self._st

    async def embed(self, text: str) -> EmbeddingResult:
        """Embed single text (uses Ollama)."""
        return await self._ollama.embed(text)

    async def embed_batch(
        self,
        texts: list[str],
        use_st: bool = True,
    ) -> list[EmbeddingResult]:
        """
        Embed batch of texts.

        Args:
            texts: Texts to embed
            use_st: Use sentence-transformers (faster) or Ollama

        Returns:
            List of embedding results
        """
        if use_st and len(texts) > 5:  # ST overhead only worth it for batches
            return await self._get_st().embed_batch(texts)
        return await self._ollama.embed_batch(texts)

    async def close(self) -> None:
        """Cleanup resources."""
        if self._ollama._client:
            await self._ollama._client.aclose()
```

### 5.3 Git Capture (Revised)

```python
# devmemory/capture/git.py
"""Git commit capture with macOS-optimized watching."""

from __future__ import annotations

import asyncio
import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from git import Repo
from git.exc import InvalidGitRepositoryError
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from devmemory.db.models import DevMemory
from shared.embeddings import HybridEmbeddingService

@dataclass
class CommitCapture:
    """Captured commit data."""
    sha: str
    message: str
    author: str
    timestamp: datetime
    repo_path: str
    branch: str
    files_changed: list[str]
    insertions: int
    deletions: int
    diff_summary: str

class GitHeadHandler(FileSystemEventHandler):
    """Watch .git/HEAD for branch/commit changes."""

    def __init__(
        self,
        repo_path: Path,
        on_commit: Callable[[CommitCapture], None],
    ):
        self.repo_path = repo_path
        self.on_commit = on_commit
        self._last_sha: str | None = None

        try:
            self.repo = Repo(repo_path)
            self._last_sha = self.repo.head.commit.hexsha
        except (InvalidGitRepositoryError, ValueError):
            self.repo = None

    def on_modified(self, event: FileModifiedEvent):
        """Handle HEAD file modification."""
        if event.is_directory:
            return

        # Check if HEAD or refs changed
        src = str(event.src_path)
        if "HEAD" in src or "refs/heads" in src:
            self._check_new_commit()

    def _check_new_commit(self):
        """Check if there's a new commit."""
        if not self.repo:
            return

        try:
            current_sha = self.repo.head.commit.hexsha
            if current_sha != self._last_sha:
                capture = self._capture_commit(current_sha)
                self._last_sha = current_sha
                self.on_commit(capture)
        except Exception:
            pass  # Ignore transient git states

    def _capture_commit(self, sha: str) -> CommitCapture:
        """Extract commit information."""
        commit = self.repo.commit(sha)

        # Get diff stats
        files_changed = []
        insertions = 0
        deletions = 0

        if commit.parents:
            diff = commit.diff(commit.parents[0])
            for d in diff:
                if d.a_path:
                    files_changed.append(d.a_path)
                elif d.b_path:
                    files_changed.append(d.b_path)

            stats = commit.stats.total
            insertions = stats.get("insertions", 0)
            deletions = stats.get("deletions", 0)

        # Build diff summary (truncated)
        diff_summary = self._build_diff_summary(commit, max_length=2000)

        return CommitCapture(
            sha=sha,
            message=commit.message.strip(),
            author=commit.author.name,
            timestamp=datetime.fromtimestamp(
                commit.committed_date, tz=timezone.utc
            ),
            repo_path=str(self.repo_path),
            branch=self.repo.active_branch.name if not self.repo.head.is_detached else "HEAD",
            files_changed=files_changed[:50],  # Limit
            insertions=insertions,
            deletions=deletions,
            diff_summary=diff_summary,
        )

    def _build_diff_summary(self, commit, max_length: int = 2000) -> str:
        """Build a concise diff summary."""
        lines = [
            f"Commit: {commit.hexsha[:8]}",
            f"Author: {commit.author.name}",
            f"Date: {commit.committed_datetime.isoformat()}",
            "",
            commit.message.strip(),
            "",
            "Files changed:",
        ]

        if commit.parents:
            for d in commit.diff(commit.parents[0])[:20]:
                change = d.change_type
                path = d.a_path or d.b_path
                lines.append(f"  [{change}] {path}")

        summary = "\n".join(lines)
        if len(summary) > max_length:
            summary = summary[:max_length] + "\n..."

        return summary

def create_observer() -> Observer:
    """Create platform-appropriate observer."""
    if platform.system() == "Darwin":
        # Use polling on macOS to avoid kqueue file descriptor issues
        # 5 second interval is good balance of responsiveness and efficiency
        return PollingObserver(timeout=5)
    return Observer()

class GitWatcher:
    """Watch multiple repositories for commits."""

    def __init__(
        self,
        repo_paths: list[Path],
        embedding_service: HybridEmbeddingService,
        on_memory_created: Callable[[DevMemory], None] | None = None,
    ):
        self.repo_paths = repo_paths
        self.embedding_service = embedding_service
        self.on_memory_created = on_memory_created

        self._observer = create_observer()
        self._handlers: dict[Path, GitHeadHandler] = {}
        self._commit_queue: asyncio.Queue[CommitCapture] = asyncio.Queue()
        self._running = False

    async def start(self) -> None:
        """Start watching repositories."""
        self._running = True

        # Set up handlers
        for repo_path in self.repo_paths:
            git_dir = repo_path / ".git"
            if not git_dir.exists():
                continue

            handler = GitHeadHandler(
                repo_path,
                lambda c: asyncio.create_task(self._enqueue_commit(c)),
            )
            self._observer.schedule(handler, str(git_dir), recursive=True)
            self._handlers[repo_path] = handler

        # Start observer in thread
        self._observer.start()

        # Start commit processor
        asyncio.create_task(self._process_commits())

    async def stop(self) -> None:
        """Stop watching."""
        self._running = False
        self._observer.stop()
        self._observer.join(timeout=5)

    async def _enqueue_commit(self, capture: CommitCapture) -> None:
        """Add commit to processing queue."""
        await self._commit_queue.put(capture)

    async def _process_commits(self) -> None:
        """Process commits from queue."""
        while self._running:
            try:
                capture = await asyncio.wait_for(
                    self._commit_queue.get(),
                    timeout=1.0,
                )
                await self._create_memory(capture)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                import sys
                print(f"Error processing commit: {e}", file=sys.stderr)

    async def _create_memory(self, capture: CommitCapture) -> None:
        """Create memory from captured commit."""
        content = capture.diff_summary

        # Generate embedding
        result = await self.embedding_service.embed(content)

        memory = DevMemory(
            memory_type="commit",
            title=capture.message.split("\n")[0][:100],
            content=content,
            context={
                "repo": capture.repo_path,
                "sha": capture.sha,
                "branch": capture.branch,
                "files_changed": capture.files_changed,
                "insertions": capture.insertions,
                "deletions": capture.deletions,
            },
            embedding=result.vector,
            captured_at=capture.timestamp,
        )

        if self.on_memory_created:
            self.on_memory_created(memory)
```

---

## 6. Dependency Audit

### 6.1 Package Version Analysis

| Package | Current | Latest | Action |
|---------|---------|--------|--------|
| `mcp` | 1.25.0 | 1.25.0 | ✅ Current |
| `instructor` | 1.14.1 | 1.14.1 | ✅ Current |
| `sentence-transformers` | 3.4.1 | 3.4.1 | ✅ Current |
| `asyncpg` | 0.31.0 | 0.31.0 | ✅ Current |
| `pgvector` | 0.2.4 | 0.3.6 | ⚠️ **Upgrade recommended** |
| `tree-sitter` | 0.24.0 | 0.24.0 | ✅ Current |
| `tiktoken` | 0.3.3 | 0.8.0 | ⚠️ **Upgrade recommended** |
| `alembic` | 1.18.0 | 1.18.0 | ✅ Current |
| `rerankers` | 0.10.0 | 0.10.0 | ✅ Current |

### 6.2 Recommended Upgrades

```toml
# pyproject.toml - Updated dependencies
[project]
dependencies = [
    # Core - pinned to known-good versions
    "fastapi>=0.115.0,<0.120.0",
    "uvicorn>=0.32.0",
    "typer>=0.14.0",
    "rich>=13.9.0",
    "pydantic>=2.10.0,<3.0.0",
    "pydantic-settings>=2.6.0",

    # Database - UPGRADE pgvector
    "asyncpg>=0.30.0",
    "pgvector>=0.3.6",  # Was 0.2.4
    "alembic>=1.14.0",

    # AI/ML
    "instructor>=1.7.0",
    "tiktoken>=0.8.0",  # Was 0.3.3
    "sentence-transformers>=3.4.0",
    "ollama>=0.4.0",

    # Git/Code
    "gitpython>=3.1.45",
    "watchdog>=6.0.0",
    "tree-sitter>=0.23.0",
    "tree-sitter-python>=0.23.0",
    "tree-sitter-javascript>=0.23.0",
    "tree-sitter-typescript>=0.23.0",

    # MCP
    "mcp>=1.25.0",

    # HTTP
    "httpx>=0.28.0",
]
```

### 6.3 tree-sitter Language Bindings

Already installed:
- `tree-sitter-language-pack==0.9.0` (includes many languages)

Needed for CodeMCP:
- Python: ✅ Available
- JavaScript: ✅ Available
- TypeScript: ✅ Available
- C#: ✅ Available (tree-sitter-c-sharp)
- YAML: ✅ Available

---

## 7. KAS Code Reuse Analysis

### 7.1 Modules to Directly Import

| KAS Module | Location | Reuse Strategy |
|------------|----------|----------------|
| `db.py` | `knowledge.db` | **Import Database class, extend with DevMemory methods** |
| `embeddings.py` | `knowledge.embeddings` | **Import EmbeddingService, use as base** |
| `search.py` | `knowledge.search` | **Import rrf_fusion, adapt for DevMemory** |
| `config.py` | `knowledge.config` | **Import Settings pattern, extend** |
| `reranker.py` | `knowledge.reranker` | **Import LocalReranker directly** |

### 7.2 Code to Copy and Modify

| KAS Code | Purpose | Modifications Needed |
|----------|---------|---------------------|
| `rrf_fusion()` | RRF algorithm | Change field names for DevMemory schema |
| `Database.bm25_search()` | BM25 query | Adapt for devmemory.memories table |
| `Database.vector_search()` | Vector query | Adapt for devmemory.memories table |

### 7.3 Implementation Strategy

```python
# shared/kas_bridge.py
"""Bridge to reuse KAS infrastructure."""

import sys
from pathlib import Path

# Add KAS to path
KAS_PATH = Path.home() / "claude-code/personal/knowledge-activation-system/src"
if str(KAS_PATH) not in sys.path:
    sys.path.insert(0, str(KAS_PATH))

# Re-export KAS modules
from knowledge.db import Database as KASDatabase
from knowledge.embeddings import EmbeddingService as KASEmbeddingService
from knowledge.search import rrf_fusion
from knowledge.reranker import LocalReranker
from knowledge.config import Settings as KASSettings

__all__ = [
    "KASDatabase",
    "KASEmbeddingService",
    "rrf_fusion",
    "LocalReranker",
    "KASSettings",
]
```

### 7.4 Shared vs Separate Installation

**Recommended: Shared Installation**

```bash
# Install dev-memory-suite in same venv as KAS
cd ~/claude-code/personal/knowledge-activation-system
source .venv/bin/activate

# Install dev-memory-suite as editable
cd ~/claude-code/ai-tools/dev-memory-suite
pip install -e .
```

This allows:
- Direct imports from `knowledge.*`
- Shared dependencies (no version conflicts)
- Single virtual environment
- Easier development

---

## 8. Revised Architecture

### 8.1 Updated System Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              Claude Code                                    │
│                        (Primary User Interface)                             │
└────────────────────────────────────┬───────────────────────────────────────┘
                                     │ MCP Protocol (stdio)
            ┌────────────────────────┼────────────────────────┐
            │                        │                        │
            ▼                        ▼                        ▼
    ┌───────────────┐        ┌───────────────┐        ┌───────────────┐
    │   DevMemory   │        │    CodeMCP    │        │  ContextLens  │
    │   MCP Server  │◄──────►│   MCP Server  │◄──────►│   MCP Server  │
    └───────┬───────┘        └───────┬───────┘        └───────┬───────┘
            │                        │                        │
            └────────────────────────┼────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │          SHARED CORE            │
                    │                                 │
                    │  ┌─────────────────────────┐   │
                    │  │   KAS Bridge Module     │   │
                    │  │   (knowledge.*)         │   │
                    │  └─────────────────────────┘   │
                    │                                 │
                    │  ┌─────────────────────────┐   │
                    │  │  Hybrid Embedding Svc   │   │
                    │  │  (Ollama + ST)          │   │
                    │  └─────────────────────────┘   │
                    │                                 │
                    │  ┌─────────────────────────┐   │
                    │  │   Database Pool         │   │
                    │  │   (asyncpg singleton)   │   │
                    │  └─────────────────────────┘   │
                    │                                 │
                    └────────────────┬────────────────┘
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        │                            │                            │
        ▼                            ▼                            ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│  PostgreSQL   │          │    Ollama     │          │ Git Repos     │
│  (knowledge-  │          │  (Embeddings  │          │ ~/claude-code │
│   db:5432)    │          │   + LLMs)     │          │               │
│               │          │               │          │               │
│ Schemas:      │          │ Models:       │          │ Watched via:  │
│ - public (KAS)│          │ - nomic-embed │          │ - PollingObs  │
│ - devmemory   │          │ - qwen2.5     │          │   (macOS)     │
│ - codemcp     │          │ - deepseek-r1 │          │ - .git/HEAD   │
└───────────────┘          └───────────────┘          └───────────────┘
```

### 8.2 Module Dependencies

```
dev-memory-suite/
├── shared/                    # SHARED across all components
│   ├── __init__.py
│   ├── config.py             # Unified settings
│   ├── db.py                 # Database pool (extends KAS)
│   ├── embeddings.py         # Hybrid embedding service
│   ├── kas_bridge.py         # KAS import bridge
│   └── logging.py            # Structured logging
│
├── devmemory/                 # PHASE 1
│   ├── depends on: shared/*
│   └── depends on: knowledge.reranker (via kas_bridge)
│
├── codemcp/                   # PHASE 2
│   ├── depends on: shared/*
│   └── depends on: devmemory.search (for memory context)
│
└── contextlens/               # PHASE 3
    ├── depends on: shared/*
    ├── depends on: devmemory.search
    └── depends on: codemcp.search
```

---

## 9. Updated Task Breakdown

### Phase 1: DevMemory (12 days, revised from 14)

#### Week 1: Foundation (Days 1-7)

| Day | Tasks | Hours | Dependencies |
|-----|-------|-------|--------------|
| 1 | Project setup: pyproject.toml, directory structure, shared/ module | 4h | None |
| 1 | KAS bridge: Import and verify KAS modules work | 2h | Day 1 |
| 2 | Database schema: devmemory schema, Alembic init, migrations | 6h | Day 1 |
| 3 | Shared db.py: Extend KASDatabase, connection pool | 4h | Day 2 |
| 3 | Shared embeddings.py: HybridEmbeddingService | 4h | Day 1 |
| 4 | DevMemory models: Pydantic models, dataclasses | 3h | Day 2 |
| 4 | DevMemory db queries: CRUD operations | 4h | Day 3 |
| 5 | CLI skeleton: Typer app, devmemory command group | 3h | Day 1 |
| 5 | Manual capture: `devmemory add` command | 3h | Day 4 |
| 6 | GitWatcher: PollingObserver, HEAD watching | 6h | Day 4 |
| 7 | Basic search: Adapt KAS hybrid search for DevMemory | 5h | Day 4 |
| 7 | Search CLI: `devmemory search` command | 2h | Day 7 |

**Week 1 Deliverables:**
- Working CLI with `add` and `search` commands
- Git commit auto-capture (polling)
- Database with proper schema
- Hybrid search functional

#### Week 2: Entity Extraction & Polish (Days 8-12)

| Day | Tasks | Hours | Dependencies |
|-----|-------|-------|--------------|
| 8 | Entity extraction: Instructor + Ollama integration | 6h | Week 1 |
| 9 | Entity storage: Dedupe logic, confidence thresholds | 5h | Day 8 |
| 9 | Entity CLI: `devmemory entities list/related` | 2h | Day 9 |
| 10 | Temporal filters: "last week", "last month" parsing | 3h | Day 7 |
| 10 | Search enhancements: `--since`, `--type` flags | 2h | Day 10 |
| 10 | Reranking integration: Use KAS LocalReranker | 2h | Day 7 |
| 11 | MCP server: Tool definitions, search_memory, add_memory | 6h | Day 10 |
| 12 | Testing: Unit tests, integration tests (80% coverage) | 6h | Day 11 |
| 12 | Documentation: CLI help, README update | 2h | Day 12 |

**Week 2 Deliverables:**
- Entity extraction working
- Temporal queries working
- MCP server ready
- 80% test coverage

### Phase 2: CodeMCP (8 days, revised from 10)

#### Week 1: Indexing (Days 1-4)

| Day | Tasks | Hours | Dependencies |
|-----|-------|-------|--------------|
| 1 | tree-sitter setup: Parser initialization, Python support | 4h | Phase 1 |
| 1 | Symbol extraction: Functions, classes from Python | 4h | Day 1 |
| 2 | TypeScript/JS parsers: Add language support | 4h | Day 1 |
| 2 | Database schema: code_repos, code_files, code_symbols | 3h | Phase 1 |
| 3 | Batch indexer: Repo scanning, streaming processing | 6h | Day 2 |
| 4 | Embedding generation: Symbol embeddings | 4h | Day 3 |
| 4 | Incremental indexing: File hash comparison | 3h | Day 3 |

#### Week 2: Search & MCP (Days 5-8)

| Day | Tasks | Hours | Dependencies |
|-----|-------|-------|--------------|
| 5 | Semantic search: Vector search on symbols | 5h | Day 4 |
| 5 | search_code tool: MCP implementation | 3h | Day 5 |
| 6 | explain_function tool: Symbol lookup + source | 4h | Day 5 |
| 6 | find_related tool: Dependency-based relations | 4h | Day 5 |
| 7 | get_architecture tool: Repo summary | 4h | Day 6 |
| 7 | DevMemory integration: Historical context in explain | 3h | Day 6 |
| 8 | Testing: Parser tests, search tests | 4h | Day 7 |
| 8 | MCP config: Claude.json setup, documentation | 2h | Day 7 |

### Phase 3: ContextLens (6 days, revised from 7)

| Day | Tasks | Hours | Dependencies |
|-----|-------|-------|--------------|
| 1 | Token counting: tiktoken integration | 3h | Phase 2 |
| 1 | File discovery: Glob patterns, gitignore respect | 3h | Day 1 |
| 2 | Relevance scoring: Embedding similarity | 4h | Day 1 |
| 2 | Recency scoring: File modification times | 2h | Day 2 |
| 3 | Combined scoring: Weighted combination | 3h | Day 2 |
| 3 | DevMemory signals: Historical relevance | 3h | Day 2 |
| 4 | CLI: `contextlens analyze` command | 4h | Day 3 |
| 4 | Optimization suggestions: Token budget fitting | 3h | Day 3 |
| 5 | MCP server: Tools for Claude Code integration | 5h | Day 4 |
| 6 | Testing and documentation | 5h | Day 5 |

### Phase 4: Integration (3 days)

| Day | Tasks | Hours | Dependencies |
|-----|-------|-------|--------------|
| 1 | End-to-end testing: All three tools together | 5h | Phase 3 |
| 1 | Performance profiling: Identify bottlenecks | 3h | Day 1 |
| 2 | Bug fixes from testing | 4h | Day 1 |
| 2 | MCP config finalization: All servers in claude.json | 2h | Day 2 |
| 3 | Install script: One-command setup | 3h | Day 2 |
| 3 | Final documentation: README, CLAUDE.md updates | 3h | Day 3 |

---

## Summary of Changes

### Added
- Risk analysis with mitigations (6 risks identified)
- Improvement recommendations (7 improvements)
- KAS code reuse strategy
- Package version audit
- Expanded technical specifications
- Revised timeline (29 days vs 34 days original)

### Modified
- Watchdog → PollingObserver for macOS
- Embedding service → Hybrid (Ollama + sentence-transformers)
- Database → Single database with schema separation
- Reranker → mxbai-rerank-large-v2 (upgraded)
- Entity types → Reduced from 11 to 7
- Relationship types → Reduced from 10 to 5

### Removed
- Browser extension (Phase 1) → Deferred
- Terminal ZSH hook (Week 1) → Moved to Week 3
- ContextLens TUI dashboard → Simplified to static output
- Separate database → Consolidated

### Key Decisions

1. **Use KAS code directly** - Don't reinvent the wheel
2. **Single database, multiple schemas** - Simpler architecture
3. **PollingObserver on macOS** - Avoid kqueue issues
4. **Hybrid embeddings** - Ollama for single, ST for batch
5. **HNSW only** - Worth the memory for speed
6. **Defer browser extension** - Focus on core value

---

**Next Steps:**
1. Review this document
2. Approve modifications
3. Begin Phase 1, Day 1 implementation

