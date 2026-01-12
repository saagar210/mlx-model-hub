# User Decisions Log

All decisions captured during the planning phase.

## Storage & Database

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary Database | PostgreSQL + pgvector + pgvectorscale | Best scalability, security, 11x throughput with DiskANN |
| Source of Truth | Obsidian YAML frontmatter | PostgreSQL is derived/rebuildable cache |
| Embedding Dimensions | 768 | Nomic Embed Text v1.5 native dimension |
| Vector Index | DiskANN (via pgvectorscale) | Better than HNSW for large datasets |

## Content & Ingestion

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Browser Support | Chrome only | User's primary browser |
| Content Priority | YouTube → Bookmarks → Files | YouTube is primary use case |
| Podcasts | Skip | Not a priority for user |
| File Handling | Reference only (store path) | Don't copy/move files |
| Vault Location | ~/Obsidian/ | Use existing vault |
| YouTube Seed Data | Google Takeout, last 6 months | Manageable initial dataset |

## Search & AI

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Search Method | Hybrid (BM25 + Vector) | Best of both worlds |
| Fusion Method | RRF (k=60) | Rank-based, avoids score normalization |
| Reranking | mxbai-rerank-large-v2 | 20-35% accuracy improvement |
| Embedding Model | Nomic Embed Text v1.5 via Ollama | Local, no API costs |
| AI Tiers | OpenRouter Free → DeepSeek → Claude | Cost optimization |

## Spaced Repetition

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Algorithm | FSRS (not SM-2) | 89.6% vs 47% accuracy, 20-30% fewer reviews |
| Implementation | py-fsrs 6.3.0 | Stable, well-tested |
| Target Review Time | <15 min/day | Sustainable habit |

## Chunking Strategy

| Decision | Choice | Rationale |
|----------|--------|-----------|
| YouTube | Timestamp groups (~3 min) | Natural breakpoints |
| Bookmarks | Semantic paragraphs (512 tokens) | Preserve meaning |
| PDFs | Page-level | Natural document structure |
| General | 400 tokens, 15% overlap | Research-backed defaults |

## Automation & Maintenance

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Git Sync | Hourly auto-commit | Frequent enough, not excessive |
| Git Remote | Local only | User preference |
| Dependency Updates | Dependabot + auto-merge | Zero-touch maintenance |
| Docker Updates | Watchtower (weekly) | Automatic, safe schedule |
| Target Maintenance | ~0 min/month | Fully automated |

## Interface

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Initial Interface | CLI only (Phase 1-3) | Faster development, test core functionality |
| Web App | Next.js 15 + shadcn/ui | Modern, type-safe |
| Daily Review | Web dashboard | Primary engagement interface |

## Special Features (Approved)

| Feature | Included | Rationale |
|---------|----------|-----------|
| Whisper Fallback | ✅ Yes | Captures 5-10% of YouTube without captions |
| Confidence Scoring | ✅ Yes | Prevents hallucinated answers |
| Content Validation | ✅ Yes | Basic quality gates |
| Query Expansion | ❌ No | Hybrid search handles vocabulary mismatch |
| Git LFS | ❌ No | Reference-only design, no binaries in git |
| Completeness Verification | ❌ No | Confidence scoring covers main failure mode |

## Risk Mitigations (Approved)

| Risk | Mitigation |
|------|------------|
| pgvector upgrade crashes | Pin to 0.7.x, test in staging |
| Nomic v2 transition | Same 768 dims, seamless upgrade |
| Whisper hallucinations | Validate transcript length vs duration |
| FSRS algorithm changes | py-fsrs handles state migration |
| Data loss | YAML is source of truth, PostgreSQL rebuildable |
