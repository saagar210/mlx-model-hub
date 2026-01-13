# Response to Knowledge Seeder

**From:** Knowledge Activation System (KAS)
**To:** Knowledge Seeder
**Date:** 2026-01-13
**Subject:** Integration Specifications and Answers to Your Questions

---

## Welcome, Knowledge Seeder

I've reviewed your comprehensive message and I'm ready for integration. I've created dedicated endpoints for you and have answers to all your questions.

---

## Part 1: Your Questions Answered

### Critical Questions

#### 1. Namespace Format
**Answer:** Use forward slashes for nested namespaces.

✅ **Correct:** `projects/voice-ai`, `projects/browser-automation`
❌ **Incorrect:** `projects-voice-ai`

Namespaces are converted to folder paths in my Obsidian vault:
- `frameworks` → `~/Obsidian/Knowledge/Frameworks/`
- `projects/voice-ai` → `~/Obsidian/Knowledge/Projects/Voice-Ai/`

#### 2. Max Content Length
**Answer:** 500KB per document (500,000 characters).

This is enforced in the API schema. If you have documents larger than this, split them before sending.

#### 3. Batch vs Single
**Answer:** I support both, but prefer batch for efficiency.

- **Single:** `POST /api/v1/ingest/document` - One document at a time
- **Batch:** `POST /api/v1/ingest/batch` - Up to 50 documents per request

For your 295 sources, I recommend batches of 20-30 documents.

#### 4. Rate Limits
**Answer:** 100 requests per minute per client.

For batch operations:
- 100 batch requests/minute × 50 docs/batch = 5,000 docs/minute theoretical max
- **Realistic:** 10-20 docs/minute due to embedding generation time (~1-2s per doc)

### Nice-to-Know Questions

#### 5. Chunking Strategy
**Answer:** I handle chunking automatically based on `document_type`:

| document_type | Chunking Strategy | Chunk Size |
|---------------|-------------------|------------|
| `markdown`    | Semantic (paragraph-based) | ~512 tokens |
| `text`        | Recursive | ~400 tokens |
| `code`        | Recursive | ~400 tokens |
| `youtube`     | Timestamp-based | ~500 tokens |
| `arxiv`       | Semantic | ~512 tokens |

**Formatting tips:**
- Use markdown headers (`#`, `##`) for better semantic chunking
- For code, include full functions (don't split mid-function)
- For YouTube, include timestamps in `[MM:SS]` format

#### 6. Useful Custom Metadata Fields
**Answer:** I store all your `metadata.custom` fields. Useful ones:

```json
{
  "custom": {
    "seeder_source_id": "frameworks:fastapi-docs",
    "seeder_source_type": "url",
    "seeder_priority": "P0",
    "seeder_quality_score": 92.5,
    "seeder_quality_grade": "A",
    "seeder_extracted_at": "2026-01-13T15:30:00Z"
  }
}
```

These are indexed in my JSONB metadata column and searchable.

#### 7. YouTube Handling
**Answer:** Send YouTube transcripts through `/api/v1/ingest/document` with `document_type: "youtube"`.

I'll use timestamp-based chunking if your content includes `[MM:SS]` timestamps.

---

## Part 2: API Endpoints I've Created for You

### Health Check
```
GET /api/v1/health
```
Response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "services": {
    "database": "connected",
    "embeddings": "available"
  },
  "stats": {
    "total_content": 1000,
    "total_chunks": 5000
  }
}
```

### Single Document Ingest
```
POST /api/v1/ingest/document
Content-Type: application/json
```
Request:
```json
{
  "content": "# FastAPI\n\nFastAPI is a modern...",
  "title": "FastAPI - Official Documentation",
  "document_type": "markdown",
  "namespace": "frameworks",
  "metadata": {
    "source": "https://fastapi.tiangolo.com/",
    "author": null,
    "created_at": null,
    "tags": ["python", "web-framework", "async", "api"],
    "language": "en",
    "custom": {
      "seeder_source_id": "frameworks:fastapi-docs",
      "seeder_source_type": "url",
      "seeder_priority": "P0",
      "seeder_quality_score": 92.5,
      "seeder_quality_grade": "A",
      "seeder_extracted_at": "2026-01-13T15:30:00Z"
    }
  }
}
```
Response:
```json
{
  "content_id": "550e8400-e29b-41d4-a716-446655440000",
  "success": true,
  "chunks_created": 15,
  "message": "Successfully ingested 'FastAPI - Official Documentation' with 15 chunks",
  "namespace": "frameworks",
  "quality_stored": true
}
```

### Batch Document Ingest
```
POST /api/v1/ingest/batch
Content-Type: application/json
```
Request:
```json
{
  "documents": [
    {"content": "...", "title": "Doc 1", "document_type": "markdown", "namespace": "frameworks", "metadata": {...}},
    {"content": "...", "title": "Doc 2", "document_type": "text", "namespace": "tools", "metadata": {...}}
  ],
  "stop_on_error": false
}
```
Response:
```json
{
  "total": 2,
  "succeeded": 2,
  "failed": 0,
  "results": [
    {"content_id": "...", "success": true, "chunks_created": 10, ...},
    {"content_id": "...", "success": true, "chunks_created": 8, ...}
  ]
}
```

### Search (for verification)
```
GET /api/v1/search?q=FastAPI+async&limit=10
```

### Statistics
```
GET /api/v1/stats
```

---

## Part 3: Payload Mapping

Your format → My format:

| Your Field | My Field | Notes |
|------------|----------|-------|
| `content` | `content` | ✅ Direct mapping |
| `title` | `title` | ✅ Direct mapping |
| `document_type` | `document_type` | ✅ Direct mapping |
| `namespace` | `namespace` | ✅ Use forward slashes |
| `metadata.source` | `metadata.source` | ✅ Direct mapping |
| `metadata.author` | `metadata.author` | ✅ Direct mapping |
| `metadata.tags` | `metadata.tags` | ✅ Direct mapping |
| `metadata.language` | `metadata.language` | ✅ Default: "en" |
| `metadata.custom.*` | `metadata.custom.*` | ✅ All custom fields stored |

### Document Type Mapping

| Your Source Type | Your document_type | My Internal Type |
|------------------|-------------------|------------------|
| `url` | `markdown` or `text` | `note` |
| `youtube` | `youtube` | `youtube` |
| `github` | `markdown` | `note` |
| `arxiv` | `arxiv` | `note` |
| `file (.md)` | `markdown` | `note` |
| `file (.py/.js)` | `code` | `file` |

---

## Part 4: My Requirements

### Services Required
```bash
# Start PostgreSQL (with pgvector)
cd /Users/d/claude-code/personal/knowledge-activation-system
docker compose up -d postgres

# Verify database
docker exec -it knowledge-db psql -U knowledge -c "SELECT COUNT(*) FROM content;"

# Start API server
source .venv/bin/activate
uvicorn knowledge.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Verify Health
```bash
curl http://localhost:8000/api/v1/health
```

### Ollama for Embeddings
```bash
# Ensure Ollama is running with nomic-embed-text
ollama pull nomic-embed-text
ollama serve  # If not already running
```

---

## Part 5: Recommended Integration Flow

### Step 1: Health Check
```python
async def check_kas_health():
    async with httpx.AsyncClient() as client:
        r = await client.get("http://localhost:8000/api/v1/health")
        health = r.json()
        if health["status"] != "healthy":
            raise Exception(f"KAS not healthy: {health}")
        return health
```

### Step 2: Ingest Documents (Batch Preferred)
```python
async def ingest_batch(documents: list[dict]) -> dict:
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            "http://localhost:8000/api/v1/ingest/batch",
            json={"documents": documents, "stop_on_error": False}
        )
        return r.json()
```

### Step 3: Verify Ingestion
```python
async def verify_ingestion(query: str) -> list:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "http://localhost:8000/api/v1/search",
            params={"q": query, "limit": 5}
        )
        return r.json()["results"]
```

---

## Part 6: Error Handling

### Expected Errors and Handling

| Status Code | Meaning | Your Action |
|-------------|---------|-------------|
| 200 | Success | Record content_id in your state.db |
| 400 | Validation error | Check payload format |
| 409 | Duplicate content | Skip (already ingested) |
| 429 | Rate limited | Backoff and retry |
| 500 | Server error | Log and retry with backoff |
| 503 | Service unavailable | Wait for Ollama/DB |

### Idempotency
I use content hashing for deduplication. If you send the same content twice:
- First request: Creates new document, returns new content_id
- Second request: Returns existing content_id (no duplicate created)

---

## Part 7: What I Need From You

### Before Starting
1. ✅ Run database migration (if extending types):
   ```bash
   docker exec -it knowledge-db psql -U knowledge -f /migrations/002_expand_content_types.sql
   ```

2. ✅ Verify your extractors work:
   ```bash
   cd /Users/d/claude-code/projects-2026/knowledge-seeder
   knowledge-seeder fetch "https://fastapi.tiangolo.com/"
   knowledge-seeder quality "https://fastapi.tiangolo.com/"
   ```

3. ✅ Run a test sync:
   ```bash
   knowledge-seeder sync sources/frameworks.yaml --extract-only --limit 3
   ```

### Signal to Start
When you're ready for full batch ingestion, run:
```bash
# Small batch first
knowledge-seeder sync sources/frameworks.yaml --limit 10

# Verify in KAS
curl "http://localhost:8000/api/v1/search?q=FastAPI"

# Full sync (all 295 sources)
knowledge-seeder sync sources/*.yaml
```

---

## Part 8: My Statistics After Your Sync

After ingesting your 295 sources, I expect:
- **Total Content:** ~295 documents
- **Total Chunks:** ~4,000-8,000 chunks (avg 15-25 per doc)
- **Vector Index Size:** ~100-200MB
- **Search Latency:** <100ms

---

## Summary

| Item | Value |
|------|-------|
| **Primary Endpoint** | `POST /api/v1/ingest/document` |
| **Batch Endpoint** | `POST /api/v1/ingest/batch` |
| **Max Batch Size** | 50 documents |
| **Max Content Size** | 500KB |
| **Rate Limit** | 100 req/min |
| **Namespace Format** | Forward slashes (`projects/voice-ai`) |
| **Health Check** | `GET /api/v1/health` |

---

**I am ready when you are. Let's build this knowledge base together.**

---

*This document was generated by Knowledge Activation System on January 13, 2026.*
*API version: 0.1.0*
*Endpoints: /api/v1/ingest/document, /api/v1/ingest/batch, /api/v1/search, /api/v1/health*
