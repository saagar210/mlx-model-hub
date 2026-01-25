# Knowledge Infrastructure Readiness Plan

## Executive Assessment

**From a 30-year industry veteran's perspective:**

The Knowledge Engine is under active development - we leave it alone. Our job is to **build everything around it** so when it's ready, we can immediately start feeding knowledge. This means: build the tooling, curate the sources, prepare the infrastructure dependencies, and have a clear execution plan.

**Critical Path**: Prepare Dependencies → Build Knowledge Seeder CLI → Curate & Validate Sources → Wait for Knowledge Engine → Execute Seeding

---

## Current State Assessment

### What's Ready

| Component | Status | Notes |
|-----------|--------|-------|
| Knowledge Engine | IN PROGRESS | Do not touch - under construction |
| Source YAML Files | 100% | ~250 curated sources ready |
| Knowledge Strategy Doc | 100% | Methodologies documented |
| Implementation Plan (Seeder) | 100% | Architecture documented |
| **Knowledge Seeder Code** | **0%** | **Primary work item** |

### What We're Building (Independent of Knowledge Engine)

The Knowledge Seeder CLI is **completely decoupled** from the Knowledge Engine. It will:
1. Parse YAML source files
2. Fetch content from URLs, YouTube, files
3. Track state in local SQLite
4. Queue content for ingestion
5. Connect to Knowledge Engine API **only when ready**

This means we can build and test the Seeder without touching the Knowledge Engine.

---

## What Needs to Be Done

### Phase 1: Prepare Dependencies (30 minutes)

**Ollama Models** (for future Knowledge Engine use):
```bash
# Verify what's already downloaded
ollama list

# These will be needed when Knowledge Engine is ready:
# - nomic-embed-text (embeddings)
# - qllama/bge-reranker-v2-m3 (reranking)
# - llama3.2 (LLM)

# Download if missing (can do now or later)
ollama pull nomic-embed-text
ollama pull qllama/bge-reranker-v2-m3
ollama pull llama3.2
```

**Python Environment**:
```bash
python --version  # Need 3.11+
```

**No Docker needed yet** - Knowledge Engine will handle its own infrastructure when ready.

---

### Phase 2: Build Knowledge Seeder CLI (1-2 days)

**Objective**: Implement the batch ingestion tool per the existing implementation plan.

**Location**: `/Users/d/claude-code/projects-2026/knowledge-seeder/`

**Core Components**:
```
knowledge-seeder/
├── src/knowledge_seeder/
│   ├── __init__.py
│   ├── cli.py              # Typer CLI
│   ├── config.py           # Settings
│   ├── client.py           # Knowledge Engine API client
│   ├── source_manager.py   # YAML parsing
│   ├── state_manager.py    # SQLite state tracking
│   └── sync.py             # Main sync logic
├── sources/                # Already created (10 YAML files)
├── pyproject.toml
└── tests/
```

**Key Features**:
1. Parse YAML source files
2. Track ingestion state in SQLite
3. Idempotent operations (skip already-ingested)
4. Rate limiting (respect API limits)
5. Retry failed sources
6. Progress reporting

**CLI Commands**:
```bash
# Sync all sources from YAML files
knowledge-seeder sync sources/*.yaml

# Sync specific namespace
knowledge-seeder sync sources/frameworks.yaml --namespace frameworks

# Check status
knowledge-seeder status
knowledge-seeder status --namespace frameworks

# Retry failed
knowledge-seeder retry --failed-only

# Manual ingest
knowledge-seeder ingest https://example.com --namespace test
```

---

### Phase 3: Test Knowledge Seeder (Standalone) (2-4 hours)

**Objective**: Validate the Seeder works independently before connecting to Knowledge Engine.

**Standalone Testing** (no Knowledge Engine required):
```bash
# Test YAML parsing
knowledge-seeder validate sources/frameworks.yaml

# Test content extraction (fetches but doesn't ingest)
knowledge-seeder fetch https://langchain-ai.github.io/langgraph/concepts/ --dry-run

# Test YouTube extraction
knowledge-seeder fetch "https://www.youtube.com/watch?v=zjkBMFhNj_g" --dry-run

# Test state management
knowledge-seeder status
```

**What We're Validating** (without Knowledge Engine):
- YAML files parse correctly
- URLs are reachable and content extracts
- YouTube transcripts download
- SQLite state tracks properly
- Rate limiting works
- Retry logic functions

---

### Phase 4: Source Validation & Curation (2-4 hours)

**Objective**: Verify all 250 sources are valid and accessible.

**Run Source Validation**:
```bash
# Validate all sources without ingesting
knowledge-seeder validate sources/*.yaml --check-urls

# Output: report of valid/invalid/unreachable sources
```

**Fix Issues**:
- Update broken URLs
- Remove dead sources
- Find alternatives for unavailable content
- Mark YouTube videos without transcripts

**Expected Cleanup**:
| Issue Type | Est. Count | Action |
|------------|------------|--------|
| Broken URLs | ~5-10 | Find alternatives |
| No transcript | ~2-3 | Mark skip or find alt |
| Rate limited | ~1-2 | Add delays |
| Paywall | ~3-5 | Remove or find free version |

---

### Phase 5: Prepare Execution Plan (1 hour)

**Objective**: Have everything ready to execute when Knowledge Engine is ready.

**Execution Order** (documented and ready):
```bash
# P0 - Essential (first batch)
knowledge-seeder sync sources/frameworks.yaml
knowledge-seeder sync sources/infrastructure.yaml

# P1 - Important (second batch)
knowledge-seeder sync sources/tools.yaml
knowledge-seeder sync sources/ai-research.yaml

# P2 - Best Practices (third batch)
knowledge-seeder sync sources/best-practices.yaml

# P3 - Tutorials (fourth batch)
knowledge-seeder sync sources/tutorials-youtube.yaml

# Project-specific (final batch)
knowledge-seeder sync sources/project-*.yaml
```

**Expected Volume** (when executed):
| Namespace | Documents | Est. Chunks |
|-----------|-----------|-------------|
| frameworks | ~25 | ~500 |
| infrastructure | ~25 | ~400 |
| tools | ~30 | ~600 |
| ai-research | ~25 | ~400 |
| best-practices | ~25 | ~400 |
| tutorials | ~18 | ~300 |
| projects/* | ~100 | ~1500 |
| **Total** | **~250** | **~4100** |

---

## Software & Dependencies Summary

### Required (Must Have)

| Software | Version | Purpose | Status |
|----------|---------|---------|--------|
| Python | 3.11+ | Runtime | Check |
| Docker | 24+ | Infrastructure | Check |
| Ollama | Latest | Local LLM | Installed |
| nomic-embed-text | Latest | Embeddings | Verify |
| bge-reranker-v2-m3 | Latest | Reranking | **Download** |
| llama3.2 | Latest | LLM | **Download** |

### Python Packages

```bash
# Knowledge Engine (already in pyproject.toml)
pip install -e /Users/d/claude-code/personal/knowledge-engine

# Knowledge Seeder (to be created)
pip install typer rich httpx pyyaml aiosqlite

# Evaluation (for validation)
pip install ragas deepeval
```

### Optional Enhancements

| Software | Purpose | When to Add |
|----------|---------|-------------|
| MLX | Faster inference on Apple Silicon | After validation |
| Redis | Caching layer | When scaling |
| Neo4j | Graph relations | When needed |
| Voyage AI | Better embeddings | When quality insufficient |
| Cohere | Better reranking | When quality insufficient |

---

## Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Ollama slow inference | Medium | Medium | Consider MLX later |
| URL extraction failures | High | Low | Retry logic, fallbacks |
| YouTube transcript unavailable | Medium | Low | Skip, mark failed |
| Chunk quality issues | Medium | Medium | Tune chunk size |
| Search relevance poor | Low | High | Rerank tuning, evaluation |

### Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Disk space exhaustion | Low | High | Monitor, cleanup old |
| Rate limiting by sources | Medium | Low | Respectful delays |
| Source URLs change | High | Low | Periodic refresh |
| Model memory pressure | Medium | Medium | One model at a time |

---

## Decision Points

### Decision 1: Ollama vs MLX

**Current**: Ollama (simpler, works now)
**Alternative**: MLX (230 tok/s vs ~100 tok/s on Apple Silicon)

**Recommendation**: Start with Ollama. Switch to MLX only if inference speed becomes a bottleneck during RAG queries. The Knowledge Seeder is I/O bound (network), not inference bound.

### Decision 2: Premium Providers

**Current**: All local/free (Ollama)
**Alternative**: Voyage AI embeddings, Cohere reranking, Claude LLM

**Recommendation**: Start free. Upgrade only if evaluation metrics don't meet targets after tuning. The Knowledge Engine already supports seamless switching via environment variables.

### Decision 3: Graph Database

**Current**: Disabled (PostgreSQL + Qdrant sufficient)
**Alternative**: Neo4j for entity relationships

**Recommendation**: Skip for now. Graph is useful for "What entities are related to X?" queries, not essential for document retrieval. Add later if downstream projects need it.

---

## Timeline

```
Phase 1: Preparation (Today)
├── [30 min] Verify/download Ollama models (for future use)
└── [30 min] Review implementation plan for Knowledge Seeder

Phase 2: Build Knowledge Seeder CLI (Day 1-2)
├── [4 hours] Core architecture (client, state manager, source parser)
├── [4 hours] Content extractors (URL, YouTube, file)
├── [4 hours] CLI commands (sync, validate, fetch, status)
└── [4 hours] Tests and error handling

Phase 3: Validate Sources (Day 3)
├── [2 hours] Run URL validation across all YAML files
├── [2 hours] Fix broken/invalid sources
└── [2 hours] Test content extraction (dry-run mode)

Phase 4: Ready State (Day 4)
├── [1 hour] Document execution plan
├── [1 hour] Create pre-flight checklist
└── WAIT for Knowledge Engine to be ready

Phase 5: Execute (When Knowledge Engine Ready)
├── Connect Knowledge Seeder to Knowledge Engine API
├── Run batch ingestion (~250 sources)
└── Begin downstream project development
```

---

## Success Criteria

**Ready to seed knowledge when:**

1. [ ] Knowledge Seeder CLI built and tested (standalone)
2. [ ] All YAML source files validated (URLs accessible)
3. [ ] Content extraction working (dry-run successful)
4. [ ] State management functional (SQLite tracking)
5. [ ] Execution plan documented
6. [ ] Knowledge Engine signals "ready" (not our concern until then)

**NOT our concern right now:**
- Knowledge Engine health checks
- RAG query quality
- Search relevance
- RAGAS evaluation scores

Those come AFTER we connect and seed.

---

## Appendix: Quick Reference Commands

```bash
# Ollama (prepare models for future use)
ollama serve                            # Start server
ollama list                             # List models
ollama pull nomic-embed-text            # Embeddings
ollama pull qllama/bge-reranker-v2-m3   # Reranking
ollama pull llama3.2                    # LLM

# Knowledge Seeder CLI (what we're building)
knowledge-seeder validate sources/*.yaml        # Validate YAML files
knowledge-seeder validate sources/*.yaml --check-urls  # Check URL accessibility
knowledge-seeder fetch <url> --dry-run          # Test extraction without ingesting
knowledge-seeder status                         # Show state database
knowledge-seeder sync sources/*.yaml            # Full sync (when connected)
knowledge-seeder retry --failed-only            # Retry failed sources
```

---

## Appendix: Project Locations

```
/Users/d/claude-code/
├── personal/
│   └── knowledge-engine/           # DO NOT TOUCH - under development
│
└── projects-2026/
    ├── READINESS_PLAN.md           # This document
    │
    └── knowledge-seeder/           # Our work
        ├── IMPLEMENTATION_PLAN.md  # Architecture & code plan
        ├── KNOWLEDGE_STRATEGY.md   # Ingestion methodology
        └── sources/                # 10 YAML source files (~250 sources)
            ├── frameworks.yaml
            ├── infrastructure.yaml
            ├── ai-research.yaml
            ├── tools.yaml
            ├── best-practices.yaml
            ├── tutorials-youtube.yaml
            ├── project-voice-ai.yaml
            ├── project-browser-automation.yaml
            ├── project-rag-evaluation.yaml
            └── project-mcp-servers.yaml
```

---

## Sources

- [LlamaIndex Production RAG Guide](https://developers.llamaindex.ai/python/framework/optimizing/production_rag/)
- [Qdrant RAG Use Cases](https://qdrant.tech/rag/)
- [MLX vs Ollama Performance Study](https://arxiv.org/abs/2511.05502)
- [Local LLM Hosting 2025 Guide](https://medium.com/@rosgluk/local-llm-hosting-complete-2025-guide-ollama-vllm-localai-jan-lm-studio-more-f98136ce7e4a)
- [RAGAS Evaluation Framework](https://docs.ragas.io/)
- [DeepEval RAG Guide](https://deepeval.com/guides/guides-rag-evaluation)
- [MCP Protocol Documentation](https://modelcontextprotocol.io/)
