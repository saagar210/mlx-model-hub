# Quick Start Guide

## For New Chat Sessions

This document provides everything needed to continue implementation.

## Current Status

**Ready for Phase 1 Implementation**

All planning complete. No blockers.

## What to Build First (Phase 1)

1. `docker-compose.yml` - PostgreSQL + pgvector + pgvectorscale
2. `docker/postgres/init.sql` - Full schema with triggers and indexes
3. `pyproject.toml` - Python dependencies
4. `src/knowledge/config.py` - Configuration management
5. `src/knowledge/db.py` - Database connection and queries
6. `src/knowledge/embeddings.py` - Nomic via Ollama integration
7. `src/knowledge/search.py` - Hybrid search with RRF fusion
8. `cli.py` - Basic CLI with search command
9. Tests for all above

## Key Files to Read

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project overview and quick reference |
| `docs/IMPLEMENTATION_PLAN.md` | Full task breakdown with checkboxes |
| `docs/DATABASE_SCHEMA.md` | Complete SQL schema |
| `docs/ARCHITECTURE.md` | System design and data flows |
| `docs/DECISIONS.md` | All user decisions for reference |

## Technology Quick Reference

```
Database:     PostgreSQL 16 + pgvector 0.7.x + pgvectorscale
Backend:      FastAPI (Python 3.11+)
Frontend:     Next.js 15 + shadcn/ui
Embeddings:   Nomic Embed Text v1.5 (768 dims) via Ollama
Reranking:    mxbai-rerank-large-v2 via Ollama
Spaced Rep:   py-fsrs 6.3.0
Transcribe:   Whisper large-v3 (fallback for YouTube)
```

## Python Dependencies (Phase 1)

```toml
[project]
dependencies = [
    "asyncpg>=0.29.0",
    "pgvector>=0.3.0",
    "httpx>=0.27.0",
    "typer>=0.12.0",
    "rich>=13.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "mypy>=1.8.0",
]
```

## Docker Quick Start

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: knowledge-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: knowledge
      POSTGRES_PASSWORD: localdev
      POSTGRES_DB: knowledge
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/postgres/init.sql:/docker-entrypoint-initdb.d/01_init.sql
    ports:
      - "127.0.0.1:5432:5432"
    command: >
      postgres
      -c shared_buffers=256MB
      -c effective_cache_size=1GB
      -c maintenance_work_mem=128MB
      -c work_mem=16MB

volumes:
  postgres_data:
```

## Obsidian Vault

Location: `~/Obsidian/`

Notes created by the system go in: `~/Obsidian/Knowledge/`

## Commands After Phase 1

```bash
# Start database
docker compose up -d

# Test search
python cli.py search "machine learning transformers"

# Check stats
python cli.py stats
```

## Success Criteria for Phase 1

- [ ] Docker starts cleanly with `docker compose up -d`
- [ ] Schema creates without errors
- [ ] Can embed text via Ollama
- [ ] Can insert content + chunks
- [ ] Hybrid search returns results
- [ ] CLI `search` command works
- [ ] All tests pass
