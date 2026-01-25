# CODEX_BRIEF.md
## Senior Architect Handover Document

**Project:** Universal Context Engine (AI-Native Development Environment)
**Commit:** `15703c60` feat(ai-native-dev): implement Universal Context Engine MCP server
**Date:** 2026-01-25
**Author:** Junior Developer (Claude Opus 4.5)

---

## A. State Transition

**From:** Empty project directory with only a PROJECT.md vision document describing the planned AI-native development environment.

**To:** Complete 6-phase MCP server implementation providing persistent memory across Claude Code sessions with 20 tools, ChromaDB storage, session management, service adapters, intent routing, quality tracking, and a FastAPI dashboard.

---

## B. Change Manifest (Evidence Anchors)

### Core Infrastructure

| File | Logic Change |
|------|-------------|
| `pyproject.toml` | Project dependencies: fastmcp>=2.0.0, chromadb>=0.4.22, pydantic>=2.0, httpx>=0.25.0, redis>=5.0.0 with dev dependencies pytest/pytest-asyncio |
| `src/universal_context_engine/__init__.py` | Package exports: mcp server instance, context_store, models |
| `src/universal_context_engine/config.py` | Pydantic Settings for all configuration: UCE_DATA_DIR, OLLAMA_BASE_URL, Redis URL, KAS/LocalCrew URLs, embedding/generation models |
| `src/universal_context_engine/models.py` | Pydantic models: ContextType enum (SESSION, DECISION, PATTERN, CONTEXT, BLOCKER, ERROR), ContextItem, SearchResult, SessionCapture, SessionSummary, ServiceHealth |

### Phase 1: Core Context

| File | Logic Change |
|------|-------------|
| `src/universal_context_engine/context_store.py` | ChromaDB wrapper with lazy initialization, semantic search via Ollama embeddings, metadata filtering, CRUD operations (save, search, get_recent, delete, get_stats) |
| `src/universal_context_engine/embedding.py` | OllamaEmbeddingClient for nomic-embed-text embeddings, OllamaGenerateClient for qwen2.5:14b text generation, both with async httpx clients and health checks |
| `src/universal_context_engine/server.py` | FastMCP server with 20 tool registrations across all phases, entry point via `python -m universal_context_engine.server` |

### Phase 2: Session Management

| File | Logic Change |
|------|-------------|
| `src/universal_context_engine/session.py` | SessionManager class with Redis integration for hot session state, session lifecycle (start/end), buffer management, decision/blocker capture |
| `src/universal_context_engine/summarizer.py` | LLM-based session summarization using Ollama qwen2.5:14b, decision extraction, blocker summary generation |

### Phase 3: Integration

| File | Logic Change |
|------|-------------|
| `src/universal_context_engine/adapters/__init__.py` | Exports kas_adapter, localcrew_adapter singleton instances |
| `src/universal_context_engine/adapters/kas.py` | KASAdapter class: search(), ask(), ingest(), health() methods against localhost:8000 |
| `src/universal_context_engine/adapters/localcrew.py` | LocalCrewAdapter class: research(), decompose(), get_status(), health() methods against localhost:8001 |

### Phase 4: Intent Router

| File | Logic Change |
|------|-------------|
| `src/universal_context_engine/router/__init__.py` | Exports IntentClassifier, IntentHandler, IntentType enum |
| `src/universal_context_engine/router/classifier.py` | Pattern-based intent classification with regex matchers for RESEARCH, RECALL, KNOWLEDGE, DECOMPOSE, DEBUG, SAVE intents; LLM fallback for ambiguous queries |
| `src/universal_context_engine/router/handlers.py` | IntentHandler routes classified intents to appropriate system calls (research crew, context search, unified search, decomposition) |

### Phase 5: Feedback & Quality

| File | Logic Change |
|------|-------------|
| `src/universal_context_engine/feedback/__init__.py` | Exports feedback_tracker, log_interaction, get_metrics |
| `src/universal_context_engine/feedback/tracker.py` | FeedbackTracker with lazy ChromaDB initialization (matching settings to avoid conflicts), interaction logging, mark_helpful/mark_not_helpful, stats aggregation |
| `src/universal_context_engine/feedback/metrics.py` | QualityMetrics dataclass, get_metrics() function computing success rate, feedback rate, helpful rate, avg latency |
| `src/universal_context_engine/feedback/export.py` | export_training_data() for JSONL export, export_for_dspy() for DSPy optimization format |

### Phase 6: Observability

| File | Logic Change |
|------|-------------|
| `src/universal_context_engine/dashboard/__init__.py` | Exports FastAPI app instance |
| `src/universal_context_engine/dashboard/api.py` | FastAPI dashboard with endpoints: /health (all services), /stats (context stats), /quality (feedback metrics), /sessions, /decisions, /blockers |
| `scripts/start_services.sh` | Bash script to start PostgreSQL (Docker), Redis, KAS API, LocalCrew API, UCE Dashboard |
| `scripts/stop_services.sh` | Bash script to stop all services via pkill |

### Documentation

| File | Logic Change |
|------|-------------|
| `README.md` | Complete rewrite: Quick start, architecture diagram, MCP registration, all 20 tools documented, dashboard API, services table |
| `docs/ARCHITECTURE.md` | System design: component diagram, data flow, storage paths, configuration, error handling |
| `docs/MCP_TOOLS.md` | Complete tool reference: parameters, examples, return values for all 20 tools |
| `docs/TROUBLESHOOTING.md` | Common issues guide: service health, ChromaDB conflicts, MCP server debugging, testing commands |

### Tests

| File | Logic Change |
|------|-------------|
| `tests/__init__.py` | Empty package init |
| `tests/test_context_store.py` | 6 tests: save, search, filter, get_recent, stats, delete |
| `tests/test_server.py` | 5 tests: save_context, search_context, get_recent, recall_work, context_stats tools |
| `tests/test_session.py` | 5 tests: start_session, end_session, capture_decision, capture_blocker, get_blockers |

**Total: 34 files, 9,478 lines added, 16 tests passing**

---

## C. Trade-Off Defense

### 1. ChromaDB vs PostgreSQL/pgvector

**Decision:** ChromaDB for vector storage instead of PostgreSQL with pgvector.

**Defense:** ChromaDB provides zero-configuration local persistence with built-in embedding support. Since KAS already uses PostgreSQL for structured data, adding another pgvector instance would duplicate infrastructure. ChromaDB's file-based storage at `~/.local/share/universal-context/chromadb/` simplifies deployment and backup. Trade-off: No ACID transactions across context + feedback collections.

### 2. Lazy Initialization Pattern

**Decision:** All components lazily initialize their connections (ChromaDB, Redis, Ollama).

**Defense:** Prevents startup failures when optional services (Redis, Ollama) are unavailable. The MCP server can still load and report degraded status via `service_status` tool. Trade-off: First tool call may have higher latency.

### 3. Single ChromaDB Settings Object

**Decision:** Both ContextStore and FeedbackTracker use identical ChromaDB settings (`allow_reset=True`).

**Defense:** ChromaDB throws ValueError if multiple clients access the same path with different settings. Matching settings ensures no conflicts. Trade-off: `allow_reset=True` is slightly less safe but necessary for test isolation.

### 4. Pattern-Based Intent Classification

**Decision:** Regex patterns before LLM fallback for intent routing.

**Defense:** Pattern matching is deterministic, fast (<1ms), and doesn't require Ollama. LLM fallback only triggers for ambiguous queries. Trade-off: Fixed patterns may not cover all natural language variations.

### 5. Ollama for All LLM Operations

**Decision:** Use local Ollama (nomic-embed-text, qwen2.5:14b) instead of cloud APIs.

**Defense:** Aligns with project goal of fully local AI infrastructure. No API costs, no rate limits, works offline. Trade-off: Embedding/generation quality depends on local hardware.

### 6. FastAPI Dashboard Separate from MCP Server

**Decision:** Dashboard runs as separate uvicorn process (port 8002) rather than embedded in MCP.

**Defense:** MCP protocol is stdio-based and doesn't support HTTP endpoints. Separate dashboard allows browser access to metrics. Trade-off: Two processes to manage instead of one.

### 7. No Authentication on Dashboard

**Decision:** Dashboard API has no authentication.

**Defense:** All services run on localhost. Adding auth would complicate local development. Security model assumes trusted local environment. Trade-off: Anyone with localhost access can view metrics.

---

## D. The Audit Mandate (Instructions for Codex)

Codex, please review my work and generate these 7 specific reports based on FACTS and LOGIC, not assumptions:

### 1. Security Issues Summary
Analyze all files for security vulnerabilities including:
- Input validation gaps
- Injection risks (command, SQL, prompt)
- Sensitive data exposure
- Authentication/authorization issues
- Dependency vulnerabilities

### 2. Code Quality Report
Assess code quality metrics:
- Type annotation coverage
- Docstring completeness
- Function complexity (cyclomatic)
- Code duplication
- Naming conventions adherence
- PEP 8 compliance

### 3. Architecture Assessment
Evaluate architectural decisions:
- Component coupling/cohesion
- Single responsibility violations
- Dependency direction issues
- Interface design quality
- Scalability concerns
- Error boundary completeness

### 4. Test Coverage Analysis
Review test suite:
- Coverage percentage estimate
- Missing test cases
- Edge cases not covered
- Integration test gaps
- Mock usage appropriateness
- Test isolation issues

### 5. Performance Observations
Identify performance concerns:
- Blocking operations in async code
- N+1 query patterns
- Memory leak potential
- Connection pool management
- Caching opportunities missed
- Resource cleanup issues

### 6. Risk Assessment
Evaluate project risks:
- Single points of failure
- External dependency risks
- Data integrity concerns
- Recovery/rollback capabilities
- Monitoring blind spots
- Operational complexity

### 7. Improvement Recommendations
Provide actionable improvements:
- Priority-ordered fixes
- Refactoring suggestions
- Missing functionality
- Documentation gaps
- Testing improvements
- Deployment considerations

---

**Files to Review:**
- All files in `src/universal_context_engine/`
- All files in `tests/`
- `docs/ARCHITECTURE.md`
- `scripts/*.sh`
