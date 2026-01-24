# Knowledge Activation System

## Quick Start for New Session

**READ FIRST:** `docs/SESSION_HANDOFF.md` contains complete context including:
- What KAS is and why it exists
- All completed work (P1-P38 + Integrations)
- Key files reference
- What's next

**Current Phase:** ✅ Production Ready
**Status:** All features complete, 7 integrations available

## Project Overview

A hybrid Obsidian-centric personal knowledge management system with:
- AI-powered semantic + keyword hybrid search
- Content ingestion (YouTube, bookmarks, local files)
- FSRS spaced repetition for active engagement
- Query routing and multi-hop reasoning
- Entity extraction and knowledge graph
- Multiple platform integrations

## Current Metrics (2026-01-20)

| Metric | Value |
|--------|-------|
| Documents | 2,600+ |
| Chunks | 11,300+ |
| Entities | 1,400+ |
| Tests | 501 passing |
| API Endpoints | 40+ routes |
| **Evaluation Score** | **95.57%** |
| Integrations | 7 |

## Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Database | PostgreSQL + pgvector + pgvectorscale | 16 + 0.7.x |
| Backend | FastAPI (Python) | 0.115+ |
| Frontend | Next.js 15 + shadcn/ui | 15.x |
| Embeddings | Nomic Embed Text v1.5 via Ollama | 768 dims |
| Reranking | mxbai-rerank-large-v2 | - |
| Spaced Rep | FSRS (py-fsrs) | 6.3.0 |
| Package Manager | uv | Latest |

## Available Integrations

| Integration | Location | Status |
|-------------|----------|--------|
| MCP Server | `mcp-server/` | ✅ Production |
| Web UI | `web/` | ✅ Production |
| CLI | `cli.py` | ✅ Production |
| iOS Shortcuts | `/shortcuts/*` API | ✅ Production |
| Raycast | `integrations/raycast/` | ✅ Ready |
| Browser Ext | `integrations/browser-extension/` | ✅ Ready |
| n8n Node | `integrations/n8n/` | ✅ Ready |
| Python SDK | `sdk/python/kas_client/` | ✅ Production |

## Quick Commands

```bash
# Start database
docker compose up -d

# Run API server
PYTHONPATH=src uv run uvicorn knowledge.api.main:app --reload

# Run tests
PYTHONPATH=src uv run pytest tests/ -v

# Run evaluation
PYTHONPATH=src uv run python evaluation/evaluate.py --verbose

# CLI commands
uv run python cli.py search "query"
uv run python cli.py stats
uv run python cli.py doctor
uv run python cli.py maintenance

# Launchd jobs
launchctl list | grep com.kas
launchctl start com.kas.maintenance
tail -f /tmp/kas-maintenance.log
```

## Key Files Reference

### API Routes
| Route | Purpose |
|-------|---------|
| `routes/search.py` | Hybrid search with reranking |
| `routes/content.py` | Content CRUD operations |
| `routes/shortcuts.py` | iOS Shortcuts integration |
| `routes/batch.py` | Batch operations |
| `routes/entities.py` | Entity extraction |
| `routes/auth.py` | API key management |

### Core Modules
| File | Purpose |
|------|---------|
| `search.py` | Hybrid search (BM25 + vector + RRF) |
| `reranker.py` | Cross-encoder reranking |
| `query_router.py` | Query classification |
| `multihop.py` | Multi-hop reasoning |
| `autotag.py` | LLM-based auto-tagging |
| `entity_extraction.py` | Entity and relationship extraction |

## Documentation

| Document | Purpose |
|----------|---------|
| `docs/SESSION_HANDOFF.md` | **START HERE** - Session continuity |
| `docs/PROJECT_STATUS.md` | Overall status and metrics |
| `docs/INTEGRATIONS.md` | Integration documentation |
| `docs/ROADMAP.md` | Future priorities |

## What's Next

### High Priority
1. Push ai-ml category to 95% (currently 91%)
2. Push infrastructure category to 95% (currently 94%)
3. Publish Raycast extension to Store
4. Publish browser extension to Chrome Web Store

### Medium Priority
5. Multi-user support with user isolation
6. Mobile native app (iOS/Android)
7. Voice search integration

See `docs/ROADMAP.md` for complete roadmap.

---

**Last Updated:** 2026-01-20
**Branch:** `feat/knowledge-activation-system`
**Tests:** 501 passing
