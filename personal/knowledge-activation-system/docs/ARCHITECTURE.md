# System Architecture

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interfaces                          │
├─────────────┬─────────────────┬─────────────────────────────────┤
│    CLI      │   Web App       │   Chrome Extension              │
│  (Phase 1)  │   (Phase 4)     │   (Phase 2)                     │
└──────┬──────┴────────┬────────┴──────────────┬──────────────────┘
       │               │                       │
       └───────────────┼───────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  Search  │  │   Ask    │  │  Ingest  │  │  Review  │        │
│  │ Endpoint │  │ Endpoint │  │ Endpoints│  │ Endpoints│        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
└───────┼─────────────┼─────────────┼─────────────┼───────────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Core Services                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Hybrid Search│  │  AI Service  │  │ FSRS Engine  │          │
│  │ (BM25+Vec)   │  │ (Tiered)     │  │              │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐          │
│  │  Embeddings  │  │  Reranking   │  │  Validation  │          │
│  │  (Nomic)     │  │ (mxbai)      │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
        │                                     │
        ▼                                     ▼
┌───────────────────┐               ┌─────────────────────────────┐
│   PostgreSQL      │               │   Obsidian Vault            │
│   + pgvector      │◄─────────────►│   ~/Obsidian/               │
│   + pgvectorscale │  (sync)       │   (Source of Truth)         │
└───────────────────┘               └─────────────────────────────┘
```

## Data Flow

### Ingestion Flow

```
Content Source                Processing                    Storage
─────────────────────────────────────────────────────────────────────

YouTube Video     ──┐
                   │        ┌─────────────┐
Bookmark URL      ─┼───────►│  Validate   │──── Invalid ───► Log & Skip
                   │        │  Content    │
Local File        ──┘        └─────┬───────┘
                                   │ Valid
                                   ▼
                            ┌─────────────┐
                            │  Adaptive   │
                            │  Chunking   │
                            └─────┬───────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
             ┌───────────┐  ┌───────────┐  ┌───────────┐
             │  Embed    │  │  Create   │  │  Generate │
             │  Chunks   │  │  Obsidian │  │  Auto-Tags│
             │  (Nomic)  │  │  Note     │  │  (AI)     │
             └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
                   │              │              │
                   └──────────────┼──────────────┘
                                  ▼
                           ┌─────────────┐
                           │   Insert    │
                           │   to DB     │
                           └─────────────┘
```

### Search Flow

```
Query                   Processing                         Response
─────────────────────────────────────────────────────────────────────

User Query ─────────────────────────────────────────────────────────►
                   │
                   ▼
            ┌─────────────┐
            │   Embed     │
            │   Query     │
            └─────┬───────┘
                   │
         ┌────────┴────────┐
         ▼                 ▼
   ┌───────────┐    ┌───────────┐
   │   BM25    │    │  Vector   │
   │   Search  │    │  Search   │
   │  (Top 50) │    │  (Top 50) │
   └─────┬─────┘    └─────┬─────┘
         │                │
         └───────┬────────┘
                 ▼
          ┌─────────────┐
          │  RRF Fusion │
          │   (k=60)    │
          └─────┬───────┘
                │
                ▼
          ┌─────────────┐
          │  Rerank     │
          │  (mxbai)    │
          └─────┬───────┘
                │
                ▼
          ┌─────────────┐
          │  Return     │──────────────────────────────────► Results
          │  Top 10     │
          └─────────────┘
```

### Q&A Flow (with Confidence Scoring)

```
Question                Processing                         Response
─────────────────────────────────────────────────────────────────────

User Question ──────────────────────────────────────────────────────►
                   │
                   ▼
            ┌─────────────┐
            │  Hybrid     │
            │  Search     │
            └─────┬───────┘
                  │
                  ▼
            ┌─────────────┐
            │  Rerank     │
            └─────┬───────┘
                  │
                  ▼
            ┌─────────────┐
            │  Calculate  │
            │  Confidence │
            └─────┬───────┘
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
   confidence < 0.3    confidence >= 0.3
        │                   │
        ▼                   ▼
   ┌───────────┐     ┌───────────┐
   │  Return   │     │  Generate │
   │  "Low     │     │  Answer   │
   │  Conf"    │     │  (AI)     │
   └─────┬─────┘     └─────┬─────┘
         │                 │
         └────────┬────────┘
                  ▼
            ┌─────────────┐
            │  Return     │──────────────────────────────► Answer +
            │  Response   │                                Citations +
            └─────────────┘                                Confidence
```

## Component Details

### Hybrid Search (RRF Fusion)

```
RRF Score = Σ (1 / (k + rank))

Where:
- k = 60 (constant to prevent division by small numbers)
- rank = position in result list (1-indexed)

Example:
- Document A: rank 1 in BM25, rank 5 in vector
  Score = 1/(60+1) + 1/(60+5) = 0.0164 + 0.0154 = 0.0318

- Document B: rank 3 in BM25, rank 2 in vector
  Score = 1/(60+3) + 1/(60+2) = 0.0159 + 0.0161 = 0.0320

Document B wins (higher combined score)
```

### Confidence Scoring

```python
confidence = (top_score * 0.6) + (avg_top3_score * 0.4)

Thresholds:
- < 0.3: "low" - Show warning, don't generate answer
- 0.3-0.7: "medium" - Generate answer with caution note
- > 0.7: "high" - Generate answer confidently
```

### Adaptive Chunking

| Content Type | Strategy | Parameters |
|-------------|----------|------------|
| YouTube | Timestamp groups | ~3 min segments, preserve sentence boundaries |
| Bookmarks | Semantic paragraphs | 512 tokens, 15% overlap |
| PDFs | Page-level | Full page, split if >1000 tokens |
| General | Recursive character | 400 tokens, 15% overlap |

### AI Tier Escalation

```
Request ──► OpenRouter Free ──► DeepSeek ($0.28/1M) ──► Claude (Max sub)
               │                      │                     │
               ▼                      ▼                     ▼
          Rate limit?            Rate limit?            Final tier
          Error?                 Error?                 (always works)
               │                      │
               └──────► Escalate ─────┘
```

## Obsidian Integration

### Note Format

```markdown
---
type: youtube
url: https://youtube.com/watch?v=xyz
title: "Video Title"
tags:
  - machine-learning
  - tutorial
captured_at: 2024-01-15T10:30:00Z
metadata:
  channel: "Channel Name"
  duration: 1234
  thumbnail: "https://..."
---

## Summary
AI-generated summary here...

## Transcript
Full transcript or content here...
```

### Sync Strategy

1. **Obsidian → PostgreSQL**: File watcher detects changes, re-index
2. **PostgreSQL → Obsidian**: Only for auto-generated fields (summary, auto_tags)
3. **Conflict Resolution**: YAML frontmatter is source of truth

## Infrastructure

### Docker Compose Services

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    ports: ["127.0.0.1:5432:5432"]  # Localhost only

  watchtower:
    image: containrrr/watchtower
    schedule: "0 4 * * 0"  # Weekly Sunday 4am
```

### Security

- Database bound to localhost only
- API keys in macOS Keychain (not env files)
- Parameterized queries (no SQL injection)
- Content validation on all ingest
