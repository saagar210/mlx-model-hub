# Knowledge Activation System (KAS)

A personal knowledge management system with AI-powered hybrid search, content ingestion, and spaced repetition.

## Features

- **Hybrid Search**: BM25 (keyword) + Vector (semantic) search with RRF fusion
- **Cross-Encoder Reranking**: mxbai-rerank-large-v2 for improved relevance
- **Content Ingestion**: YouTube (with Whisper fallback), bookmarks, files
- **FSRS Spaced Repetition**: Active knowledge retention
- **REST API**: FastAPI backend with 20+ endpoints
- **Web UI**: Next.js 15 + shadcn/ui frontend
- **MCP Integration**: Claude Code integration via MCP server

## Quick Start

```bash
# Start PostgreSQL
docker compose up -d

# Install Python dependencies
uv sync

# Run API server
cd src && uvicorn knowledge.api.main:app --reload

# Run web frontend
cd web && npm run dev

# Run tests
pytest
```

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Content        │     │  KAS Core        │     │  Consumers      │
│  Sources        │────▶│                  │◀────│                 │
│                 │     │  PostgreSQL      │     │  Web UI         │
│  YouTube        │     │  + pgvector      │     │  CLI            │
│  Bookmarks      │     │                  │     │  MCP Server     │
│  Files          │     │  Hybrid Search   │     │  LocalCrew      │
└─────────────────┘     │  Q&A Engine      │     └─────────────────┘
                        │  FSRS Review     │
                        └──────────────────┘
```

## Technology Stack

| Component | Technology |
|-----------|------------|
| Database | PostgreSQL 16 + pgvector + pgvectorscale |
| Backend | FastAPI (Python 3.11+) |
| Frontend | Next.js 15 + shadcn/ui |
| Embeddings | Nomic Embed Text v1.5 (768 dims) |
| Reranking | mxbai-rerank-large-v2 |
| Spaced Rep | FSRS (py-fsrs 6.3.0) |

## Documentation

- [Session Handoff](docs/SESSION_HANDOFF.md) - Context for continuing development
- [Project Status](docs/PROJECT_STATUS.md) - Current status and metrics
- [Architecture](docs/ARCHITECTURE.md) - System design
- [Database Schema](docs/DATABASE_SCHEMA.md) - PostgreSQL schema
- [Quick Start](docs/QUICK_START.md) - Getting started guide
- [Deployment](docs/DEPLOYMENT.md) - Deployment options

## API Endpoints

### Search
- `GET /api/v1/search?q=query` - Hybrid search with optional reranking
- `POST /api/v1/ask` - Q&A with source citations

### Content
- `GET /api/v1/content` - List content
- `POST /api/v1/content` - Create content
- `GET /api/v1/content/{id}` - Get content by ID

### Capture
- `POST /api/v1/capture` - Quick text capture
- `POST /api/v1/capture/url` - URL capture with auto-title

### Review
- `GET /api/v1/review/due` - Get due reviews
- `POST /api/v1/review/{id}/rate` - Submit review rating

### Analytics
- `GET /api/v1/analytics/search` - Search analytics
- `GET /api/v1/analytics/gaps` - Content gaps
- `GET /api/v1/analytics/quality` - Quality metrics

## Development Status

**Phase**: Production Readiness (P11-P38)

28 priorities identified for production hardening:
- Foundation Hardening (P11-P16)
- API Maturity (P17-P22)
- Reliability & Observability (P23-P27)
- Testing & Quality (P28-P32)
- Developer Experience (P33-P36)
- Production Operations (P37-P38)

See `docs/SESSION_HANDOFF.md` for full roadmap details.

## Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_search.py -v
```

Current: **237 tests passing**

## License

Private project - not for distribution.
