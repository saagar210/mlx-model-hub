# Knowledge Activation System

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
python cli.py search "query"
python cli.py ingest youtube <video_id>
python cli.py review

# Run tests
pytest

# Type check
mypy src/
```

## Planning Documents

- `docs/IMPLEMENTATION_PLAN.md` - Full phased implementation plan
- `docs/DATABASE_SCHEMA.md` - Complete PostgreSQL schema
- `docs/ARCHITECTURE.md` - System architecture and data flow
- `docs/DECISIONS.md` - All user decisions captured during planning
