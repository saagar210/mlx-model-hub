# Knowledge Seeder → Knowledge Engine Integration Handoff

**From:** Knowledge Seeder Development Session
**To:** Knowledge Engine
**Date:** January 2026

---

## Executive Summary

I am **Knowledge Seeder**, a CLI tool built specifically to feed you batch-curated knowledge sources. I've studied your codebase and understand your API contracts, data models, and capabilities. This document details exactly how I will integrate with you.

---

## My Location

```
/Users/d/claude-code/projects-2026/knowledge-seeder/
```

Your location (which I've studied):
```
/Users/d/claude-code/personal/knowledge-engine/
```

---

## Integration Decision: Which Endpoint?

You have two ingestion options. I recommend **Option A** for batch ingestion:

### Option A: `/v1/ingest/document` (Recommended)
- **I pre-extract content** using my specialized extractors
- **I send you clean text** with structured metadata
- **Benefits:**
  - My extractors handle edge cases you might not (GitHub READMEs, arXiv abstracts, YouTube with fallbacks)
  - I can quality-score content before sending
  - Batch control and retry logic on my side
  - You just chunk, embed, and store

### Option B: `/v1/ingest/source`
- I send you the URL, you extract
- You already have URL, YouTube, File ingestors
- **Drawback:** No GitHub-specific or arXiv-specific extraction on your side

**My Recommendation:** I'll use `/v1/ingest/document` with pre-extracted content.

---

## Exact Payload I Will Send

Based on your `DocumentCreate` model in `models/documents.py`:

```python
# POST /v1/ingest/document
{
    "content": "# FastAPI Documentation\n\nFastAPI is a modern, fast...",  # Required, min 1 char
    "title": "FastAPI - Official Documentation",  # Optional
    "document_type": "markdown",  # One of: text, markdown, html, pdf, code, youtube, bookmark, note, conversation
    "namespace": "frameworks",  # I'll use my YAML namespaces
    "metadata": {
        "source": "https://fastapi.tiangolo.com/",  # Original URL
        "author": null,  # If available from extraction
        "created_at": null,  # If available
        "tags": ["python", "web-framework", "async", "api"],  # My source tags
        "language": "en",  # ISO 639-1
        "custom": {
            "seeder_source_id": "frameworks:fastapi-docs",  # My tracking ID
            "seeder_priority": "P1",
            "seeder_source_type": "url",
            "seeder_quality_score": 87.5,
            "seeder_extracted_at": "2026-01-13T12:00:00Z"
        }
    }
}
```

### Document Type Mapping

| My Source Type | Your Document Type |
|----------------|-------------------|
| `url` | `text` or `markdown` (based on content) |
| `youtube` | `youtube` |
| `github` | `markdown` (READMEs are markdown) |
| `arxiv` | `text` (abstracts + metadata) |
| `file` | `text`, `markdown`, or `code` |

---

## Expected Response

Based on your `IngestResponse` model:

```python
{
    "document_id": "550e8400-e29b-41d4-a716-446655440000",  # UUID
    "title": "FastAPI - Official Documentation",
    "source": "https://fastapi.tiangolo.com/",
    "source_type": "document",  # Since I'm using /ingest/document
    "chunk_count": 12,
    "content_preview": "# FastAPI Documentation\n\nFastAPI is a modern..."
}
```

**What I'll store in my state database:**
- `document_id` → `source_state.document_id`
- `chunk_count` → `source_state.chunk_count`
- Timestamp → `source_state.ingested_at`

---

## Namespaces I Will Use

These match your Qdrant collection naming: `{prefix}_{namespace}_chunks`

| My Namespace | Expected Qdrant Collection |
|--------------|---------------------------|
| `frameworks` | `ke_frameworks_chunks` |
| `infrastructure` | `ke_infrastructure_chunks` |
| `ai-research` | `ke_ai-research_chunks` |
| `tools` | `ke_tools_chunks` |
| `best-practices` | `ke_best-practices_chunks` |
| `tutorials` | `ke_tutorials_chunks` |
| `projects/voice-ai` | `ke_projects/voice-ai_chunks` |
| `projects/browser-automation` | `ke_projects/browser-automation_chunks` |
| `projects/mcp-servers` | `ke_projects/mcp-servers_chunks` |
| `projects/rag-evaluation` | `ke_projects/rag-evaluation_chunks` |
| `agent-frameworks` | `ke_agent-frameworks_chunks` |
| `apple-mlx` | `ke_apple-mlx_chunks` |

**Question:** Do namespace names with `/` work correctly in your Qdrant collection naming? If not, I can use `projects-voice-ai` format instead.

---

## Rate Limiting Alignment

Your settings (from `config.py`):
- No explicit request rate limit in FREE tier
- `SEARCH_DEFAULT_LIMIT=10`

My defaults (from `config.py`):
```python
rate_limit_requests: int = 30  # per minute
rate_limit_delay: float = 2.0  # seconds between requests
```

**For batch ingestion, I'll use:**
- 2-second delay between documents
- Exponential backoff on 429/5xx errors
- Max 3 retries per document

---

## Content Quality Pre-Filter

I score content 0-100 before sending. My thresholds:

| Score | Action |
|-------|--------|
| 80+ | Send immediately |
| 40-79 | Send with `seeder_quality_score` in metadata |
| <40 | Skip (log as failed, don't waste your embedding costs) |

This protects you from:
- Empty pages
- Navigation-only content
- Heavily duplicated text
- Bot-detection pages

---

## Error Handling Contract

**Errors I expect from you:**

| HTTP Code | My Action |
|-----------|-----------|
| 200 | Mark completed, store document_id |
| 400 | Mark failed, log validation error, no retry |
| 401/403 | Mark failed, stop batch (auth issue) |
| 404 | Mark failed (shouldn't happen for ingest) |
| 429 | Exponential backoff, retry up to 3x |
| 500/502/503/504 | Exponential backoff, retry up to 3x |

---

## Sync Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE SEEDER                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Parse sources/*.yaml                                     │
│  2. For each source:                                         │
│     a. Check state DB (skip if already completed)            │
│     b. Extract content (URL/YouTube/GitHub/arXiv/File)       │
│     c. Score quality (skip if <40)                           │
│     d. Build DocumentCreate payload                          │
│     e. POST /v1/ingest/document ──────────────────────────┐ │
│     f. Store document_id in state DB                       │ │
│     g. Wait 2 seconds (rate limit)                         │ │
│                                                            │ │
└────────────────────────────────────────────────────────────┼─┘
                                                             │
                                                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE ENGINE                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Validate DocumentCreate                                  │
│  2. Create document record (PostgreSQL)                      │
│  3. Chunk content (semantic chunking)                        │
│  4. Generate embeddings (Ollama/Voyage)                      │
│  5. Store vectors (Qdrant)                                   │
│  6. Store chunks (PostgreSQL for BM25)                       │
│  7. Extract entities (Neo4j if enabled)                      │
│  8. Return IngestResponse                                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Current Inventory

### Sources Ready to Ingest

| Namespace | Count | Types |
|-----------|-------|-------|
| frameworks | 28 | url, github |
| infrastructure | 25 | url, github |
| ai-research | 24 | url, arxiv |
| tools | 29 | url, github |
| best-practices | 26 | url |
| tutorials | 18 | youtube |
| projects/voice-ai | 21 | url, github, arxiv |
| projects/browser-automation | 24 | url, github |
| projects/mcp-servers | 26 | url, github |
| projects/rag-evaluation | 28 | url, github, arxiv |
| agent-frameworks | 24 | url, github, arxiv |
| apple-mlx | 22 | url, github, arxiv |
| **TOTAL** | **295** | |

### By Source Type
- **URL:** 178 sources
- **GitHub:** 64 sources
- **arXiv:** 35 sources
- **YouTube:** 18 sources

---

## My File Structure

```
knowledge-seeder/
├── src/knowledge_seeder/
│   ├── __init__.py              # Package exports
│   ├── cli.py                   # 9 CLI commands
│   ├── config.py                # SEEDER_* env vars
│   ├── models.py                # Source, SourceState, etc.
│   ├── state.py                 # SQLite state tracking
│   ├── source_parser.py         # YAML parsing
│   ├── extractor_service.py     # Extraction coordinator
│   ├── retry.py                 # Exponential backoff
│   ├── quality.py               # Content scoring
│   ├── logging_config.py        # Structured logging
│   └── extractors/
│       ├── base.py              # BaseExtractor interface
│       ├── url.py               # Trafilatura extraction
│       ├── youtube.py           # Transcript API
│       ├── github.py            # README + file fetching
│       ├── arxiv.py             # arXiv API
│       └── file.py              # Local files
├── sources/                     # 12 YAML source files
│   ├── frameworks.yaml
│   ├── infrastructure.yaml
│   ├── ai-research.yaml
│   ├── tools.yaml
│   ├── best-practices.yaml
│   ├── tutorials-youtube.yaml
│   ├── project-voice-ai.yaml
│   ├── project-browser-automation.yaml
│   ├── project-mcp-servers.yaml
│   ├── project-rag-evaluation.yaml
│   ├── agent-frameworks.yaml
│   └── apple-mlx.yaml
├── tests/                       # 38 passing tests
├── DATA_ACQUISITION_ROADMAP.md  # 500-source expansion plan
└── pyproject.toml               # Dependencies
```

---

## Configuration I'll Need From You

Before I start batch ingestion, please confirm:

1. **API Base URL:** `http://localhost:8000` correct?
2. **Authentication:** `REQUIRE_API_KEY=false` for local dev?
3. **Namespace format:** Can I use `projects/voice-ai` or should I use `projects-voice-ai`?
4. **Content size limit:** Is there a max content length per document?
5. **Embedding model:** Using `nomic-embed-text` (768 dims)?

---

## CLI Commands for Integration

```bash
# Validate sources before ingestion
knowledge-seeder validate sources/*.yaml

# Initialize state database
knowledge-seeder init

# Full sync (extract + ingest)
knowledge-seeder sync sources/*.yaml

# Extract only (no ingestion)
knowledge-seeder sync sources/*.yaml --extract-only

# Check status
knowledge-seeder status

# View failures
knowledge-seeder failed
```

---

## What I Need You To Prepare

1. **Ensure services are running:**
   ```bash
   docker compose up -d  # PostgreSQL + Qdrant
   ```

2. **Start your API:**
   ```bash
   cd /Users/d/claude-code/personal/knowledge-engine
   uv run uvicorn knowledge_engine.api.main:create_app --factory --reload
   ```

3. **Confirm health:**
   ```bash
   curl http://localhost:8000/health
   ```

4. **Be ready for ~295 documents** across 12 namespaces

---

## Post-Integration Verification

After I complete batch ingestion, you should be able to:

```bash
# Search across all namespaces
curl -X POST http://localhost:8000/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "FastAPI async endpoints", "namespace": "frameworks"}'

# RAG query
curl -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I create an async endpoint in FastAPI?", "namespace": "frameworks"}'
```

---

## Questions for You

1. Should I batch multiple documents per request, or one at a time?
2. Do you want me to populate any specific `metadata.custom` fields?
3. Should I use your `/v1/ingest/source` for YouTube (since you have a YouTube ingestor)?
4. Do you have a preference for chunking strategy that I should consider in content formatting?

---

**I am ready when you are. All 295 sources validated, all 38 tests passing.**

---

*End of handoff document.*
