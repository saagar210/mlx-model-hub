# Developer Memory & Context Suite
# Complete Implementation Plan (A to Z)

**Version:** 1.0.0
**Created:** January 12, 2026
**Status:** Ready for Implementation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Environment Inventory](#2-environment-inventory)
3. [Architecture Overview](#3-architecture-overview)
4. [Phase 1: DevMemory](#4-phase-1-devmemory)
5. [Phase 2: CodeMCP](#5-phase-2-codemcp)
6. [Phase 3: ContextLens](#6-phase-3-contextlens)
7. [Phase 4: Integration & Polish](#7-phase-4-integration--polish)
8. [Testing Strategy](#8-testing-strategy)
9. [Deployment & Operations](#9-deployment--operations)
10. [Task Breakdown](#10-task-breakdown)

---

## 1. Executive Summary

### Vision
Transform development knowledge capture from passive (forgetting what you learned) to active (instantly recalling "how did I fix X?"). Three interconnected tools that leverage your existing Knowledge Activation System.

### The Suite

| Tool | Purpose | Core Technology |
|------|---------|-----------------|
| **DevMemory** | Capture & retrieve dev knowledge | PostgreSQL + pgvector + Entity Extraction |
| **CodeMCP** | Semantic codebase understanding | tree-sitter + MCP SDK + Embeddings |
| **ContextLens** | Smart context optimization | tiktoken + Relevance Scoring |

### Key Differentiators
- **Builds on KAS**: 70% infrastructure already exists (PostgreSQL, pgvector, hybrid search)
- **Local-first**: All data stays on your machine (Ollama models)
- **MCP Native**: Direct integration with Claude Code
- **Developer-specific**: Not generic knowledge management

### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| "How did I fix X?" relevance | 90%+ | Top-3 result accuracy |
| Search latency | <500ms p95 | End-to-end query time |
| Context token savings | 30%+ | Before/after comparison |
| Code search precision | 85%+ | Manual evaluation |
| Test coverage | 80%+ | pytest-cov |

---

## 2. Environment Inventory

### 2.1 Available Ollama Models

| Model | Size | Use Case |
|-------|------|----------|
| `nomic-embed-text:latest` | 274MB | **Primary embeddings** (768 dims) |
| `qwen2.5-coder:7b` | 4.7GB | **Code understanding & entity extraction** |
| `qwen2.5:7b` | 4.7GB | General reasoning, fallback |
| `deepseek-r1:14b` | 9.0GB | Complex reasoning (when needed) |
| `llama3.2-vision:11b` | 7.8GB | Image/screenshot understanding |

### 2.2 Existing MCP Servers

```json
{
  "taskmaster-ai": "Task management",
  "context7": "Documentation lookup",
  "playwright": "Browser automation",
  "github": "GitHub integration",
  "fetch": "HTTP fetching",
  "unified-mlx": "MLX inference",
  "postgres": "Direct DB queries",
  "memory": "Knowledge graph"
}
```

### 2.3 Docker Infrastructure

| Container | Image | Purpose |
|-----------|-------|---------|
| `knowledge-db` | `timescale/timescaledb-ha:pg16` | **KAS database** (pgvector enabled) |
| `mlx-hub-postgres` | `postgres:17-alpine` | MLX Hub data |
| `mlx-hub-mlflow` | `ghcr.io/mlflow/mlflow:v2.19.0` | Experiment tracking |

### 2.4 Key Python Packages (Already Installed)

```
# Core AI/ML
instructor==1.14.1        # Structured LLM outputs
llama-index==0.14.12      # RAG framework
sentence-transformers==3.4.1  # Local embeddings
rerankers==0.10.0         # Cross-encoder reranking
spacy==3.8.11             # NLP/NER

# Database
asyncpg                   # Async PostgreSQL
pgvector                  # Vector operations

# Development
mcp==1.25.0               # MCP SDK
GitPython==3.1.45         # Git operations
watchdog==6.0.0           # File system watching
typer, rich               # CLI framework
fastapi, uvicorn          # API server
```

### 2.5 Local Resources

| Resource | Location | Notes |
|----------|----------|-------|
| Obsidian Vault | `~/Obsidian/` | Existing knowledge base |
| Claude Code Projects | `~/claude-code/` | All repos to index |
| KAS Codebase | `~/claude-code/personal/knowledge-activation-system/` | Foundation code |

---

## 3. Architecture Overview

### 3.1 System Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           Claude Code                                      │
│                    (Primary User Interface)                                │
└─────────────────────────────┬────────────────────────────────────────────┘
                              │ MCP Protocol (stdio)
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│   DevMemory   │     │    CodeMCP    │     │  ContextLens  │
│   MCP Server  │◄───►│   MCP Server  │◄───►│   MCP Server  │
└───────┬───────┘     └───────┬───────┘     └───────┬───────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   Shared Core   │
                    │  - Database     │
                    │  - Embeddings   │
                    │  - Config       │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  PostgreSQL   │    │    Ollama     │    │  File System  │
│  + pgvector   │    │   (Local)     │    │   Watchers    │
└───────────────┘    └───────────────┘    └───────────────┘
```

### 3.2 Data Flow

```
You Code
    │
    ├──► Git Commit ──► GitWatcher ──► DevMemory DB
    │
    ├──► Terminal Error ──► ZSH Hook ──► DevMemory DB
    │
    ├──► Claude Chat ──► Export ──► ConversationImporter ──► DevMemory DB
    │
    └──► Manual Note ──► CLI ──► DevMemory DB
                                      │
                                      ▼
                              Entity Extraction
                              (qwen2.5-coder)
                                      │
                                      ▼
                              Knowledge Graph
                              (entities + relations)
                                      │
    Query: "How did I fix X?" ────────┘
                                      │
                                      ▼
                              Hybrid Search
                              (BM25 + Vector + RRF)
                                      │
                                      ▼
                              Reranking
                              (cross-encoder)
                                      │
                                      ▼
                              Results + Context
```

### 3.3 Database Schema (Complete)

```sql
-- =============================================================================
-- DEVMEMORY SCHEMA
-- =============================================================================

-- Extension requirements (already in KAS)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For fuzzy text search

-- Developer memories
CREATE TABLE dev_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Classification
    memory_type VARCHAR(50) NOT NULL CHECK (memory_type IN (
        'commit', 'error', 'note', 'conversation', 'doc_visit', 'search'
    )),

    -- Content
    title TEXT,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,  -- SHA256 for deduplication

    -- Context (flexible JSON)
    context JSONB DEFAULT '{}' CHECK (jsonb_typeof(context) = 'object'),
    -- Typical keys:
    --   commit: {repo, sha, branch, files_changed, diff_summary}
    --   error: {command, exit_code, error_type, stack_trace}
    --   note: {tags, related_files}
    --   conversation: {model, message_count, export_source}
    --   doc_visit: {url, domain, page_title}

    -- Embedding
    embedding vector(768),
    embedding_model TEXT DEFAULT 'nomic-embed-text:v1.5',

    -- Metadata
    tags TEXT[] DEFAULT '{}',
    source_url TEXT,
    source_file TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    captured_at TIMESTAMPTZ,  -- When the event actually occurred
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Full-text search
    fts_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(content, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(array_to_string(tags, ' '), '')), 'C')
    ) STORED,

    -- Constraints
    CONSTRAINT unique_content_hash UNIQUE (content_hash)
);

-- Indexes for dev_memories
CREATE INDEX idx_memories_type ON dev_memories(memory_type);
CREATE INDEX idx_memories_tags ON dev_memories USING GIN(tags);
CREATE INDEX idx_memories_context ON dev_memories USING GIN(context jsonb_path_ops);
CREATE INDEX idx_memories_fts ON dev_memories USING GIN(fts_vector);
CREATE INDEX idx_memories_embedding ON dev_memories USING hnsw(embedding vector_cosine_ops);
CREATE INDEX idx_memories_captured_at ON dev_memories(captured_at DESC);
CREATE INDEX idx_memories_source_file ON dev_memories(source_file) WHERE source_file IS NOT NULL;

-- Extracted entities
CREATE TABLE dev_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Classification
    entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN (
        'function', 'class', 'method', 'package', 'module', 'file',
        'error_type', 'concept', 'tool', 'command', 'api_endpoint'
    )),

    -- Identity
    name TEXT NOT NULL,
    qualified_name TEXT,  -- e.g., "module.class.method"
    description TEXT,

    -- Embedding for similarity
    embedding vector(768),

    -- Statistics
    mention_count INTEGER DEFAULT 1,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),

    -- Metadata
    metadata JSONB DEFAULT '{}',

    CONSTRAINT unique_entity UNIQUE (entity_type, name)
);

-- Indexes for entities
CREATE INDEX idx_entities_type ON dev_entities(entity_type);
CREATE INDEX idx_entities_name_trgm ON dev_entities USING GIN(name gin_trgm_ops);
CREATE INDEX idx_entities_embedding ON dev_entities USING hnsw(embedding vector_cosine_ops);

-- Memory-Entity links (many-to-many)
CREATE TABLE dev_memory_entities (
    memory_id UUID REFERENCES dev_memories(id) ON DELETE CASCADE,
    entity_id UUID REFERENCES dev_entities(id) ON DELETE CASCADE,

    -- Role in the memory
    role VARCHAR(50) CHECK (role IN (
        'subject', 'fixed', 'caused', 'used', 'mentioned', 'created', 'modified'
    )),

    -- Context of mention
    context_snippet TEXT,
    confidence FLOAT DEFAULT 0.8,

    PRIMARY KEY (memory_id, entity_id, role)
);

CREATE INDEX idx_me_memory ON dev_memory_entities(memory_id);
CREATE INDEX idx_me_entity ON dev_memory_entities(entity_id);

-- Entity relationships
CREATE TABLE dev_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_entity_id UUID REFERENCES dev_entities(id) ON DELETE CASCADE,
    to_entity_id UUID REFERENCES dev_entities(id) ON DELETE CASCADE,

    -- Relationship type
    relationship_type VARCHAR(50) NOT NULL CHECK (relationship_type IN (
        'uses', 'fixes', 'causes', 'related_to', 'depends_on',
        'imports', 'extends', 'implements', 'calls', 'contains'
    )),

    -- Strength (0-1)
    strength FLOAT DEFAULT 0.5,
    evidence_count INTEGER DEFAULT 1,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_relationship UNIQUE (from_entity_id, to_entity_id, relationship_type)
);

CREATE INDEX idx_rel_from ON dev_relationships(from_entity_id);
CREATE INDEX idx_rel_to ON dev_relationships(to_entity_id);
CREATE INDEX idx_rel_type ON dev_relationships(relationship_type);

-- =============================================================================
-- CODEMCP SCHEMA
-- =============================================================================

-- Indexed repositories
CREATE TABLE code_repos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Location
    path TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,

    -- Git info
    default_branch TEXT DEFAULT 'main',
    remote_url TEXT,

    -- Indexing state
    last_indexed TIMESTAMPTZ,
    last_commit_sha TEXT,
    index_status VARCHAR(20) DEFAULT 'pending' CHECK (index_status IN (
        'pending', 'indexing', 'complete', 'failed', 'stale'
    )),

    -- Statistics
    file_count INTEGER DEFAULT 0,
    symbol_count INTEGER DEFAULT 0,

    -- Configuration
    config JSONB DEFAULT '{}',  -- {ignore_patterns, languages, etc.}

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_repos_status ON code_repos(index_status);
CREATE INDEX idx_repos_path ON code_repos(path);

-- Indexed files
CREATE TABLE code_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id UUID REFERENCES code_repos(id) ON DELETE CASCADE,

    -- File info
    filepath TEXT NOT NULL,  -- Relative to repo root
    language TEXT,           -- 'python', 'typescript', 'javascript', etc.

    -- Content tracking
    content_hash TEXT NOT NULL,
    file_size INTEGER,
    line_count INTEGER,

    -- Timestamps
    last_modified TIMESTAMPTZ,
    indexed_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_file UNIQUE (repo_id, filepath)
);

CREATE INDEX idx_files_repo ON code_files(repo_id);
CREATE INDEX idx_files_language ON code_files(language);
CREATE INDEX idx_files_path ON code_files(filepath);

-- Code symbols (functions, classes, methods)
CREATE TABLE code_symbols (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID REFERENCES code_files(id) ON DELETE CASCADE,

    -- Symbol identity
    symbol_type VARCHAR(50) NOT NULL CHECK (symbol_type IN (
        'function', 'class', 'method', 'variable', 'constant',
        'interface', 'type', 'enum', 'module', 'decorator'
    )),
    name TEXT NOT NULL,
    qualified_name TEXT,  -- Full path: module.class.method

    -- Location
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    start_col INTEGER,
    end_col INTEGER,

    -- Content
    signature TEXT,       -- Function signature with types
    docstring TEXT,
    body_preview TEXT,    -- First 500 chars of body

    -- AST info
    ast_node_type TEXT,   -- tree-sitter node type
    ast_hash TEXT,        -- For change detection

    -- Embedding
    embedding vector(768),

    -- Metadata
    is_exported BOOLEAN DEFAULT true,
    is_async BOOLEAN DEFAULT false,
    decorators TEXT[],
    parameters JSONB,     -- [{name, type, default}, ...]
    return_type TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_symbols_file ON code_symbols(file_id);
CREATE INDEX idx_symbols_type ON code_symbols(symbol_type);
CREATE INDEX idx_symbols_name ON code_symbols(name);
CREATE INDEX idx_symbols_qualified ON code_symbols(qualified_name);
CREATE INDEX idx_symbols_embedding ON code_symbols USING hnsw(embedding vector_cosine_ops);

-- Import/dependency graph
CREATE TABLE code_dependencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- From symbol/file
    from_file_id UUID REFERENCES code_files(id) ON DELETE CASCADE,
    from_symbol_id UUID REFERENCES code_symbols(id) ON DELETE CASCADE,

    -- To symbol/file
    to_file_id UUID REFERENCES code_files(id) ON DELETE CASCADE,
    to_symbol_id UUID REFERENCES code_symbols(id) ON DELETE CASCADE,

    -- External reference (for external packages)
    external_module TEXT,
    external_symbol TEXT,

    -- Dependency type
    dependency_type VARCHAR(50) NOT NULL CHECK (dependency_type IN (
        'imports', 'calls', 'inherits', 'implements', 'uses_type',
        'decorates', 'instantiates', 'references'
    )),

    -- Location of reference
    line_number INTEGER,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_dependency CHECK (
        (from_file_id IS NOT NULL OR from_symbol_id IS NOT NULL) AND
        (to_file_id IS NOT NULL OR to_symbol_id IS NOT NULL OR external_module IS NOT NULL)
    )
);

CREATE INDEX idx_deps_from_file ON code_dependencies(from_file_id);
CREATE INDEX idx_deps_from_symbol ON code_dependencies(from_symbol_id);
CREATE INDEX idx_deps_to_file ON code_dependencies(to_file_id);
CREATE INDEX idx_deps_to_symbol ON code_dependencies(to_symbol_id);
CREATE INDEX idx_deps_external ON code_dependencies(external_module);

-- =============================================================================
-- CONTEXTLENS SCHEMA
-- =============================================================================

-- Context sessions (for tracking optimization history)
CREATE TABLE context_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Session info
    query TEXT,
    initial_token_count INTEGER,
    optimized_token_count INTEGER,

    -- Files considered
    files_considered JSONB,   -- [{path, tokens, relevance, included}, ...]

    -- Optimization decisions
    decisions JSONB,          -- [{action, reason, tokens_saved}, ...]

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- File relevance cache
CREATE TABLE context_file_relevance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- File
    filepath TEXT NOT NULL,
    repo_path TEXT,

    -- Query
    query_embedding vector(768),

    -- Scores
    embedding_similarity FLOAT,
    recency_score FLOAT,
    dependency_score FLOAT,
    devmemory_score FLOAT,
    final_score FLOAT,

    -- Token info
    token_count INTEGER,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '1 hour'
);

CREATE INDEX idx_relevance_filepath ON context_file_relevance(filepath);
CREATE INDEX idx_relevance_expires ON context_file_relevance(expires_at);

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Update timestamps trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables
CREATE TRIGGER update_memories_timestamp BEFORE UPDATE ON dev_memories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_entities_timestamp BEFORE UPDATE ON dev_entities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_repos_timestamp BEFORE UPDATE ON code_repos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_symbols_timestamp BEFORE UPDATE ON code_symbols
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Hybrid search function (BM25 + Vector with RRF)
CREATE OR REPLACE FUNCTION search_memories(
    query_text TEXT,
    query_embedding vector(768),
    limit_count INTEGER DEFAULT 10,
    memory_types TEXT[] DEFAULT NULL,
    since_date TIMESTAMPTZ DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    memory_type VARCHAR(50),
    title TEXT,
    content TEXT,
    context JSONB,
    tags TEXT[],
    captured_at TIMESTAMPTZ,
    bm25_rank FLOAT,
    vector_rank FLOAT,
    rrf_score FLOAT
) AS $$
WITH bm25_results AS (
    SELECT
        m.id,
        ts_rank_cd(m.fts_vector, plainto_tsquery('english', query_text)) AS rank,
        ROW_NUMBER() OVER (ORDER BY ts_rank_cd(m.fts_vector, plainto_tsquery('english', query_text)) DESC) AS row_num
    FROM dev_memories m
    WHERE m.fts_vector @@ plainto_tsquery('english', query_text)
        AND (memory_types IS NULL OR m.memory_type = ANY(memory_types))
        AND (since_date IS NULL OR m.captured_at >= since_date)
    ORDER BY rank DESC
    LIMIT 50
),
vector_results AS (
    SELECT
        m.id,
        1 - (m.embedding <=> query_embedding) AS rank,
        ROW_NUMBER() OVER (ORDER BY m.embedding <=> query_embedding) AS row_num
    FROM dev_memories m
    WHERE m.embedding IS NOT NULL
        AND (memory_types IS NULL OR m.memory_type = ANY(memory_types))
        AND (since_date IS NULL OR m.captured_at >= since_date)
    ORDER BY m.embedding <=> query_embedding
    LIMIT 50
),
rrf_combined AS (
    SELECT
        COALESCE(b.id, v.id) AS id,
        COALESCE(b.rank, 0) AS bm25_rank,
        COALESCE(v.rank, 0) AS vector_rank,
        COALESCE(1.0 / (60 + b.row_num), 0) + COALESCE(1.0 / (60 + v.row_num), 0) AS rrf_score
    FROM bm25_results b
    FULL OUTER JOIN vector_results v ON b.id = v.id
)
SELECT
    m.id,
    m.memory_type,
    m.title,
    m.content,
    m.context,
    m.tags,
    m.captured_at,
    r.bm25_rank,
    r.vector_rank,
    r.rrf_score
FROM rrf_combined r
JOIN dev_memories m ON r.id = m.id
ORDER BY r.rrf_score DESC
LIMIT limit_count;
$$ LANGUAGE SQL;
```

---

## 4. Phase 1: DevMemory

### 4.1 Project Structure

```
devmemory/
├── __init__.py
├── __main__.py                 # Entry point: python -m devmemory
├── cli.py                      # Typer CLI application
├── server.py                   # FastAPI server
├── mcp_server.py               # MCP server wrapper
├── config.py                   # Configuration management
│
├── db/
│   ├── __init__.py
│   ├── connection.py           # Database connection pool
│   ├── models.py               # SQLAlchemy ORM models
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 001_initial.py
│   └── queries.py              # Raw SQL queries
│
├── capture/
│   ├── __init__.py
│   ├── base.py                 # Abstract base capturer
│   ├── git.py                  # GitWatcher (file system + gitpython)
│   ├── terminal.py             # ZSH hook integration
│   ├── conversation.py         # Claude export importer
│   └── manual.py               # CLI note capture
│
├── processing/
│   ├── __init__.py
│   ├── chunker.py              # Semantic chunking
│   ├── embeddings.py           # Embedding generation (Ollama)
│   ├── entities.py             # Entity extraction (Instructor + LLM)
│   └── relationships.py        # Relationship inference
│
├── search/
│   ├── __init__.py
│   ├── hybrid.py               # Hybrid search (BM25 + Vector + RRF)
│   ├── temporal.py             # Temporal filtering
│   ├── entity_search.py        # Entity-based queries
│   └── reranker.py             # Cross-encoder reranking
│
└── tests/
    ├── __init__.py
    ├── conftest.py             # Pytest fixtures
    ├── test_capture/
    ├── test_processing/
    └── test_search/
```

### 4.2 Core Components

#### 4.2.1 Configuration (`config.py`)

```python
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path

class DevMemorySettings(BaseSettings):
    """DevMemory configuration with environment variable support."""

    # Database
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/devmemory",
        env="DEVMEMORY_DATABASE_URL"
    )

    # Ollama
    ollama_url: str = Field(default="http://localhost:11434", env="OLLAMA_URL")
    embedding_model: str = Field(default="nomic-embed-text:v1.5", env="EMBEDDING_MODEL")
    entity_model: str = Field(default="qwen2.5-coder:7b", env="ENTITY_MODEL")

    # Git watching
    watched_repos: list[str] = Field(
        default_factory=lambda: [str(Path.home() / "claude-code")],
        env="DEVMEMORY_WATCHED_REPOS"
    )

    # Search
    default_search_limit: int = Field(default=10, env="DEVMEMORY_SEARCH_LIMIT")
    rerank_enabled: bool = Field(default=True, env="DEVMEMORY_RERANK")
    rerank_model: str = Field(
        default="mixedbread-ai/mxbai-rerank-base-v1",
        env="DEVMEMORY_RERANK_MODEL"
    )

    # Processing
    chunk_size: int = Field(default=512, env="DEVMEMORY_CHUNK_SIZE")
    chunk_overlap: int = Field(default=50, env="DEVMEMORY_CHUNK_OVERLAP")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = DevMemorySettings()
```

#### 4.2.2 Entity Extraction (`processing/entities.py`)

```python
"""Entity extraction using Instructor + Ollama."""
from __future__ import annotations

import instructor
from ollama import Client
from pydantic import BaseModel, Field
from typing import Literal

class ExtractedEntity(BaseModel):
    """A single extracted entity."""
    name: str = Field(description="The entity name (function, package, error, etc.)")
    entity_type: Literal[
        "function", "class", "method", "package", "module", "file",
        "error_type", "concept", "tool", "command", "api_endpoint"
    ]
    description: str | None = Field(
        default=None,
        description="Brief description of what this entity is/does"
    )
    role: Literal["subject", "fixed", "caused", "used", "mentioned", "created", "modified"] = Field(
        default="mentioned",
        description="Role this entity plays in the memory"
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0, le=1.0,
        description="Confidence in extraction accuracy"
    )

class EntityExtractionResult(BaseModel):
    """Result of entity extraction from a memory."""
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[tuple[str, str, str]] = Field(
        default_factory=list,
        description="List of (from_entity, relationship_type, to_entity) tuples"
    )

class EntityExtractor:
    """Extract entities from development memories using Ollama."""

    def __init__(self, model: str = "qwen2.5-coder:7b", ollama_url: str = "http://localhost:11434"):
        self.client = instructor.from_ollama(
            Client(host=ollama_url),
            mode=instructor.Mode.JSON,
        )
        self.model = model

    async def extract(self, content: str, memory_type: str, context: dict) -> EntityExtractionResult:
        """Extract entities from memory content."""

        prompt = f"""Analyze this {memory_type} and extract relevant developer entities.

Content:
{content}

Context:
{context}

Extract:
1. Functions, classes, methods mentioned
2. Packages/libraries used or discussed
3. Error types if any
4. Commands or tools used
5. Concepts being learned or applied

For each entity, identify its role:
- "subject": Main topic of the memory
- "fixed": Something that was fixed/resolved
- "caused": Something that caused an issue
- "used": A tool/package used to accomplish something
- "mentioned": Just mentioned, not central
- "created": Something new that was created
- "modified": Something that was changed

Also identify relationships between entities (e.g., "FastAPI uses Pydantic")."""

        result = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_model=EntityExtractionResult,
        )

        return result
```

#### 4.2.3 Git Watcher (`capture/git.py`)

```python
"""Watch git repositories for commits and capture them as memories."""
from __future__ import annotations

import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import AsyncGenerator

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from git import Repo
from git.exc import InvalidGitRepositoryError

from devmemory.db.models import DevMemory
from devmemory.processing.embeddings import EmbeddingService
from devmemory.processing.entities import EntityExtractor

class GitCommitHandler(FileSystemEventHandler):
    """Handle .git directory changes to detect new commits."""

    def __init__(self, repo_path: Path, callback):
        self.repo_path = repo_path
        self.callback = callback
        self.last_head = None
        try:
            self.repo = Repo(repo_path)
            self.last_head = self.repo.head.commit.hexsha
        except InvalidGitRepositoryError:
            self.repo = None

    def on_modified(self, event: FileModifiedEvent):
        if not event.is_directory and "HEAD" in event.src_path:
            self._check_for_new_commits()

    def _check_for_new_commits(self):
        if not self.repo:
            return

        try:
            current_head = self.repo.head.commit.hexsha
            if current_head != self.last_head:
                # New commit detected
                asyncio.create_task(
                    self.callback(self.repo, self.last_head, current_head)
                )
                self.last_head = current_head
        except Exception:
            pass

class GitWatcher:
    """Watch multiple git repositories for commits."""

    def __init__(
        self,
        repo_paths: list[str | Path],
        embedding_service: EmbeddingService,
        entity_extractor: EntityExtractor,
        db_session,
    ):
        self.repo_paths = [Path(p) for p in repo_paths]
        self.embedding_service = embedding_service
        self.entity_extractor = entity_extractor
        self.db_session = db_session
        self.observer = Observer()
        self.handlers: dict[Path, GitCommitHandler] = {}

    async def start(self):
        """Start watching all repositories."""
        for repo_path in self.repo_paths:
            await self._watch_repo(repo_path)

        self.observer.start()

    async def stop(self):
        """Stop watching."""
        self.observer.stop()
        self.observer.join()

    async def _watch_repo(self, repo_path: Path):
        """Set up watching for a single repository."""
        git_dir = repo_path / ".git"
        if not git_dir.exists():
            return

        handler = GitCommitHandler(repo_path, self._on_new_commit)
        self.observer.schedule(handler, str(git_dir), recursive=False)
        self.handlers[repo_path] = handler

    async def _on_new_commit(self, repo: Repo, old_sha: str, new_sha: str):
        """Process a new commit."""
        commit = repo.commit(new_sha)

        # Build content from commit
        content = self._format_commit(commit)

        # Generate embedding
        embedding = await self.embedding_service.embed(content)

        # Extract entities
        context = {
            "repo": repo.working_dir,
            "sha": new_sha,
            "branch": repo.active_branch.name,
            "files_changed": [d.a_path for d in commit.diff(old_sha)],
        }
        entities = await self.entity_extractor.extract(content, "commit", context)

        # Store memory
        memory = DevMemory(
            memory_type="commit",
            title=commit.message.split("\n")[0][:100],
            content=content,
            context=context,
            embedding=embedding,
            captured_at=datetime.fromtimestamp(commit.committed_date, tz=timezone.utc),
        )

        async with self.db_session() as session:
            session.add(memory)
            await session.commit()

            # Store entities and relationships
            for entity in entities.entities:
                # ... store entity and link to memory
                pass

    def _format_commit(self, commit) -> str:
        """Format commit for storage and embedding."""
        lines = [
            f"Commit: {commit.hexsha[:8]}",
            f"Author: {commit.author.name}",
            f"Date: {commit.committed_datetime.isoformat()}",
            f"Message: {commit.message}",
            "",
            "Changes:",
        ]

        # Add diff summary (truncated)
        try:
            parent = commit.parents[0] if commit.parents else None
            if parent:
                diff = commit.diff(parent)
                for d in diff[:20]:  # Limit to 20 files
                    lines.append(f"  {d.change_type}: {d.a_path}")
        except Exception:
            pass

        return "\n".join(lines)
```

#### 4.2.4 Hybrid Search (`search/hybrid.py`)

```python
"""Hybrid search combining BM25 and vector similarity."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from devmemory.db.connection import get_db
from devmemory.processing.embeddings import EmbeddingService
from devmemory.search.reranker import RerankerService

@dataclass
class SearchResult:
    """A single search result."""
    id: str
    memory_type: str
    title: str | None
    content: str
    context: dict
    tags: list[str]
    captured_at: datetime | None
    score: float
    bm25_score: float
    vector_score: float

@dataclass
class SearchFilters:
    """Filters for search queries."""
    memory_types: list[str] | None = None
    since: datetime | None = None
    tags: list[str] | None = None
    repo: str | None = None

class HybridSearchService:
    """Hybrid search service with BM25, vector, and reranking."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        reranker: RerankerService | None = None,
    ):
        self.embedding_service = embedding_service
        self.reranker = reranker

    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: SearchFilters | None = None,
        rerank: bool = True,
    ) -> list[SearchResult]:
        """Execute hybrid search with optional reranking."""

        # Generate query embedding
        query_embedding = await self.embedding_service.embed(query)

        # Execute hybrid search
        async with get_db() as conn:
            # Parse temporal filters
            since_date = None
            if filters and filters.since:
                since_date = filters.since

            memory_types = filters.memory_types if filters else None

            # Use the SQL function
            rows = await conn.fetch(
                """
                SELECT * FROM search_memories($1, $2, $3, $4, $5)
                """,
                query,
                query_embedding,
                limit * 2 if rerank else limit,  # Get more for reranking
                memory_types,
                since_date,
            )

        results = [
            SearchResult(
                id=str(row["id"]),
                memory_type=row["memory_type"],
                title=row["title"],
                content=row["content"],
                context=row["context"],
                tags=row["tags"] or [],
                captured_at=row["captured_at"],
                score=row["rrf_score"],
                bm25_score=row["bm25_rank"],
                vector_score=row["vector_rank"],
            )
            for row in rows
        ]

        # Apply reranking if enabled
        if rerank and self.reranker and results:
            results = await self.reranker.rerank(query, results)
            results = results[:limit]

        return results

    async def search_with_temporal(
        self,
        query: str,
        temporal_expr: str,  # "last week", "yesterday", "last month"
        limit: int = 10,
    ) -> list[SearchResult]:
        """Search with natural language temporal filtering."""
        since = self._parse_temporal(temporal_expr)
        filters = SearchFilters(since=since)
        return await self.search(query, limit, filters)

    def _parse_temporal(self, expr: str) -> datetime:
        """Parse natural language temporal expression."""
        now = datetime.now()
        expr = expr.lower().strip()

        mappings = {
            "today": timedelta(days=1),
            "yesterday": timedelta(days=2),
            "last week": timedelta(weeks=1),
            "last month": timedelta(days=30),
            "last 3 months": timedelta(days=90),
            "last year": timedelta(days=365),
        }

        for key, delta in mappings.items():
            if key in expr:
                return now - delta

        return now - timedelta(days=7)  # Default to last week
```

### 4.3 CLI Interface (`cli.py`)

```python
"""DevMemory CLI application."""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

app = typer.Typer(
    name="devmemory",
    help="Personal developer knowledge graph - capture and recall your dev journey.",
    no_args_is_help=True,
)
console = Console()

# =============================================================================
# CAPTURE COMMANDS
# =============================================================================

@app.command()
def add(
    content: Annotated[str, typer.Argument(help="Note content to capture")],
    tags: Annotated[Optional[list[str]], typer.Option("--tag", "-t", help="Tags")] = None,
    title: Annotated[Optional[str], typer.Option("--title", help="Note title")] = None,
):
    """Add a manual note to your dev memory."""
    from devmemory.capture.manual import capture_note

    async def _add():
        result = await capture_note(content, tags=tags or [], title=title)
        console.print(f"[green]✓[/green] Captured note: {result.id[:8]}")
        if result.entities:
            console.print(f"  Extracted entities: {', '.join(e.name for e in result.entities)}")

    asyncio.run(_add())

@app.command()
def watch(
    path: Annotated[Path, typer.Argument(help="Repository path to watch")],
    background: Annotated[bool, typer.Option("--bg", help="Run in background")] = False,
):
    """Start watching a git repository for commits."""
    from devmemory.capture.git import GitWatcher

    if not (path / ".git").exists():
        console.print(f"[red]Error:[/red] {path} is not a git repository")
        raise typer.Exit(1)

    console.print(f"[blue]Watching[/blue] {path} for commits...")

    async def _watch():
        watcher = await GitWatcher.create([path])
        await watcher.start()
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await watcher.stop()

    asyncio.run(_watch())

@app.command(name="import")
def import_conversation(
    file: Annotated[Path, typer.Argument(help="Claude export JSON file")],
):
    """Import a Claude Code conversation export."""
    from devmemory.capture.conversation import import_claude_export

    if not file.exists():
        console.print(f"[red]Error:[/red] File not found: {file}")
        raise typer.Exit(1)

    async def _import():
        count = await import_claude_export(file)
        console.print(f"[green]✓[/green] Imported {count} messages from conversation")

    asyncio.run(_import())

# =============================================================================
# SEARCH COMMANDS
# =============================================================================

@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max results")] = 10,
    since: Annotated[Optional[str], typer.Option("--since", "-s", help="Time filter")] = None,
    memory_type: Annotated[Optional[str], typer.Option("--type", "-t", help="Memory type")] = None,
    rerank: Annotated[bool, typer.Option("--rerank/--no-rerank", help="Use reranking")] = True,
    json_output: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
):
    """Search your dev memory using hybrid search."""
    from devmemory.search.hybrid import HybridSearchService, SearchFilters

    async def _search():
        service = await HybridSearchService.create()

        filters = SearchFilters(
            memory_types=[memory_type] if memory_type else None,
        )

        if since:
            results = await service.search_with_temporal(query, since, limit)
        else:
            results = await service.search(query, limit, filters, rerank=rerank)

        if json_output:
            import json
            console.print(json.dumps([r.__dict__ for r in results], default=str, indent=2))
            return

        if not results:
            console.print(f"[yellow]No results found for:[/yellow] {query}")
            return

        console.print(f"\n[bold]Results for:[/bold] {query}\n")

        for i, result in enumerate(results, 1):
            # Type badge
            type_colors = {
                "commit": "blue",
                "error": "red",
                "note": "green",
                "conversation": "magenta",
                "doc_visit": "cyan",
            }
            color = type_colors.get(result.memory_type, "white")
            type_badge = f"[{color}]{result.memory_type}[/{color}]"

            # Title
            title = result.title or result.content[:60] + "..."

            # Score
            score_str = f"[dim]({result.score:.3f})[/dim]"

            console.print(f"{i}. {type_badge} {title} {score_str}")

            # Preview
            preview = result.content[:200].replace("\n", " ")
            console.print(f"   [dim]{preview}...[/dim]")

            # Tags
            if result.tags:
                tags_str = " ".join(f"[cyan]#{t}[/cyan]" for t in result.tags)
                console.print(f"   {tags_str}")

            console.print()

    asyncio.run(_search())

# =============================================================================
# ENTITY COMMANDS
# =============================================================================

entities_app = typer.Typer(help="Manage extracted entities")
app.add_typer(entities_app, name="entities")

@entities_app.command("list")
def list_entities(
    entity_type: Annotated[Optional[str], typer.Option("--type", "-t")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n")] = 20,
):
    """List all extracted entities."""
    from devmemory.db.queries import get_entities

    async def _list():
        entities = await get_entities(entity_type=entity_type, limit=limit)

        table = Table(title="Entities")
        table.add_column("Type", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Mentions", justify="right")
        table.add_column("Last Seen")

        for e in entities:
            table.add_row(
                e.entity_type,
                e.name,
                str(e.mention_count),
                e.last_seen.strftime("%Y-%m-%d") if e.last_seen else "-",
            )

        console.print(table)

    asyncio.run(_list())

@entities_app.command("related")
def related_entities(
    name: Annotated[str, typer.Argument(help="Entity name")],
    limit: Annotated[int, typer.Option("--limit", "-n")] = 10,
):
    """Find entities related to a given entity."""
    from devmemory.db.queries import get_related_entities

    async def _related():
        related = await get_related_entities(name, limit=limit)

        if not related:
            console.print(f"[yellow]No related entities found for:[/yellow] {name}")
            return

        console.print(f"\n[bold]Entities related to:[/bold] {name}\n")

        for r in related:
            console.print(f"  → {r.relationship_type} [cyan]{r.to_entity.name}[/cyan] ({r.to_entity.entity_type})")

    asyncio.run(_related())

# =============================================================================
# SERVER COMMANDS
# =============================================================================

@app.command()
def serve(
    host: Annotated[str, typer.Option(help="Host to bind")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port to bind")] = 8100,
):
    """Start the DevMemory API server."""
    import uvicorn
    from devmemory.server import create_app

    console.print(f"[green]Starting DevMemory server on {host}:{port}[/green]")
    uvicorn.run(create_app(), host=host, port=port)

@app.command()
def mcp(
):
    """Start the DevMemory MCP server (for Claude Code integration)."""
    from devmemory.mcp_server import run_mcp_server

    asyncio.run(run_mcp_server())

# =============================================================================
# UTILITY COMMANDS
# =============================================================================

@app.command()
def stats():
    """Show statistics about your dev memory."""
    from devmemory.db.queries import get_stats

    async def _stats():
        s = await get_stats()

        panel = Panel(
            f"""
[bold]DevMemory Statistics[/bold]

Total Memories: [cyan]{s.total_memories:,}[/cyan]
  • Commits: {s.commits:,}
  • Errors: {s.errors:,}
  • Notes: {s.notes:,}
  • Conversations: {s.conversations:,}

Total Entities: [cyan]{s.total_entities:,}[/cyan]
Total Relationships: [cyan]{s.total_relationships:,}[/cyan]

Storage: {s.storage_mb:.1f} MB
Oldest Memory: {s.oldest_memory.strftime('%Y-%m-%d') if s.oldest_memory else 'N/A'}
Newest Memory: {s.newest_memory.strftime('%Y-%m-%d') if s.newest_memory else 'N/A'}
            """,
            title="DevMemory",
            border_style="blue",
        )
        console.print(panel)

    asyncio.run(_stats())

@app.command()
def init():
    """Initialize DevMemory database and configuration."""
    from devmemory.db.migrations import run_migrations

    async def _init():
        console.print("[blue]Initializing DevMemory...[/blue]")

        # Run migrations
        console.print("  → Running database migrations...")
        await run_migrations()
        console.print("  [green]✓[/green] Database ready")

        # Check Ollama
        console.print("  → Checking Ollama connection...")
        from devmemory.processing.embeddings import check_ollama
        if await check_ollama():
            console.print("  [green]✓[/green] Ollama available")
        else:
            console.print("  [yellow]![/yellow] Ollama not available (embeddings disabled)")

        console.print("\n[green]DevMemory initialized![/green]")
        console.print("\nNext steps:")
        console.print("  1. devmemory watch ~/claude-code  # Start watching repos")
        console.print("  2. devmemory add 'learned about X'  # Add manual notes")
        console.print("  3. devmemory search 'how to fix Y'  # Search your memory")

    asyncio.run(_init())

if __name__ == "__main__":
    app()
```

### 4.4 MCP Server (`mcp_server.py`)

```python
"""DevMemory MCP Server for Claude Code integration."""
from __future__ import annotations

import asyncio
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Resource

from devmemory.search.hybrid import HybridSearchService, SearchFilters
from devmemory.capture.manual import capture_note
from devmemory.db.queries import get_entities, get_related_entities, get_stats

# Create MCP server
server = Server("devmemory")

# =============================================================================
# TOOLS
# =============================================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available DevMemory tools."""
    return [
        Tool(
            name="search_memory",
            description="Search your development memory for past solutions, fixes, and learnings. Use natural language queries like 'how did I fix the postgres timeout?' or 'what packages did I use for caching?'",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query"
                    },
                    "since": {
                        "type": "string",
                        "description": "Time filter: 'today', 'yesterday', 'last week', 'last month'",
                    },
                    "memory_type": {
                        "type": "string",
                        "enum": ["commit", "error", "note", "conversation", "doc_visit"],
                        "description": "Filter by memory type"
                    },
                    "limit": {
                        "type": "integer",
                        "default": 5,
                        "description": "Maximum results to return"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="add_memory",
            description="Add a note to your development memory. Use this to capture learnings, solutions, or important context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The note content to save"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags to categorize this memory"
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional title for the memory"
                    }
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="find_entity",
            description="Find information about a specific entity (function, package, error, concept) in your memory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Entity name to look up"
                    },
                    "include_related": {
                        "type": "boolean",
                        "default": True,
                        "description": "Include related entities"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="memory_stats",
            description="Get statistics about your development memory.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute a DevMemory tool."""

    if name == "search_memory":
        service = await HybridSearchService.create()

        query = arguments["query"]
        limit = arguments.get("limit", 5)
        since = arguments.get("since")
        memory_type = arguments.get("memory_type")

        filters = SearchFilters(
            memory_types=[memory_type] if memory_type else None,
        )

        if since:
            results = await service.search_with_temporal(query, since, limit)
        else:
            results = await service.search(query, limit, filters)

        if not results:
            return [TextContent(type="text", text=f"No memories found for: {query}")]

        output_lines = [f"Found {len(results)} relevant memories:\n"]

        for i, r in enumerate(results, 1):
            output_lines.append(f"## {i}. [{r.memory_type}] {r.title or 'Untitled'}")
            output_lines.append(f"*Captured: {r.captured_at.strftime('%Y-%m-%d %H:%M') if r.captured_at else 'Unknown'}*")
            output_lines.append(f"\n{r.content[:500]}...")
            if r.tags:
                output_lines.append(f"\nTags: {', '.join(r.tags)}")
            output_lines.append("\n---\n")

        return [TextContent(type="text", text="\n".join(output_lines))]

    elif name == "add_memory":
        result = await capture_note(
            content=arguments["content"],
            tags=arguments.get("tags", []),
            title=arguments.get("title"),
        )

        output = f"✓ Memory saved (ID: {result.id[:8]})"
        if result.entities:
            output += f"\nExtracted entities: {', '.join(e.name for e in result.entities)}"

        return [TextContent(type="text", text=output)]

    elif name == "find_entity":
        name_query = arguments["name"]
        include_related = arguments.get("include_related", True)

        entities = await get_entities(name_filter=name_query, limit=5)

        if not entities:
            return [TextContent(type="text", text=f"No entity found matching: {name_query}")]

        output_lines = []

        for entity in entities:
            output_lines.append(f"## {entity.name} ({entity.entity_type})")
            if entity.description:
                output_lines.append(entity.description)
            output_lines.append(f"Mentions: {entity.mention_count}")
            output_lines.append(f"Last seen: {entity.last_seen.strftime('%Y-%m-%d') if entity.last_seen else 'Unknown'}")

            if include_related:
                related = await get_related_entities(entity.name, limit=5)
                if related:
                    output_lines.append("\nRelated entities:")
                    for r in related:
                        output_lines.append(f"  → {r.relationship_type} {r.to_entity.name}")

            output_lines.append("\n---\n")

        return [TextContent(type="text", text="\n".join(output_lines))]

    elif name == "memory_stats":
        s = await get_stats()

        output = f"""DevMemory Statistics

Total Memories: {s.total_memories:,}
  • Commits: {s.commits:,}
  • Errors: {s.errors:,}
  • Notes: {s.notes:,}
  • Conversations: {s.conversations:,}

Total Entities: {s.total_entities:,}
Total Relationships: {s.total_relationships:,}

Storage: {s.storage_mb:.1f} MB
Date Range: {s.oldest_memory.strftime('%Y-%m-%d') if s.oldest_memory else 'N/A'} to {s.newest_memory.strftime('%Y-%m-%d') if s.newest_memory else 'N/A'}
"""
        return [TextContent(type="text", text=output)]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]

# =============================================================================
# RESOURCES
# =============================================================================

@server.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources."""
    return [
        Resource(
            uri="devmemory://entities",
            name="All Entities",
            description="List of all extracted entities from your development memory",
            mimeType="application/json",
        ),
        Resource(
            uri="devmemory://recent",
            name="Recent Memories",
            description="Most recent captured memories",
            mimeType="application/json",
        ),
    ]

@server.read_resource()
async def read_resource(uri: str) -> str:
    """Read a DevMemory resource."""
    import json

    if uri == "devmemory://entities":
        entities = await get_entities(limit=100)
        return json.dumps([
            {"name": e.name, "type": e.entity_type, "mentions": e.mention_count}
            for e in entities
        ], indent=2)

    elif uri == "devmemory://recent":
        from devmemory.db.queries import get_recent_memories
        memories = await get_recent_memories(limit=20)
        return json.dumps([
            {
                "type": m.memory_type,
                "title": m.title,
                "preview": m.content[:200],
                "captured": m.captured_at.isoformat() if m.captured_at else None,
            }
            for m in memories
        ], indent=2)

    return "{}"

# =============================================================================
# ENTRY POINT
# =============================================================================

async def run_mcp_server():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )

if __name__ == "__main__":
    asyncio.run(run_mcp_server())
```

---

## 5. Phase 2: CodeMCP

### 5.1 Project Structure

```
codemcp/
├── __init__.py
├── __main__.py
├── server.py                   # MCP server implementation
├── config.py                   # Configuration
│
├── indexer/
│   ├── __init__.py
│   ├── manager.py              # Index management
│   ├── batch.py                # Batch indexing
│   ├── incremental.py          # Incremental updates (file watcher)
│   └── languages/
│       ├── __init__.py
│       ├── base.py             # Abstract language parser
│       ├── python.py           # Python parser (tree-sitter)
│       ├── typescript.py       # TypeScript parser
│       └── javascript.py       # JavaScript parser
│
├── parser/
│   ├── __init__.py
│   ├── treesitter.py           # tree-sitter integration
│   ├── symbols.py              # Symbol extraction
│   └── dependencies.py         # Import/call graph
│
├── search/
│   ├── __init__.py
│   ├── semantic.py             # Semantic code search
│   ├── structural.py           # Structural queries (AST-based)
│   └── architecture.py         # High-level architecture queries
│
├── tools/
│   ├── __init__.py
│   ├── search_code.py          # search_code tool
│   ├── explain_function.py     # explain_function tool
│   ├── find_related.py         # find_related tool
│   └── get_architecture.py     # get_architecture tool
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_indexer/
    ├── test_parser/
    └── test_tools/
```

### 5.2 Tree-sitter Parser (`parser/treesitter.py`)

```python
"""Tree-sitter based code parser."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator

import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Parser, Node

@dataclass
class ParsedSymbol:
    """A parsed code symbol."""
    name: str
    symbol_type: str  # function, class, method, etc.
    qualified_name: str
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    signature: str | None = None
    docstring: str | None = None
    body_preview: str | None = None
    is_exported: bool = True
    is_async: bool = False
    decorators: list[str] = field(default_factory=list)
    parameters: list[dict] | None = None
    return_type: str | None = None
    ast_node_type: str | None = None

@dataclass
class ParsedImport:
    """A parsed import statement."""
    module: str
    symbols: list[str]  # Empty for "import module", populated for "from module import x, y"
    alias: str | None = None
    line_number: int = 0
    is_relative: bool = False

class TreeSitterParser:
    """Parse source code using tree-sitter."""

    LANGUAGE_MAP = {
        ".py": ("python", tspython.language()),
        ".js": ("javascript", tsjavascript.language()),
        ".jsx": ("javascript", tsjavascript.language()),
        ".ts": ("typescript", tstypescript.language_typescript()),
        ".tsx": ("typescript", tstypescript.language_tsx()),
    }

    def __init__(self):
        self.parsers: dict[str, Parser] = {}
        self._init_parsers()

    def _init_parsers(self):
        """Initialize tree-sitter parsers for each language."""
        for ext, (lang_name, lang) in self.LANGUAGE_MAP.items():
            if lang_name not in self.parsers:
                parser = Parser(Language(lang))
                self.parsers[lang_name] = parser

    def parse_file(self, filepath: Path) -> tuple[list[ParsedSymbol], list[ParsedImport]]:
        """Parse a file and extract symbols and imports."""
        ext = filepath.suffix.lower()

        if ext not in self.LANGUAGE_MAP:
            return [], []

        lang_name, _ = self.LANGUAGE_MAP[ext]
        parser = self.parsers[lang_name]

        content = filepath.read_text(encoding="utf-8", errors="replace")
        tree = parser.parse(content.encode("utf-8"))

        symbols = list(self._extract_symbols(tree.root_node, content, lang_name))
        imports = list(self._extract_imports(tree.root_node, content, lang_name))

        return symbols, imports

    def _extract_symbols(
        self, node: Node, source: str, language: str, parent_name: str = ""
    ) -> Generator[ParsedSymbol, None, None]:
        """Extract symbols from AST."""

        # Python-specific extractions
        if language == "python":
            yield from self._extract_python_symbols(node, source, parent_name)

        # TypeScript/JavaScript extractions
        elif language in ("typescript", "javascript"):
            yield from self._extract_ts_symbols(node, source, parent_name)

    def _extract_python_symbols(
        self, node: Node, source: str, parent_name: str = ""
    ) -> Generator[ParsedSymbol, None, None]:
        """Extract Python symbols."""

        for child in node.children:
            if child.type == "function_definition":
                yield self._parse_python_function(child, source, parent_name)

            elif child.type == "async_function_definition":
                sym = self._parse_python_function(child, source, parent_name)
                sym.is_async = True
                yield sym

            elif child.type == "class_definition":
                class_sym = self._parse_python_class(child, source, parent_name)
                yield class_sym

                # Extract methods
                class_body = self._find_child(child, "block")
                if class_body:
                    qualified = f"{parent_name}.{class_sym.name}" if parent_name else class_sym.name
                    yield from self._extract_python_symbols(class_body, source, qualified)

            elif child.type == "decorated_definition":
                # Handle decorated functions/classes
                decorators = [
                    source[d.start_byte:d.end_byte]
                    for d in child.children if d.type == "decorator"
                ]
                definition = self._find_child(child, "function_definition") or \
                            self._find_child(child, "class_definition") or \
                            self._find_child(child, "async_function_definition")
                if definition:
                    for sym in self._extract_python_symbols(
                        Node.__new__(Node), source, parent_name
                    ):
                        # This is a placeholder - actual implementation would iterate
                        pass

    def _parse_python_function(
        self, node: Node, source: str, parent_name: str
    ) -> ParsedSymbol:
        """Parse a Python function definition."""
        name_node = self._find_child(node, "identifier")
        name = source[name_node.start_byte:name_node.end_byte] if name_node else "unknown"

        params_node = self._find_child(node, "parameters")
        params_str = source[params_node.start_byte:params_node.end_byte] if params_node else "()"

        # Extract return type annotation
        return_type = None
        return_node = self._find_child(node, "type")
        if return_node:
            return_type = source[return_node.start_byte:return_node.end_byte]

        # Extract docstring
        docstring = None
        body = self._find_child(node, "block")
        if body and body.children:
            first_stmt = body.children[0]
            if first_stmt.type == "expression_statement":
                string_node = self._find_child(first_stmt, "string")
                if string_node:
                    docstring = source[string_node.start_byte:string_node.end_byte].strip('"""\'')

        # Build signature
        signature = f"def {name}{params_str}"
        if return_type:
            signature += f" -> {return_type}"

        qualified_name = f"{parent_name}.{name}" if parent_name else name

        return ParsedSymbol(
            name=name,
            symbol_type="method" if parent_name else "function",
            qualified_name=qualified_name,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            start_col=node.start_point[1],
            end_col=node.end_point[1],
            signature=signature,
            docstring=docstring,
            return_type=return_type,
            ast_node_type=node.type,
        )

    def _parse_python_class(self, node: Node, source: str, parent_name: str) -> ParsedSymbol:
        """Parse a Python class definition."""
        name_node = self._find_child(node, "identifier")
        name = source[name_node.start_byte:name_node.end_byte] if name_node else "unknown"

        # Extract bases
        bases = []
        arg_list = self._find_child(node, "argument_list")
        if arg_list:
            bases_str = source[arg_list.start_byte:arg_list.end_byte]
            bases = [b.strip() for b in bases_str.strip("()").split(",") if b.strip()]

        # Extract docstring
        docstring = None
        body = self._find_child(node, "block")
        if body and body.children:
            first_stmt = body.children[0]
            if first_stmt.type == "expression_statement":
                string_node = self._find_child(first_stmt, "string")
                if string_node:
                    docstring = source[string_node.start_byte:string_node.end_byte].strip('"""\'')

        qualified_name = f"{parent_name}.{name}" if parent_name else name

        return ParsedSymbol(
            name=name,
            symbol_type="class",
            qualified_name=qualified_name,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            start_col=node.start_point[1],
            end_col=node.end_point[1],
            signature=f"class {name}({', '.join(bases)})" if bases else f"class {name}",
            docstring=docstring,
            ast_node_type=node.type,
        )

    def _extract_imports(
        self, node: Node, source: str, language: str
    ) -> Generator[ParsedImport, None, None]:
        """Extract import statements."""

        for child in node.children:
            if language == "python":
                if child.type == "import_statement":
                    # import module
                    module_node = self._find_child(child, "dotted_name")
                    if module_node:
                        yield ParsedImport(
                            module=source[module_node.start_byte:module_node.end_byte],
                            symbols=[],
                            line_number=child.start_point[0] + 1,
                        )

                elif child.type == "import_from_statement":
                    # from module import x, y
                    module_node = self._find_child(child, "dotted_name")
                    module = source[module_node.start_byte:module_node.end_byte] if module_node else ""

                    symbols = []
                    for name_node in child.children:
                        if name_node.type == "dotted_name" and name_node != module_node:
                            symbols.append(source[name_node.start_byte:name_node.end_byte])
                        elif name_node.type == "aliased_import":
                            name = self._find_child(name_node, "dotted_name")
                            if name:
                                symbols.append(source[name.start_byte:name.end_byte])

                    yield ParsedImport(
                        module=module,
                        symbols=symbols,
                        line_number=child.start_point[0] + 1,
                        is_relative=module.startswith("."),
                    )

    @staticmethod
    def _find_child(node: Node, child_type: str) -> Node | None:
        """Find first child of given type."""
        for child in node.children:
            if child.type == child_type:
                return child
        return None
```

### 5.3 MCP Server (`server.py`)

```python
"""CodeMCP - MCP Server for semantic codebase understanding."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from codemcp.config import settings
from codemcp.indexer.manager import IndexManager
from codemcp.search.semantic import SemanticSearch
from codemcp.search.architecture import ArchitectureAnalyzer

server = Server("codemcp")
index_manager: IndexManager | None = None
semantic_search: SemanticSearch | None = None

async def get_index_manager() -> IndexManager:
    """Get or create index manager."""
    global index_manager
    if index_manager is None:
        index_manager = await IndexManager.create()
    return index_manager

async def get_semantic_search() -> SemanticSearch:
    """Get or create semantic search."""
    global semantic_search
    if semantic_search is None:
        semantic_search = await SemanticSearch.create()
    return semantic_search

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available CodeMCP tools."""
    return [
        Tool(
            name="search_code",
            description="Semantic search across your codebase. Finds functions, classes, and code blocks by meaning, not just keywords. Example: 'authentication handling' finds all auth-related code.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language description of what you're looking for"
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository path to search (optional, searches all indexed repos)"
                    },
                    "language": {
                        "type": "string",
                        "enum": ["python", "typescript", "javascript"],
                        "description": "Filter by programming language"
                    },
                    "symbol_type": {
                        "type": "string",
                        "enum": ["function", "class", "method"],
                        "description": "Filter by symbol type"
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "description": "Maximum results"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="explain_function",
            description="Get detailed explanation of a function including its signature, docstring, usage examples from the codebase, and any related DevMemory context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Function name (can be partial, e.g., 'authenticate' or 'auth.login')"
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository path (optional)"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="find_related",
            description="Find files and functions conceptually related to a given file or function. Uses dependency analysis and semantic similarity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "File path (relative to repo root)"
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name (function/class) to find related code for"
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "description": "Maximum results"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_architecture",
            description="Get high-level architecture overview of a repository. Shows main modules, entry points, key abstractions, and dependency graph.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository path"
                    },
                    "depth": {
                        "type": "string",
                        "enum": ["summary", "detailed"],
                        "default": "summary",
                        "description": "Level of detail"
                    }
                },
                "required": ["repo"]
            }
        ),
        Tool(
            name="index_repo",
            description="Index a repository for semantic search. Run this before searching a new codebase.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to repository"
                    },
                    "force": {
                        "type": "boolean",
                        "default": False,
                        "description": "Force re-indexing even if already indexed"
                    }
                },
                "required": ["path"]
            }
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute a CodeMCP tool."""

    if name == "search_code":
        search = await get_semantic_search()

        results = await search.search(
            query=arguments["query"],
            repo_path=arguments.get("repo"),
            language=arguments.get("language"),
            symbol_type=arguments.get("symbol_type"),
            limit=arguments.get("limit", 10),
        )

        if not results:
            return [TextContent(
                type="text",
                text=f"No code found matching: {arguments['query']}"
            )]

        output_lines = [f"Found {len(results)} matches:\n"]

        for r in results:
            output_lines.append(f"## {r.qualified_name}")
            output_lines.append(f"**File:** `{r.filepath}:{r.start_line}`")
            output_lines.append(f"**Type:** {r.symbol_type}")
            if r.signature:
                output_lines.append(f"```\n{r.signature}\n```")
            if r.docstring:
                output_lines.append(f"*{r.docstring[:200]}...*" if len(r.docstring) > 200 else f"*{r.docstring}*")
            output_lines.append(f"Relevance: {r.score:.2f}")
            output_lines.append("\n---\n")

        return [TextContent(type="text", text="\n".join(output_lines))]

    elif name == "explain_function":
        search = await get_semantic_search()

        # Find the function
        results = await search.search(
            query=arguments["name"],
            symbol_type="function",
            limit=1,
        )

        if not results:
            # Try method
            results = await search.search(
                query=arguments["name"],
                symbol_type="method",
                limit=1,
            )

        if not results:
            return [TextContent(
                type="text",
                text=f"Function not found: {arguments['name']}"
            )]

        func = results[0]

        # Get full source
        from codemcp.db.queries import get_symbol_source
        source = await get_symbol_source(func.id)

        # Get callers
        from codemcp.db.queries import get_callers
        callers = await get_callers(func.id, limit=5)

        # Check DevMemory for related context
        devmemory_context = ""
        try:
            from devmemory.search.hybrid import HybridSearchService
            dm_search = await HybridSearchService.create()
            memories = await dm_search.search(func.name, limit=3)
            if memories:
                devmemory_context = "\n## Related DevMemory\n"
                for m in memories:
                    devmemory_context += f"- [{m.memory_type}] {m.title or m.content[:50]}...\n"
        except ImportError:
            pass

        output = f"""# {func.qualified_name}

**File:** `{func.filepath}:{func.start_line}-{func.end_line}`
**Type:** {func.symbol_type}

## Signature
```python
{func.signature}
```

## Documentation
{func.docstring or '*No docstring*'}

## Source
```python
{source[:1000]}{'...' if len(source) > 1000 else ''}
```

## Called By
{chr(10).join(f'- `{c.qualified_name}` in `{c.filepath}`' for c in callers) if callers else '*No callers found in indexed code*'}
{devmemory_context}
"""
        return [TextContent(type="text", text=output)]

    elif name == "find_related":
        search = await get_semantic_search()

        filepath = arguments.get("filepath")
        symbol = arguments.get("symbol")
        limit = arguments.get("limit", 10)

        if symbol:
            related = await search.find_related_to_symbol(symbol, limit)
        elif filepath:
            related = await search.find_related_to_file(filepath, limit)
        else:
            return [TextContent(
                type="text",
                text="Please provide either 'filepath' or 'symbol'"
            )]

        if not related:
            return [TextContent(type="text", text="No related code found")]

        output_lines = ["## Related Code\n"]
        for r in related:
            output_lines.append(f"- `{r.qualified_name}` in `{r.filepath}`")
            output_lines.append(f"  *Relationship: {r.relationship_type} (score: {r.score:.2f})*")

        return [TextContent(type="text", text="\n".join(output_lines))]

    elif name == "get_architecture":
        analyzer = ArchitectureAnalyzer()
        repo_path = Path(arguments["repo"]).expanduser()
        depth = arguments.get("depth", "summary")

        architecture = await analyzer.analyze(repo_path, detailed=(depth == "detailed"))

        output = f"""# Architecture: {repo_path.name}

## Overview
- **Files:** {architecture.file_count}
- **Symbols:** {architecture.symbol_count}
- **Languages:** {', '.join(architecture.languages)}

## Main Entry Points
{chr(10).join(f'- `{e}`' for e in architecture.entry_points)}

## Key Modules
{chr(10).join(f'- **{m.name}**: {m.description}' for m in architecture.modules)}

## Dependency Graph
```
{architecture.dependency_graph_ascii}
```
"""

        if depth == "detailed":
            output += f"""
## All Symbols
{chr(10).join(f'- `{s.qualified_name}` ({s.symbol_type})' for s in architecture.all_symbols[:50])}
{'... and more' if len(architecture.all_symbols) > 50 else ''}
"""

        return [TextContent(type="text", text=output)]

    elif name == "index_repo":
        manager = await get_index_manager()

        repo_path = Path(arguments["path"]).expanduser()
        force = arguments.get("force", False)

        if not repo_path.exists():
            return [TextContent(
                type="text",
                text=f"Repository not found: {repo_path}"
            )]

        result = await manager.index_repository(repo_path, force=force)

        return [TextContent(
            type="text",
            text=f"""Indexed repository: {repo_path.name}

- Files: {result.files_indexed}
- Symbols: {result.symbols_extracted}
- Dependencies: {result.dependencies_mapped}
- Duration: {result.duration_seconds:.1f}s
"""
        )]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]

async def run_mcp_server():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )

if __name__ == "__main__":
    asyncio.run(run_mcp_server())
```

---

## 6. Phase 3: ContextLens

### 6.1 Project Structure

```
contextlens/
├── __init__.py
├── __main__.py
├── cli.py                      # Rich CLI with dashboard
├── server.py                   # MCP server
├── config.py
│
├── scoring/
│   ├── __init__.py
│   ├── relevance.py            # File relevance scoring
│   ├── recency.py              # Recency-based scoring
│   ├── dependency.py           # Dependency proximity scoring
│   └── devmemory.py            # DevMemory signal integration
│
├── counting/
│   ├── __init__.py
│   ├── tokens.py               # tiktoken-based counting
│   └── compression.py          # Compression estimation
│
├── optimization/
│   ├── __init__.py
│   ├── selector.py             # File selection algorithm
│   ├── summarizer.py           # Large file summarization
│   └── strategies.py           # Optimization strategies
│
├── ui/
│   ├── __init__.py
│   ├── dashboard.py            # Rich TUI dashboard
│   └── components.py           # Reusable UI components
│
└── tests/
```

### 6.2 Core Components

#### Relevance Scorer (`scoring/relevance.py`)

```python
"""File relevance scoring for context optimization."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import tiktoken

from contextlens.config import settings

@dataclass
class FileRelevance:
    """Relevance score for a file."""
    filepath: str
    token_count: int

    # Individual scores (0-1)
    embedding_similarity: float
    recency_score: float
    dependency_score: float
    devmemory_score: float

    # Combined score
    final_score: float

    # Recommendation
    include: bool
    reason: str

class RelevanceScorer:
    """Score files by relevance to a query/task."""

    def __init__(
        self,
        embedding_service,
        devmemory_client=None,
        codemcp_client=None,
    ):
        self.embedding_service = embedding_service
        self.devmemory_client = devmemory_client
        self.codemcp_client = codemcp_client
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")

        # Weights for combining scores
        self.weights = {
            "embedding": 0.4,
            "recency": 0.2,
            "dependency": 0.25,
            "devmemory": 0.15,
        }

    async def score_files(
        self,
        query: str,
        files: list[Path],
        max_tokens: int = 100000,
    ) -> list[FileRelevance]:
        """Score all files and recommend inclusion."""

        # Generate query embedding
        query_embedding = await self.embedding_service.embed(query)

        relevances = []

        for filepath in files:
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
                tokens = len(self.tokenizer.encode(content))

                # Skip very large files
                if tokens > 50000:
                    relevances.append(FileRelevance(
                        filepath=str(filepath),
                        token_count=tokens,
                        embedding_similarity=0,
                        recency_score=0,
                        dependency_score=0,
                        devmemory_score=0,
                        final_score=0,
                        include=False,
                        reason="File too large (>50k tokens)"
                    ))
                    continue

                # Calculate individual scores
                emb_score = await self._embedding_similarity(content, query_embedding)
                rec_score = self._recency_score(filepath)
                dep_score = await self._dependency_score(filepath, query) if self.codemcp_client else 0
                dm_score = await self._devmemory_score(filepath, query) if self.devmemory_client else 0

                # Combine scores
                final = (
                    self.weights["embedding"] * emb_score +
                    self.weights["recency"] * rec_score +
                    self.weights["dependency"] * dep_score +
                    self.weights["devmemory"] * dm_score
                )

                relevances.append(FileRelevance(
                    filepath=str(filepath),
                    token_count=tokens,
                    embedding_similarity=emb_score,
                    recency_score=rec_score,
                    dependency_score=dep_score,
                    devmemory_score=dm_score,
                    final_score=final,
                    include=True,  # Will be determined in optimization
                    reason=""
                ))

            except Exception as e:
                relevances.append(FileRelevance(
                    filepath=str(filepath),
                    token_count=0,
                    embedding_similarity=0,
                    recency_score=0,
                    dependency_score=0,
                    devmemory_score=0,
                    final_score=0,
                    include=False,
                    reason=f"Error: {str(e)}"
                ))

        # Sort by score
        relevances.sort(key=lambda x: x.final_score, reverse=True)

        # Apply token budget
        total_tokens = 0
        for r in relevances:
            if total_tokens + r.token_count <= max_tokens and r.final_score > 0.1:
                r.include = True
                r.reason = f"High relevance ({r.final_score:.2f})"
                total_tokens += r.token_count
            else:
                r.include = False
                if r.final_score <= 0.1:
                    r.reason = "Low relevance"
                else:
                    r.reason = "Excluded due to token budget"

        return relevances

    async def _embedding_similarity(self, content: str, query_embedding) -> float:
        """Calculate embedding similarity."""
        # Embed first 2000 chars for efficiency
        content_preview = content[:2000]
        content_embedding = await self.embedding_service.embed(content_preview)

        # Cosine similarity
        import numpy as np
        similarity = np.dot(query_embedding, content_embedding) / (
            np.linalg.norm(query_embedding) * np.linalg.norm(content_embedding)
        )
        return float(max(0, similarity))

    def _recency_score(self, filepath: Path) -> float:
        """Score based on file modification time."""
        import time

        try:
            mtime = filepath.stat().st_mtime
            age_hours = (time.time() - mtime) / 3600

            # Decay function: recent files score higher
            if age_hours < 1:
                return 1.0
            elif age_hours < 24:
                return 0.8
            elif age_hours < 168:  # 1 week
                return 0.5
            elif age_hours < 720:  # 1 month
                return 0.3
            else:
                return 0.1
        except Exception:
            return 0.1

    async def _dependency_score(self, filepath: Path, query: str) -> float:
        """Score based on dependency proximity to query-related files."""
        if not self.codemcp_client:
            return 0

        # Use CodeMCP to find related files
        try:
            related = await self.codemcp_client.find_related(str(filepath))
            if not related:
                return 0.2

            # If this file is commonly referenced, it's important
            return min(1.0, 0.3 + len(related) * 0.1)
        except Exception:
            return 0.2

    async def _devmemory_score(self, filepath: Path, query: str) -> float:
        """Score based on DevMemory relevance."""
        if not self.devmemory_client:
            return 0

        try:
            # Check if this file appears in relevant memories
            memories = await self.devmemory_client.search(
                f"{query} {filepath.name}",
                limit=5
            )

            if not memories:
                return 0.1

            # Higher score if file is mentioned in relevant memories
            file_mentions = sum(
                1 for m in memories
                if filepath.name in m.content or str(filepath) in str(m.context)
            )

            return min(1.0, 0.2 + file_mentions * 0.2)
        except Exception:
            return 0.1
```

#### CLI Dashboard (`ui/dashboard.py`)

```python
"""Rich TUI dashboard for ContextLens."""
from __future__ import annotations

from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text

console = Console()

class ContextDashboard:
    """Interactive context usage dashboard."""

    def __init__(self, scorer, max_tokens: int = 200000):
        self.scorer = scorer
        self.max_tokens = max_tokens
        self.relevances = []
        self.total_tokens = 0
        self.saved_tokens = 0

    def render(self) -> Layout:
        """Render the dashboard layout."""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3),
        )

        layout["main"].split_row(
            Layout(name="files", ratio=2),
            Layout(name="stats", ratio=1),
        )

        # Header
        layout["header"].update(
            Panel(
                Text("ContextLens - Smart Context Optimizer", style="bold cyan", justify="center"),
                border_style="cyan"
            )
        )

        # Files table
        layout["files"].update(self._render_files_table())

        # Stats panel
        layout["stats"].update(self._render_stats())

        # Footer
        layout["footer"].update(
            Panel(
                "[q] Quit  [r] Refresh  [+/-] Include/Exclude  [o] Optimize",
                border_style="dim"
            )
        )

        return layout

    def _render_files_table(self) -> Panel:
        """Render the files table."""
        table = Table(title="Files by Relevance", expand=True)

        table.add_column("", width=3)  # Include checkbox
        table.add_column("File", style="cyan")
        table.add_column("Tokens", justify="right", style="yellow")
        table.add_column("Relevance", justify="right")
        table.add_column("Reason", style="dim")

        for r in self.relevances[:30]:  # Show top 30
            checkbox = "[green]✓[/green]" if r.include else "[red]✗[/red]"

            # Relevance bar
            score_bar = self._score_bar(r.final_score)

            table.add_row(
                checkbox,
                r.filepath.split("/")[-1],  # Just filename
                f"{r.token_count:,}",
                score_bar,
                r.reason[:30],
            )

        return Panel(table, title="Context Files", border_style="blue")

    def _render_stats(self) -> Panel:
        """Render statistics panel."""
        included = sum(1 for r in self.relevances if r.include)
        excluded = len(self.relevances) - included
        included_tokens = sum(r.token_count for r in self.relevances if r.include)
        excluded_tokens = sum(r.token_count for r in self.relevances if not r.include)

        usage_pct = (included_tokens / self.max_tokens) * 100 if self.max_tokens else 0

        # Usage bar
        usage_bar = Progress(
            TextColumn("[bold]Context Usage"),
            BarColumn(bar_width=20),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        )
        task = usage_bar.add_task("usage", total=100, completed=usage_pct)

        stats_text = f"""
[bold cyan]Token Budget[/bold cyan]
  Used: [green]{included_tokens:,}[/green] / {self.max_tokens:,}
  Available: [yellow]{self.max_tokens - included_tokens:,}[/yellow]

[bold cyan]Files[/bold cyan]
  Included: [green]{included}[/green]
  Excluded: [red]{excluded}[/red]

[bold cyan]Savings[/bold cyan]
  Tokens saved: [green]{excluded_tokens:,}[/green]
  Percentage: [green]{(excluded_tokens / (included_tokens + excluded_tokens) * 100) if excluded_tokens else 0:.1f}%[/green]

[bold cyan]Top Scores[/bold cyan]
  Highest: {self.relevances[0].final_score:.3f if self.relevances else 0}
  Threshold: 0.100
"""

        return Panel(stats_text, title="Statistics", border_style="green")

    def _score_bar(self, score: float) -> str:
        """Create a visual score bar."""
        filled = int(score * 10)
        empty = 10 - filled

        if score >= 0.7:
            color = "green"
        elif score >= 0.4:
            color = "yellow"
        else:
            color = "red"

        return f"[{color}]{'█' * filled}{'░' * empty}[/{color}] {score:.2f}"

    async def analyze(self, query: str, files: list):
        """Analyze files and update dashboard."""
        self.relevances = await self.scorer.score_files(query, files, self.max_tokens)
        self.total_tokens = sum(r.token_count for r in self.relevances if r.include)
        self.saved_tokens = sum(r.token_count for r in self.relevances if not r.include)

    def show(self):
        """Display the dashboard."""
        console.print(self.render())
```

---

## 7. Phase 4: Integration & Polish

### 7.1 MCP Configuration

**Final `~/.claude.json` additions:**

```json
{
  "mcpServers": {
    "devmemory": {
      "command": "python",
      "args": ["-m", "devmemory.mcp_server"],
      "env": {
        "DEVMEMORY_DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/devmemory",
        "OLLAMA_URL": "http://localhost:11434"
      }
    },
    "codemcp": {
      "command": "python",
      "args": ["-m", "codemcp.server"],
      "env": {
        "CODEMCP_DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/devmemory",
        "CODEMCP_REPOS": "/Users/d/claude-code",
        "OLLAMA_URL": "http://localhost:11434"
      }
    },
    "contextlens": {
      "command": "python",
      "args": ["-m", "contextlens.server"],
      "env": {
        "CONTEXTLENS_MAX_TOKENS": "200000"
      }
    }
  }
}
```

### 7.2 Docker Compose (Development)

```yaml
version: "3.8"

services:
  devmemory-db:
    image: timescale/timescaledb-ha:pg16
    container_name: devmemory-db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: devmemory
    ports:
      - "5433:5432"
    volumes:
      - devmemory-data:/home/postgres/pgdata/data
      - ./docker/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  devmemory-data:
```

### 7.3 Pyproject.toml (Complete)

```toml
[project]
name = "dev-memory-suite"
version = "0.1.0"
description = "Developer Memory & Context Suite - Capture, understand, and optimize your development knowledge"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [{name = "Saagar"}]

dependencies = [
    # Core
    "fastapi>=0.115.0",
    "uvicorn>=0.32.0",
    "typer>=0.14.0",
    "rich>=13.9.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "httpx>=0.28.0",

    # Database
    "sqlalchemy>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pgvector>=0.3.6",

    # AI/ML
    "ollama>=0.4.7",
    "instructor>=1.7.0",
    "tiktoken>=0.8.0",
    "sentence-transformers>=3.4.0",

    # Git/Code
    "gitpython>=3.1.45",
    "watchdog>=6.0.0",
    "tree-sitter>=0.23.4",
    "tree-sitter-python>=0.23.6",
    "tree-sitter-javascript>=0.23.1",
    "tree-sitter-typescript>=0.23.2",

    # MCP
    "mcp>=1.25.0",

    # Utilities
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.25.0",
    "pytest-cov>=6.0.0",
    "mypy>=1.14.0",
    "ruff>=0.8.0",
]

reranking = [
    "rerankers>=0.10.0",
]

[project.scripts]
devmemory = "devmemory.cli:app"
codemcp = "codemcp.cli:app"
contextlens = "contextlens.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["devmemory", "codemcp", "contextlens", "shared"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]

[tool.mypy]
python_version = "3.11"
strict = true
plugins = ["pydantic.mypy"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP"]
```

---

## 8. Testing Strategy

### 8.1 Test Structure

```
tests/
├── conftest.py                 # Shared fixtures
├── integration/
│   ├── test_full_flow.py       # End-to-end tests
│   └── test_mcp_servers.py     # MCP protocol tests
├── devmemory/
│   ├── test_capture.py
│   ├── test_entities.py
│   ├── test_search.py
│   └── test_cli.py
├── codemcp/
│   ├── test_parser.py
│   ├── test_indexer.py
│   └── test_tools.py
└── contextlens/
    ├── test_scoring.py
    ├── test_optimization.py
    └── test_dashboard.py
```

### 8.2 Key Test Cases

```python
# tests/conftest.py
import pytest
import asyncio
from pathlib import Path

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def db_connection():
    """Create test database connection."""
    from shared.db import create_test_db
    conn = await create_test_db()
    yield conn
    await conn.close()

@pytest.fixture
def sample_repo(tmp_path):
    """Create a sample repository for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Create sample Python file
    (repo_path / "main.py").write_text('''
"""Main module."""

def greet(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {name}!"

class Calculator:
    """Simple calculator."""

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b
''')

    return repo_path

# tests/devmemory/test_search.py
import pytest
from devmemory.search.hybrid import HybridSearchService, SearchFilters

@pytest.mark.asyncio
async def test_hybrid_search_returns_results(db_connection):
    """Test that hybrid search returns relevant results."""
    service = HybridSearchService(db_connection)

    # Add test memory
    await db_connection.execute("""
        INSERT INTO dev_memories (memory_type, content, embedding)
        VALUES ('note', 'Fixed postgres connection timeout by increasing pool size', $1)
    """, [0.1] * 768)  # Dummy embedding

    results = await service.search("postgres timeout fix", limit=5)

    assert len(results) > 0
    assert "postgres" in results[0].content.lower()

@pytest.mark.asyncio
async def test_temporal_filtering(db_connection):
    """Test temporal filtering in search."""
    service = HybridSearchService(db_connection)

    results = await service.search_with_temporal(
        "any query",
        "last week",
        limit=10
    )

    # All results should be from last week
    from datetime import datetime, timedelta
    week_ago = datetime.now() - timedelta(days=7)

    for r in results:
        assert r.captured_at >= week_ago

# tests/codemcp/test_parser.py
import pytest
from codemcp.parser.treesitter import TreeSitterParser

def test_parse_python_function(sample_repo):
    """Test parsing Python functions."""
    parser = TreeSitterParser()

    symbols, imports = parser.parse_file(sample_repo / "main.py")

    # Should find greet function and Calculator class
    names = [s.name for s in symbols]
    assert "greet" in names
    assert "Calculator" in names
    assert "add" in names  # Method

def test_extract_docstrings(sample_repo):
    """Test docstring extraction."""
    parser = TreeSitterParser()

    symbols, _ = parser.parse_file(sample_repo / "main.py")

    greet = next(s for s in symbols if s.name == "greet")
    assert greet.docstring == "Greet someone by name."
```

---

## 9. Deployment & Operations

### 9.1 Installation Script

```bash
#!/bin/bash
# install.sh - Install Dev Memory Suite

set -e

echo "Installing Dev Memory Suite..."

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "Python 3.11+ required"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "Docker required"; exit 1; }
command -v ollama >/dev/null 2>&1 || { echo "Ollama required"; exit 1; }

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install package
pip install -e ".[dev,reranking]"

# Start database
docker compose up -d devmemory-db

# Wait for database
echo "Waiting for database..."
sleep 5

# Run migrations
alembic upgrade head

# Pull required Ollama models
echo "Pulling Ollama models..."
ollama pull nomic-embed-text:v1.5
ollama pull qwen2.5-coder:7b

# Initialize DevMemory
devmemory init

# Add MCP servers to Claude config
echo "
Add these to your ~/.claude.json mcpServers:

\"devmemory\": {
  \"command\": \"$(which python)\",
  \"args\": [\"-m\", \"devmemory.mcp_server\"]
},
\"codemcp\": {
  \"command\": \"$(which python)\",
  \"args\": [\"-m\", \"codemcp.server\"]
}
"

echo "Installation complete!"
```

### 9.2 Daily Operations

```bash
# Start watching repositories
devmemory watch ~/claude-code &

# Check status
devmemory stats

# Search your memory
devmemory search "how to handle auth tokens"

# Index a new repo for CodeMCP
# (via Claude Code with codemcp MCP server)
# Use: index_repo tool

# View context optimization
contextlens analyze "implement user authentication" --dir ~/claude-code/my-project
```

---

## 10. Task Breakdown

### Phase 1: DevMemory (14 days)

#### Week 1: Foundation
| Day | Tasks |
|-----|-------|
| 1 | Project setup, pyproject.toml, directory structure |
| 2 | Database schema, Alembic migrations |
| 3 | Shared config, database connection pool |
| 4 | Embedding service (Ollama integration) |
| 5 | Basic CLI skeleton (Typer + Rich) |
| 6 | Manual note capture (`devmemory add`) |
| 7 | Basic hybrid search implementation |

#### Week 2: Capture & Entities
| Day | Tasks |
|-----|-------|
| 8 | GitWatcher implementation (watchdog + gitpython) |
| 9 | Git commit processing and storage |
| 10 | Entity extraction (Instructor + Ollama) |
| 11 | Entity storage and deduplication |
| 12 | Relationship inference |
| 13 | Temporal filtering |
| 14 | MCP server wrapper + testing |

### Phase 2: CodeMCP (10 days)

#### Week 1: Indexing
| Day | Tasks |
|-----|-------|
| 15 | Tree-sitter setup, Python parser |
| 16 | TypeScript/JavaScript parsers |
| 17 | Symbol extraction and storage |
| 18 | Batch indexer |
| 19 | Embedding generation for symbols |

#### Week 2: Search & MCP
| Day | Tasks |
|-----|-------|
| 20 | Semantic search implementation |
| 21 | search_code, explain_function tools |
| 22 | Dependency graph building |
| 23 | find_related, get_architecture tools |
| 24 | MCP server, Claude config, testing |

### Phase 3: ContextLens (7 days)

| Day | Tasks |
|-----|-------|
| 25 | Token counting (tiktoken) |
| 26 | Relevance scoring implementation |
| 27 | File selection algorithm |
| 28 | CLI dashboard (Rich TUI) |
| 29 | CodeMCP + DevMemory integration |
| 30 | MCP server |
| 31 | Testing and polish |

### Phase 4: Integration (3 days)

| Day | Tasks |
|-----|-------|
| 32 | End-to-end integration testing |
| 33 | Performance optimization |
| 34 | Documentation, README, install script |

---

## Appendix A: Research Sources

### MCP Development
- [Model Context Protocol Official](https://modelcontextprotocol.io/)
- [MCP Best Practices](https://mcp-best-practice.github.io/mcp-best-practice/best-practice/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

### Hybrid Search
- [ParadeDB Hybrid Search](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual)
- [Hybrid Retrieval with BM25 + pgvector](https://medium.com/@richardhightower/stop-the-hallucinations-hybrid-retrieval-with-bm25-pgvector-embedding-rerank-llm-rubric-rerank-895d8f7c7242)
- [Postgres Hybrid Search](https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/)

### Tree-sitter & Code Analysis
- [Semantic Code Indexing with AST and Tree-sitter](https://medium.com/@email2dineshkuppan/semantic-code-indexing-with-ast-and-tree-sitter-for-ai-agents-part-1-of-3-eb5237ba687a)
- [Building RAG on Codebases](https://lancedb.com/blog/building-rag-on-codebases-part-1/)
- [cAST: AST-based Chunking for RAG](https://arxiv.org/html/2506.15655v1)

### Knowledge Graphs
- [Neo4j GraphRAG Python Package](https://neo4j.com/blog/news/graphrag-python-package/)
- [From LLMs to Knowledge Graphs](https://medium.com/@claudiubranzan/from-llms-to-knowledge-graphs-building-production-ready-graph-systems-in-2025-2b4aff1ec99a)

---

## Appendix B: Local Environment Reference

### Ollama Models
```
nomic-embed-text:latest (274 MB) - Embeddings
qwen2.5-coder:7b (4.7 GB) - Code understanding
qwen2.5:7b (4.7 GB) - General reasoning
deepseek-r1:14b (9 GB) - Complex tasks
```

### Docker Containers
```
knowledge-db (timescale/timescaledb-ha:pg16) - Existing KAS database
```

### Key Python Packages
```
mcp==1.25.0, instructor==1.14.1, llama-index==0.14.12
sentence-transformers==3.4.1, rerankers==0.10.0, spacy==3.8.11
GitPython==3.1.45, watchdog==6.0.0
```

---

**End of Implementation Plan**

*This document is the complete A-to-Z guide for building the Developer Memory & Context Suite.*
