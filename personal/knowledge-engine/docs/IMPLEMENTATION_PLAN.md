# Knowledge Engine - Implementation Plan

## Overview

A cost-optimized knowledge infrastructure for AI applications. Designed as a reusable foundation that other projects can build upon.

**Philosophy**: Start FREE, upgrade when needed.

## Current State

### Models Downloaded (Ollama)
- `nomic-embed-text:latest` - 768-dim embeddings (274 MB)
- `qllama/bge-reranker-v2-m3` - Reranking model (635 MB)
- `llama3.2:latest` - LLM for RAG (2.0 GB)

### Infrastructure Required
- Docker for Qdrant + PostgreSQL
- Ollama running locally

---

## Phase 1: Core Infrastructure

**Goal**: Get basic ingestion and search working end-to-end.

### 1.1 Database Setup
- [ ] Verify docker-compose.yml starts Qdrant + PostgreSQL cleanly
- [ ] Create PostgreSQL schema migrations (Alembic)
- [ ] Test Qdrant collection creation with 768-dim vectors
- [ ] Add health check endpoints for each database

**Files to create/modify**:
```
src/knowledge_engine/storage/
├── migrations/
│   ├── env.py
│   ├── versions/
│   │   └── 001_initial_schema.py
├── models.py          # SQLAlchemy models
└── postgres.py        # Already exists, verify/test
```

### 1.2 Embedding Service
- [ ] Verify OllamaEmbeddingService connects to local Ollama
- [ ] Test single text embedding
- [ ] Test batch embedding (performance baseline)
- [ ] Add embedding caching (optional, for repeated queries)

**Test commands**:
```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags

# Test embedding
curl -X POST http://localhost:11434/api/embeddings \
  -d '{"model": "nomic-embed-text", "prompt": "test"}'
```

### 1.3 Vector Storage
- [ ] Test Qdrant upsert with real embeddings
- [ ] Test Qdrant search returns correct results
- [ ] Verify payload filtering works (document_id, document_type)
- [ ] Test batch upsert performance

### 1.4 Basic Ingestion Pipeline
- [ ] Create Document model (Pydantic)
- [ ] Implement chunking strategy (sentence-based, ~512 tokens)
- [ ] Wire up: Text → Chunks → Embeddings → Qdrant
- [ ] Add PostgreSQL metadata storage

**API Endpoint**: `POST /v1/ingest/document`
```json
{
  "content": "Your text here",
  "title": "Document Title",
  "document_type": "article",
  "metadata": {}
}
```

### 1.5 Basic Search
- [ ] Implement vector-only search
- [ ] Return results with scores and payloads
- [ ] Add score threshold filtering

**API Endpoint**: `POST /v1/search`
```json
{
  "query": "What is...",
  "limit": 10,
  "filters": {"document_type": "article"}
}
```

### Phase 1 Deliverables
- Working REST API with `/health`, `/v1/ingest/document`, `/v1/search`
- Basic ingestion → embedding → storage pipeline
- Vector search with filtering

---

## Phase 2: Enhanced Search

**Goal**: Improve search quality with hybrid search and reranking.

### 2.1 BM25/Sparse Search
- [ ] Add BM25 scoring via PostgreSQL full-text search
- [ ] Or implement sparse vectors in Qdrant
- [ ] Test keyword-heavy queries work better

### 2.2 Hybrid Search (RRF Fusion)
- [ ] Implement Reciprocal Rank Fusion
- [ ] Combine vector + BM25 results
- [ ] Tune RRF k parameter (default 60)

**Algorithm**:
```python
def rrf_score(ranks: list[int], k: int = 60) -> float:
    return sum(1 / (k + r) for r in ranks)
```

### 2.3 Reranking
- [ ] Wire up OllamaReranker with `qllama/bge-reranker-v2-m3`
- [ ] Test reranking improves result relevance
- [ ] Add passthrough fallback if reranking fails
- [ ] Configure top_n parameter

### 2.4 Search Quality Testing
- [ ] Create test query dataset (20+ queries)
- [ ] Measure MRR (Mean Reciprocal Rank)
- [ ] Measure Recall@10
- [ ] A/B test: vector-only vs hybrid vs hybrid+rerank

### Phase 2 Deliverables
- Hybrid search (vector + BM25)
- Reranking for result quality
- Search quality metrics baseline

---

## Phase 3: RAG (Retrieval-Augmented Generation)

**Goal**: Question answering with citations.

### 3.1 Context Assembly
- [ ] Retrieve top-k chunks via hybrid search
- [ ] Format chunks with source metadata
- [ ] Implement context window management (fit within LLM limits)

### 3.2 LLM Integration
- [ ] Wire up OllamaLLM with `llama3.2`
- [ ] Create RAG prompt template with citations
- [ ] Handle streaming responses

**Prompt Template**:
```
Answer the question based on the context below. Include [1], [2] citations.
If the answer isn't in the context, say "I don't know."

Context:
[1] {chunk_1}
[2] {chunk_2}

Question: {query}
Answer:
```

### 3.3 Confidence Scoring
- [ ] Calculate retrieval confidence (avg similarity score)
- [ ] Add "low confidence" warning when score < 0.3
- [ ] Return confidence in API response

### 3.4 Citation Extraction
- [ ] Parse citations from LLM response
- [ ] Link citations to source documents
- [ ] Return structured citation metadata

**API Endpoint**: `POST /v1/query`
```json
{
  "query": "What is...",
  "include_sources": true
}
```

**Response**:
```json
{
  "answer": "Based on the documents, ...",
  "confidence": 0.85,
  "citations": [
    {"index": 1, "document_id": "...", "chunk": "...", "score": 0.92}
  ]
}
```

### Phase 3 Deliverables
- RAG endpoint with citations
- Confidence scoring
- Streaming responses

---

## Phase 4: Memory System

**Goal**: Persistent memory storage and recall for AI agents.

### 4.1 Memory Model
- [ ] Define memory types: fact, preference, context, episode
- [ ] Create Memory Pydantic model
- [ ] Add PostgreSQL table for memories
- [ ] Create memory-specific Qdrant collection

### 4.2 Memory Storage
- [ ] Embed memory content
- [ ] Store in both Qdrant (vector) and PostgreSQL (metadata)
- [ ] Add timestamp and decay tracking
- [ ] Support namespaces for multi-tenancy

**API Endpoint**: `POST /v1/memory/store`
```json
{
  "content": "User prefers dark mode",
  "memory_type": "preference",
  "namespace": "user_123"
}
```

### 4.3 Memory Recall
- [ ] Search memories by semantic similarity
- [ ] Filter by type, namespace, recency
- [ ] Apply time decay weighting
- [ ] Return with relevance scores

**API Endpoint**: `POST /v1/memory/recall`
```json
{
  "query": "What are user preferences?",
  "memory_types": ["preference"],
  "namespace": "user_123",
  "limit": 5
}
```

### 4.4 Memory Management
- [ ] List memories endpoint
- [ ] Delete memory endpoint
- [ ] Bulk delete by namespace/type
- [ ] Memory expiration (optional)

### Phase 4 Deliverables
- Memory store/recall API
- Multi-tenant namespaces
- Memory type filtering

---

## Phase 5: MCP Integration

**Goal**: Enable Claude Desktop/Code to use Knowledge Engine.

### 5.1 MCP Server Setup
- [ ] Implement MCP server using `mcp` library
- [ ] Register tools with proper schemas
- [ ] Add stdio transport for CLI usage

### 5.2 MCP Tools
```python
# Tools to implement
knowledge_search(query, limit, filters)    # Search documents
knowledge_query(query)                      # RAG with answer
knowledge_ingest(content, title, type)     # Add content
knowledge_remember(content, type)           # Store memory
knowledge_recall(query, types, limit)       # Recall memories
```

### 5.3 Claude Desktop Configuration
```json
{
  "mcpServers": {
    "knowledge-engine": {
      "command": "python",
      "args": ["-m", "knowledge_engine.mcp.server"]
    }
  }
}
```

### 5.4 Testing with Claude
- [ ] Test each tool from Claude Desktop
- [ ] Verify error handling and responses
- [ ] Document tool usage examples

### Phase 5 Deliverables
- Working MCP server
- 5 registered tools
- Claude Desktop integration guide

---

## Phase 6: Content Ingestion (Extended)

**Goal**: Support various content types beyond plain text.

### 6.1 URL/Web Content
- [ ] Fetch and parse web pages
- [ ] Extract main content (readability)
- [ ] Handle different content types (article, blog, docs)
- [ ] Store URL as source reference

### 6.2 File Ingestion
- [ ] PDF parsing (pymupdf or pdfplumber)
- [ ] Markdown parsing
- [ ] Code file parsing (with language detection)
- [ ] Store file path as reference (don't copy files)

### 6.3 YouTube Transcripts
- [ ] Fetch transcripts via youtube-transcript-api
- [ ] Chunk by timestamp segments
- [ ] Store video metadata (title, channel, duration)
- [ ] Fallback: note when transcript unavailable

### 6.4 Batch Ingestion
- [ ] Ingest multiple documents endpoint
- [ ] Background processing with status tracking
- [ ] Progress reporting

### Phase 6 Deliverables
- URL ingestion
- File ingestion (PDF, Markdown, Code)
- YouTube transcript ingestion

---

## Phase 7: Graph Database (Optional)

**Goal**: Add relationship-based knowledge via Neo4j.

### 7.1 Neo4j Setup
- [ ] Enable via `docker compose --profile graph up -d`
- [ ] Set `GRAPH_ENABLED=true`
- [ ] Create graph schema (nodes, relationships)

### 7.2 Entity Extraction
- [ ] Extract entities from chunks (using LLM)
- [ ] Create entity nodes in Neo4j
- [ ] Link entities to source documents

### 7.3 Relationship Extraction
- [ ] Extract relationships between entities
- [ ] Store in Neo4j with relationship types
- [ ] Support custom relationship schemas

### 7.4 Graph-Enhanced Search
- [ ] Traverse relationships for related content
- [ ] Combine graph traversal with vector search
- [ ] Use graph for "related to X" queries

### Phase 7 Deliverables
- Neo4j integration (optional profile)
- Entity/relationship extraction
- Graph-enhanced search

---

## Phase 8: Production Hardening

**Goal**: Make the system production-ready.

### 8.1 Error Handling
- [ ] Comprehensive error types
- [ ] Graceful degradation (reranking fails → passthrough)
- [ ] Retry logic with exponential backoff
- [ ] Circuit breakers for external services

### 8.2 Logging & Monitoring
- [ ] Structured logging (JSON)
- [ ] Request tracing (correlation IDs)
- [ ] Metrics export (Prometheus format)
- [ ] Health check dashboard

### 8.3 Security
- [ ] API key authentication (optional)
- [ ] Rate limiting
- [ ] Input validation and sanitization
- [ ] Namespace isolation verification

### 8.4 Performance
- [ ] Connection pooling (already in config)
- [ ] Query optimization
- [ ] Batch processing optimization
- [ ] Load testing with locust

### 8.5 Documentation
- [ ] OpenAPI/Swagger docs (auto-generated)
- [ ] Usage examples
- [ ] Deployment guide
- [ ] Upgrade path guide (FREE → Premium)

### Phase 8 Deliverables
- Production-ready error handling
- Monitoring and logging
- Security features
- Performance optimization

---

## Upgrade Paths

### FREE → Premium Embeddings
```bash
# .env
EMBEDDING_PROVIDER=voyage
VOYAGE_API_KEY=your-key
```

### FREE → Premium Reranking
```bash
# .env
RERANK_PROVIDER=cohere
COHERE_API_KEY=your-key
```

### FREE → Premium LLM
```bash
# .env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key
```

### Enable Graph Database
```bash
docker compose --profile graph up -d
# .env
GRAPH_ENABLED=true
```

### Enable Redis Cache
```bash
docker compose --profile cache up -d
# .env
REDIS_ENABLED=true
```

---

## Implementation Checklist Summary

### Phase 1: Core Infrastructure
- [ ] Database setup and migrations
- [ ] Embedding service working
- [ ] Vector storage working
- [ ] Basic ingestion pipeline
- [ ] Basic search endpoint

### Phase 2: Enhanced Search
- [ ] BM25/sparse search
- [ ] Hybrid search with RRF
- [ ] Reranking integration
- [ ] Search quality metrics

### Phase 3: RAG
- [ ] Context assembly
- [ ] LLM integration
- [ ] Confidence scoring
- [ ] Citations

### Phase 4: Memory System
- [ ] Memory model
- [ ] Store/recall endpoints
- [ ] Multi-tenant namespaces
- [ ] Memory management

### Phase 5: MCP Integration
- [ ] MCP server
- [ ] All 5 tools
- [ ] Claude Desktop config

### Phase 6: Content Ingestion
- [ ] URL ingestion
- [ ] File ingestion
- [ ] YouTube transcripts
- [ ] Batch processing

### Phase 7: Graph (Optional)
- [ ] Neo4j setup
- [ ] Entity extraction
- [ ] Relationship extraction
- [ ] Graph search

### Phase 8: Production
- [ ] Error handling
- [ ] Logging/monitoring
- [ ] Security
- [ ] Performance
- [ ] Documentation

---

## Quick Start Commands

```bash
# 1. Start infrastructure
docker compose up -d

# 2. Verify databases
curl http://localhost:6333/health    # Qdrant
curl http://localhost:5432           # PostgreSQL (will fail, use psql)

# 3. Verify Ollama models
ollama list

# 4. Install dependencies
pip install -e .

# 5. Run tests
pytest

# 6. Start API
uvicorn knowledge_engine.api.main:app --reload

# 7. Test endpoints
curl http://localhost:8000/health
curl -X POST http://localhost:8000/v1/search -H "Content-Type: application/json" \
  -d '{"query": "test"}'
```

---

## File Structure (Final)

```
knowledge-engine/
├── src/knowledge_engine/
│   ├── __init__.py
│   ├── config.py                 # Settings with provider selection
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app
│   │   ├── routes/
│   │   │   ├── health.py
│   │   │   ├── ingest.py
│   │   │   ├── search.py
│   │   │   ├── query.py
│   │   │   └── memory.py
│   │   └── deps.py              # Dependencies (engine instance)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── engine.py            # Main orchestrator
│   │   ├── embeddings.py        # Ollama/Voyage provider
│   │   ├── reranker.py          # Ollama/Cohere provider
│   │   ├── llm.py               # Ollama/Anthropic provider
│   │   ├── chunker.py           # Text chunking
│   │   └── fusion.py            # RRF fusion
│   ├── mcp/
│   │   ├── __init__.py
│   │   └── server.py            # MCP server with tools
│   ├── models/
│   │   ├── __init__.py
│   │   ├── document.py
│   │   ├── chunk.py
│   │   ├── memory.py
│   │   └── search.py
│   └── storage/
│       ├── __init__.py
│       ├── qdrant.py            # Vector DB
│       ├── postgres.py          # Metadata DB
│       ├── neo4j.py             # Graph DB (optional)
│       ├── redis.py             # Cache (optional)
│       └── migrations/
│           └── versions/
├── tests/
│   ├── test_config.py
│   ├── test_embeddings.py
│   ├── test_search.py
│   └── ...
├── docs/
│   ├── ARCHITECTURE.md
│   └── IMPLEMENTATION_PLAN.md   # This file
├── docker-compose.yml
├── pyproject.toml
├── CLAUDE.md
├── README.md
└── .env.example
```

---

## Notes for AI Reference

This project is designed as **infrastructure** for other AI projects:

1. **Multi-tenancy**: Use `namespace` parameter to isolate data per project
2. **Provider abstraction**: Easy to swap embeddings/reranking/LLM providers
3. **MCP ready**: Claude Desktop/Code can use this directly
4. **Cost-optimized**: Start FREE with Ollama, upgrade when needed
5. **No vendor lock-in**: All components are swappable

**Integration pattern for consuming projects**:
```python
from knowledge_engine.core.engine import KnowledgeEngine

engine = KnowledgeEngine()
await engine.initialize()

# Ingest content
await engine.ingest(content="...", title="...", namespace="my_project")

# Search
results = await engine.search(query="...", namespace="my_project")

# RAG query
answer = await engine.query(query="...", namespace="my_project")

# Memory
await engine.store_memory(content="...", memory_type="fact", namespace="my_project")
memories = await engine.recall_memories(query="...", namespace="my_project")
```
