# Knowledge Engine

Cost-optimized knowledge infrastructure for AI applications. **Starts FREE**, scales to enterprise.

## Features

- **Hybrid Search**: Vector + BM25 + (optional) Graph
- **RAG with Citations**: Question answering with confidence scores
- **Memory System**: Persistent memory storage and recall
- **Multi-tenancy**: Namespace isolation for projects
- **MCP Integration**: Works with Claude Desktop and Claude Code

## Cost Tiers

| Tier | What You Get | Monthly Cost |
|------|--------------|--------------|
| **FREE** | Ollama + Qdrant + PostgreSQL (all self-hosted) | **$0** |
| **Premium** | + Voyage AI embeddings + Cohere reranking | ~$50-200 |
| **Enterprise** | + Managed databases + Anthropic API | ~$500+ |

## Quick Start (FREE Tier)

### Prerequisites

- Python 3.11+
- Docker
- [Ollama](https://ollama.ai/) installed and running

### Setup

```bash
# 1. Clone and enter directory
cd knowledge-engine

# 2. Pull Ollama models (FREE)
ollama pull nomic-embed-text
ollama pull qllama/bge-reranker-v2-m3
ollama pull llama3.2

# 3. Start databases (FREE, self-hosted)
docker compose up -d

# 4. Install dependencies
pip install -e .

# 5. Run the API
uvicorn knowledge_engine.api.main:app --reload

# 6. Test it
curl http://localhost:8000/health
```

That's it! You now have a fully functional knowledge engine at **zero cost**.

## Usage

### REST API

```python
import httpx

# Ingest a document
httpx.post("http://localhost:8000/v1/ingest/document", json={
    "content": "Your document content here",
    "title": "My Document"
})

# Search
httpx.post("http://localhost:8000/v1/search", json={
    "query": "What is...",
    "limit": 10
})

# Store a memory
httpx.post("http://localhost:8000/v1/memory/store", json={
    "content": "Remember this fact",
    "memory_type": "fact"
})
```

### MCP (Claude Desktop/Code)

```bash
# Install MCP support
pip install -e ".[mcp]"

# Add to Claude Desktop config
```

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

## Upgrading to Premium

When you're ready for better quality:

```bash
# 1. Install premium dependencies
pip install -e ".[premium]"

# 2. Set API keys in .env
EMBEDDING_PROVIDER=voyage
VOYAGE_API_KEY=your-key

RERANK_PROVIDER=cohere
COHERE_API_KEY=your-key
```

## Architecture

```
┌─────────────────────────────────────────┐
│           Your AI Projects              │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
┌───────────────┐   ┌───────────────┐
│   REST API    │   │  MCP Server   │
└───────┬───────┘   └───────┬───────┘
        │                   │
        └─────────┬─────────┘
                  ▼
┌─────────────────────────────────────────┐
│         Knowledge Engine Core           │
│                                         │
│  Embeddings: Ollama (FREE) / Voyage AI  │
│  Reranking:  Ollama (FREE) / Cohere     │
└─────────────────┬───────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
┌───────┐   ┌─────────┐   ┌──────────┐
│Qdrant │   │PostgreSQL│   │ Neo4j   │
│(FREE) │   │ (FREE)   │   │(optional)│
└───────┘   └──────────┘   └──────────┘
```

## License

MIT
