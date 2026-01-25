# Knowledge Engine

## Project Overview
Cost-optimized knowledge infrastructure for AI applications. Designed to start FREE and scale to enterprise.

## Cost Tiers

| Tier | Components | Monthly Cost |
|------|------------|--------------|
| **FREE** (default) | Ollama + Qdrant + PostgreSQL (self-hosted) | **$0** |
| **Graph** | + Neo4j Community (self-hosted) | $0 |
| **Premium** | + Voyage AI + Cohere + Anthropic | ~$50-200 |
| **Enterprise** | + Qdrant Cloud + Neo4j Aura | ~$500-1000 |

## Technology Stack

| Component | FREE (default) | Premium (upgrade) |
|-----------|---------------|-------------------|
| Embeddings | Ollama (nomic-embed-text) | Voyage AI |
| Reranking | Ollama (bge-reranker-v2-m3) | Cohere Rerank |
| LLM | Ollama (llama3.2) | Anthropic Claude |
| Vector DB | Qdrant (Docker) | Qdrant Cloud |
| Graph DB | Disabled / Neo4j Community | Neo4j Aura |
| Metadata | PostgreSQL (Docker) | PostgreSQL |

## Quick Start (FREE)

```bash
# 1. Make sure Ollama is running with required models
ollama serve
ollama pull nomic-embed-text
ollama pull qllama/bge-reranker-v2-m3
ollama pull llama3.2

# 2. Start databases
docker compose up -d

# 3. Install and run
pip install -e .
uvicorn knowledge_engine.api.main:app --reload
```

## Commands

```bash
# Core (FREE tier)
docker compose up -d                        # Start Qdrant + PostgreSQL
docker compose --profile graph up -d        # Add Neo4j
docker compose --profile cache up -d        # Add Redis

# Run API
uvicorn knowledge_engine.api.main:app --reload

# Run MCP server (for Claude Desktop)
pip install -e ".[mcp]"
python -m knowledge_engine.mcp.server

# Install premium providers
pip install -e ".[premium]"

# Install all optional features
pip install -e ".[all]"

# Tests
pytest
```

## Environment Variables

```bash
# Switch to premium embeddings
EMBEDDING_PROVIDER=voyage
VOYAGE_API_KEY=your-key

# Switch to premium reranking
RERANK_PROVIDER=cohere
COHERE_API_KEY=your-key

# Enable graph database
GRAPH_ENABLED=true
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/ingest/document` | POST | Ingest a document |
| `/v1/search` | POST | Hybrid search |
| `/v1/query` | POST | RAG query |
| `/v1/memory/store` | POST | Store memory |
| `/v1/memory/recall` | POST | Recall memories |
| `/health` | GET | Health check |

## MCP Tools

| Tool | Description |
|------|-------------|
| `knowledge_search` | Search knowledge base |
| `knowledge_query` | Ask question with RAG |
| `knowledge_ingest` | Add content |
| `knowledge_remember` | Store memory |
| `knowledge_recall` | Recall memories |

## Project Structure

```
knowledge-engine/
├── src/knowledge_engine/
│   ├── api/           # FastAPI REST API
│   ├── core/          # Business logic
│   │   ├── engine.py  # Main orchestrator
│   │   ├── embeddings.py  # Ollama/Voyage
│   │   └── reranker.py    # Ollama/Cohere
│   ├── mcp/           # MCP server
│   ├── models/        # Pydantic models
│   └── storage/       # Database adapters
├── tests/
├── docs/
│   ├── ARCHITECTURE.md
│   └── IMPLEMENTATION_PLAN.md  # Full 8-phase implementation plan
└── docker-compose.yml
```

## Implementation Plan

See `docs/IMPLEMENTATION_PLAN.md` for the complete 8-phase implementation plan:

1. **Phase 1**: Core Infrastructure (DB setup, embeddings, vector storage, basic ingestion/search)
2. **Phase 2**: Enhanced Search (BM25, hybrid search, reranking)
3. **Phase 3**: RAG (context assembly, LLM integration, citations)
4. **Phase 4**: Memory System (store/recall, multi-tenancy)
5. **Phase 5**: MCP Integration (Claude Desktop/Code tools)
6. **Phase 6**: Content Ingestion (URL, files, YouTube)
7. **Phase 7**: Graph Database (Neo4j, optional)
8. **Phase 8**: Production Hardening

## Upgrade Path

1. **Start FREE**: Ollama + Docker databases
2. **Need better search?**: Add `RERANK_PROVIDER=cohere`
3. **Need better embeddings?**: Add `EMBEDDING_PROVIDER=voyage`
4. **Need graph relations?**: Add `GRAPH_ENABLED=true`
5. **Need cloud scale?**: Switch to Qdrant Cloud + Neo4j Aura
