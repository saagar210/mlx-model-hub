# Universal Context Engine

Unified context aggregation layer that combines data from Knowledge Activation System, Git repositories, and browser sessions into a single queryable store with temporal knowledge graph capabilities and cross-source entity linking.

## Features

- **Hybrid Search**: Combines vector similarity (pgvector), BM25 full-text, and entity graph traversal using Reciprocal Rank Fusion (RRF)
- **Bi-temporal Knowledge Graph**: Tracks both event time and ingestion time for all facts
- **Entity Resolution**: Rule-based + alias mapping for cross-source entity linking
- **Multi-source Adapters**: KAS, Git, Browser (via Playwright MCP)
- **MCP Integration**: Exposes tools for Claude Code integration
- **REST API**: Full-featured FastAPI endpoints

## Architecture

```
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│     KAS     │ │     Git     │ │   Browser   │
│   Adapter   │ │   Adapter   │ │   Adapter   │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │
       └───────────────┼───────────────┘
                       │
              ┌────────▼────────┐
              │   Sync Engine   │
              │  + Embeddings   │
              │  + Entities     │
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │   PostgreSQL    │
              │  + pgvector     │
              └────────┬────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
│ Hybrid      │ │  REST API   │ │ MCP Server  │
│ Search      │ │  (FastAPI)  │ │ (stdio)     │
└─────────────┘ └─────────────┘ └─────────────┘
```

## Quick Start

### 1. Start PostgreSQL with pgvector

```bash
cd docker
docker compose up -d postgres
```

### 2. Install Dependencies

```bash
pip install -e ".[dev]"
```

### 3. Run Migrations

```bash
python scripts/migrate.py
```

### 4. Start the API Server

```bash
uvicorn uce.main:app --reload --port 8100
```

### 5. (Optional) Start MCP Server

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "universal-context": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "uce.mcp.server"],
      "cwd": "/path/to/universal-context-engine/src"
    }
  }
}
```

## API Endpoints

- `GET /health` - Health check
- `GET /api/v1/search?q=query` - Hybrid search
- `GET /api/v1/context/recent` - Recent context
- `GET /api/v1/context/working` - Current working context
- `GET /api/v1/entities` - List entities
- `GET /api/v1/entities/search?q=query` - Search entities

## MCP Tools

- `search_context` - Search unified context
- `get_recent_context` - Get recent activity
- `get_entity_context` - Get context for an entity
- `get_working_context` - Current working state

## Configuration

Environment variables (prefix `UCE_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `UCE_DATABASE_URL` | `postgresql+asyncpg://uce:uce@localhost:5434/universal_context` | PostgreSQL URL |
| `UCE_OLLAMA_URL` | `http://localhost:11434` | Ollama API URL |
| `UCE_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| `UCE_API_PORT` | `8100` | API port |
| `UCE_SYNC_ENABLED` | `true` | Enable background sync |

## Development

```bash
# Run tests
pytest tests/ -v

# Run with debug logging
UCE_DEBUG=true uvicorn uce.main:app --reload
```

## License

MIT
