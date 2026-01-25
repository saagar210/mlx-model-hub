# Universal Context Engine

## Overview
Unified context aggregation layer that combines data from Knowledge Activation System, Git repositories, and browser sessions into a single queryable store with temporal knowledge graph capabilities.

## Architecture
- **Memory Model**: Zep-style bi-temporal knowledge graph (event time + ingestion time)
- **Vector Store**: PostgreSQL + pgvector + pgvectorscale
- **Embeddings**: nomic-embed-text 768d via Ollama
- **Entity Resolution**: Rule-based + LLM-assisted

## Key Components
- `src/uce/models/` - Pydantic models for context items, entities, relationships
- `src/uce/adapters/` - Data source adapters (KAS, Git, Browser)
- `src/uce/entity_resolution/` - Entity extraction and linking
- `src/uce/search/` - Hybrid search (vector + BM25 + RRF fusion)
- `src/uce/mcp/` - MCP server for Claude Code integration
- `src/uce/api/` - FastAPI REST endpoints

## Commands
```bash
# Development
uv pip install -e ".[dev]"
pytest tests/ -v

# Start API server
uvicorn uce.main:app --reload --port 8100

# Start MCP server (stdio)
python -m uce.mcp.server

# Run migrations
python scripts/migrate.py

# Docker
docker compose -f docker/docker-compose.yml up -d
```

## Environment Variables
- `UCE_DATABASE_URL` - PostgreSQL connection string
- `UCE_OLLAMA_URL` - Ollama API URL (default: http://localhost:11434)
- `UCE_KAS_DB_URL` - Knowledge Activation System database
- `UCE_NEO4J_URI` - Neo4j connection (optional)

## MCP Integration
Add to `~/.claude.json`:
```json
"universal-context": {
  "type": "stdio",
  "command": "python",
  "args": ["-m", "uce.mcp.server"],
  "cwd": "/path/to/universal-context-engine"
}
```

## Database
- Port 5434 (to avoid conflicts with other PostgreSQL instances)
- Extensions: vector, pg_trgm
