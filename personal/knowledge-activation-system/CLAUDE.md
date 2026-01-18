# Knowledge Activation System

## Quick Start for New Session

**READ FIRST:** `docs/SESSION_HANDOFF.md` contains complete context including:
- What KAS is and why it exists
- All completed work (P1-P38)
- Key files reference
- SDK usage examples

**Current Phase:** ✅ Production Ready
**Status:** All 38 priorities complete

## Project Overview
A hybrid Obsidian-centric personal knowledge management system with:
- AI-powered semantic + keyword hybrid search
- Content ingestion (YouTube, bookmarks, local files)
- FSRS spaced repetition for active engagement
- Near-zero maintenance through automation

## Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Database | PostgreSQL + pgvector + pgvectorscale | 16 + 0.7.x |
| Backend | FastAPI (Python) | 0.115+ |
| Frontend | Next.js 15 + shadcn/ui | 15.x |
| Embeddings | Nomic Embed Text v1.5 via Ollama | 768 dims |
| Reranking | mxbai-rerank-large-v2 via Ollama | - |
| Spaced Rep | FSRS (py-fsrs) | 6.3.0 |
| Transcription | Whisper large-v3 (fallback) | - |
| AI Tiers | OpenRouter Free → DeepSeek → Claude | - |

## Key Design Decisions

1. **Source of Truth**: Obsidian YAML frontmatter → PostgreSQL is derived cache
2. **Search**: Hybrid (BM25 + vector) with RRF fusion, then reranking
3. **Chunking**: Adaptive by content type (YouTube: timestamps, Bookmarks: semantic, PDFs: page-level)
4. **Files**: Reference only (store paths, don't copy)
5. **Git**: Hourly auto-commit, local only
6. **Vault**: ~/Obsidian/ (existing)

## Implementation Phases

- **Phase 1**: Foundation (PostgreSQL, embeddings, hybrid search, CLI)
- **Phase 2**: Content Ingestion (YouTube + Whisper fallback, bookmarks, files)
- **Phase 3**: Intelligence Layer (Q&A with confidence scoring, reranking, auto-tags)
- **Phase 4**: Web Application (Next.js frontend)
- **Phase 5**: Active Engagement (FSRS Daily Review)
- **Phase 6**: Polish & Automation (Dependabot, Watchtower, backups)

## Three Special Features

1. **Whisper Fallback**: When YouTube lacks captions, transcribe via local Whisper
2. **Confidence Scoring**: Show "low confidence" warning when retrieval score <0.3
3. **Content Validation**: Skip empty, too-short, or error page content on ingest

## Commands

```bash
# Start database
docker compose up -d

# Run CLI
uv run python cli.py search "query"
uv run python cli.py ingest youtube <video_id>
uv run python cli.py review

# Run tests (MUST use uv run to get correct dependencies)
uv run pytest tests/ -v

# Type check
uv run mypy src/
```

## Planning Documents

- `docs/SESSION_HANDOFF.md` - **START HERE** - Complete context for new sessions
- `docs/PROJECT_STATUS.md` - Overall project status and metrics
- `docs/IMPLEMENTATION_PLAN.md` - Full phased implementation plan
- `docs/DATABASE_SCHEMA.md` - Complete PostgreSQL schema
- `docs/ARCHITECTURE.md` - System architecture and data flow
- `docs/DECISIONS.md` - All user decisions captured during planning

## Current Status (2026-01-18)

**All P1-P38 Complete** ✅

| Metric | Value |
|--------|-------|
| Documents | 1,512 |
| Chunks | 3,998 |
| Tests | 419 passing, 3 skipped |
| API Endpoints | 25+ routes |
| MCP Tools | kas_search, kas_ingest, kas_review |

### What's Included:
- Hybrid search (BM25 + vector + RRF fusion)
- Cross-encoder reranking
- Redis caching + query expansion
- API authentication + rate limiting
- Circuit breaker + graceful degradation
- Prometheus metrics + OpenTelemetry tracing
- Export/import + webhooks
- Python SDK (`sdk/python/kas_client/`)
- Load testing + evaluation framework

Run tests: `uv run pytest tests/ -v`
