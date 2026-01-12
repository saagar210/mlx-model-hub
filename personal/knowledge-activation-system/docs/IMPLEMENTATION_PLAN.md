# Implementation Plan

## Phase 1: Foundation (CLI-only)

### 1.1 Docker Setup
- [ ] Create `docker-compose.yml` with PostgreSQL 16 + pgvector + pgvectorscale
- [ ] Create `docker/postgres/init.sql` with schema
- [ ] Configure localhost-only binding (127.0.0.1:5432)
- [ ] Add Watchtower for auto-updates

### 1.2 Database Schema
- [ ] Create `content` table with FTS vector
- [ ] Create `chunks` table with embedding vector(768)
- [ ] Create `review_queue` table with FSRS state
- [ ] Add all indexes (GIN for tags/FTS, DiskANN for embeddings)

### 1.3 Python Package Structure
- [ ] Initialize `pyproject.toml` with dependencies
- [ ] Create `src/knowledge/__init__.py`
- [ ] Create `src/knowledge/config.py` (env vars, paths)
- [ ] Create `src/knowledge/db.py` (PostgreSQL connection, queries)

### 1.4 Embeddings
- [ ] Create `src/knowledge/embeddings.py`
- [ ] Integrate Nomic Embed Text v1.5 via Ollama
- [ ] Add batch embedding support
- [ ] Track embedding model version in chunks table

### 1.5 Hybrid Search
- [ ] Create `src/knowledge/search.py`
- [ ] Implement BM25 search via PostgreSQL FTS
- [ ] Implement vector search via pgvector
- [ ] Implement RRF fusion (k=60)
- [ ] Add reranking via mxbai-rerank-large-v2

### 1.6 CLI
- [ ] Create `cli.py` entry point
- [ ] Add `search <query>` command
- [ ] Add `stats` command (content counts, index health)

### 1.7 Tests
- [ ] Set up pytest
- [ ] Test database connection
- [ ] Test embeddings
- [ ] Test hybrid search
- [ ] Test RRF fusion

---

## Phase 2: Content Ingestion

### 2.1 Content Validation
- [ ] Create `src/knowledge/validation.py`
- [ ] Check non-empty content
- [ ] Check minimum length (>100 chars)
- [ ] Check for error pages (404, access denied)

### 2.2 Adaptive Chunking
- [ ] Create `src/knowledge/chunking.py`
- [ ] YouTube: timestamp-based (~3 min segments)
- [ ] Bookmarks: semantic paragraph-based (512 tokens, 15% overlap)
- [ ] PDFs: page-level
- [ ] General: RecursiveCharacterTextSplitter (400 tokens, 15% overlap)

### 2.3 YouTube Ingestion
- [ ] Create `src/knowledge/ingest/youtube.py`
- [ ] Fetch captions via youtube-transcript-api
- [ ] Implement Whisper fallback (download audio via yt-dlp, transcribe)
- [ ] Validate transcript length vs video duration
- [ ] Parse Google Takeout watch history (last 6 months)
- [ ] Create Obsidian note with YAML frontmatter
- [ ] Add CLI command: `ingest youtube <video_id>`
- [ ] Add CLI command: `ingest youtube-takeout <path>`

### 2.4 Bookmark Ingestion
- [ ] Create `src/knowledge/ingest/bookmark.py`
- [ ] Fetch page content via httpx
- [ ] Extract main content (readability/trafilatura)
- [ ] Create Obsidian note
- [ ] Add CLI command: `ingest bookmark <url>`

### 2.5 Chrome Extension
- [ ] Create `extension/` directory
- [ ] Manifest V3 setup
- [ ] "Save to Knowledge" button
- [ ] Send URL to local FastAPI endpoint
- [ ] Configure CORS for localhost

### 2.6 File Watcher
- [ ] Create `src/knowledge/ingest/files.py`
- [ ] Watch configured directories
- [ ] Support: PDF, TXT, MD
- [ ] Reference only (store path, don't copy)
- [ ] Add CLI command: `ingest file <path>`
- [ ] Add CLI command: `watch <directory>`

---

## Phase 3: Intelligence Layer

### 3.1 AI Provider Setup
- [ ] Create `src/knowledge/ai.py`
- [ ] Implement tiered provider: OpenRouter Free → DeepSeek → Claude
- [ ] Add retry logic with tier escalation
- [ ] Track costs per tier

### 3.2 Q&A with Citations
- [ ] Add `ask <query>` CLI command
- [ ] Retrieve relevant chunks
- [ ] Generate answer with source_ref citations
- [ ] Format citations as clickable references

### 3.3 Confidence Scoring
- [ ] Calculate confidence from reranker scores
- [ ] Top score (60%) + avg top-3 (40%)
- [ ] Return "low confidence" warning if <0.3
- [ ] Show confidence level in responses

### 3.4 Auto-Tagging
- [ ] Generate tags via AI on ingest
- [ ] Store in `auto_tags` column
- [ ] Keep separate from manual `tags`

---

## Phase 4: Web Application

### 4.1 FastAPI Backend
- [ ] Create `src/knowledge/api/` directory
- [ ] Set up FastAPI app with CORS
- [ ] `/search` endpoint
- [ ] `/ask` endpoint
- [ ] `/content` CRUD endpoints
- [ ] `/review` endpoints
- [ ] Generate OpenAPI schema

### 4.2 Next.js Frontend
- [ ] Initialize Next.js 15 in `web/` directory
- [ ] Set up shadcn/ui
- [ ] Generate TypeScript types from OpenAPI
- [ ] Search page with results
- [ ] Content detail page
- [ ] Daily Review dashboard

### 4.3 Integration
- [ ] Type-safe API client
- [ ] Error handling
- [ ] Loading states

---

## Phase 5: Active Engagement

### 5.1 FSRS Engine
- [ ] Create `src/knowledge/review.py`
- [ ] Integrate py-fsrs 6.3.0
- [ ] Store FSRS state in review_queue.fsrs_state
- [ ] Calculate next review dates

### 5.2 Daily Review System
- [ ] Get due items for today
- [ ] Present content for review
- [ ] Record responses (Again, Hard, Good, Easy)
- [ ] Update FSRS state
- [ ] Add CLI command: `review`

### 5.3 Review Queue Management
- [ ] Auto-add new content to queue
- [ ] Archive/suspend items
- [ ] Priority adjustments

---

## Phase 6: Polish & Automation

### 6.1 Dependency Automation
- [ ] Configure Dependabot for Python
- [ ] Configure Dependabot for Node.js
- [ ] Set up auto-merge for patch/minor updates

### 6.2 Docker Automation
- [ ] Configure Watchtower (weekly, Sunday 4am)
- [ ] Auto-cleanup old images

### 6.3 Backup System
- [ ] Daily pg_dump cron job
- [ ] Weekly restore test script
- [ ] Alert on backup failure

### 6.4 Git Automation
- [ ] Hourly auto-commit script for Obsidian vault
- [ ] Local only (no remote push)

### 6.5 Monitoring
- [ ] Health check endpoint
- [ ] Embedding model version tracking
- [ ] Search latency logging

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Search latency | <200ms p95 |
| Embedding throughput | >100 docs/min |
| FSRS retention | >90% |
| Daily Review time | <15 min |
| Maintenance time | ~0 min/month |
