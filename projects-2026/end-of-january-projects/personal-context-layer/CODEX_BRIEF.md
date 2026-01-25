# CODEX BRIEF: Personal Context Layer MCP Server

**Prepared by:** Junior Developer (Claude Opus 4.5)
**Date:** 2026-01-25
**Project:** personal-context-layer

---

## A. State Transition

- **From:** Empty project directory with only PROJECT.md planning document
- **To:** Fully implemented Python MCP server with 17 tools across 4 adapters (Obsidian, Git, KAS) plus aggregate cross-source functionality, 40 passing tests

---

## B. Change Manifest (Evidence Anchors)

### Core Infrastructure
| File | Logic Change |
|------|--------------|
| `pyproject.toml` | Defined project metadata, dependencies (mcp, pydantic, httpx, frontmatter), and dev tools (pytest, ruff) |
| `.env` | Configuration for OBSIDIAN_VAULT, GIT_REPOS, KAS_API_URL paths |
| `src/personal_context/__init__.py` | Package initialization with version |
| `src/personal_context/__main__.py` | Entry point for `python -m personal_context` execution |
| `src/personal_context/config.py` | Pydantic Settings class loading from environment variables |
| `src/personal_context/schema.py` | Data models: ContextItem, ContextSource enum, NoteResult, SearchResult |

### Adapters Layer
| File | Logic Change |
|------|--------------|
| `src/personal_context/adapters/base.py` | Abstract base class defining adapter interface: `search()`, `get_recent()`, `health_check()` |
| `src/personal_context/adapters/obsidian.py` | ~200 LOC adapter reading markdown files, parsing YAML frontmatter, extracting wikilinks for backlinks, glob-based search with relevance scoring |
| `src/personal_context/adapters/git.py` | ~250 LOC adapter using subprocess to run git commands, parsing log output, searching commit messages across repos |
| `src/personal_context/adapters/kas.py` | ~170 LOC HTTP client adapter using httpx to query KAS API at localhost:8000, with graceful degradation when unavailable |

### Server Layer
| File | Logic Change |
|------|--------------|
| `src/personal_context/server.py` | FastMCP server exposing 17 tools: 5 Obsidian (search_notes, read_note, get_backlinks, recent_notes, notes_by_tag), 5 Git (get_git_context, search_commits, file_history, recent_commits, git_diff), 3 KAS (kas_search, kas_ask, kas_namespaces), 4 Aggregate (search_all, get_recent_activity, get_working_context, get_entity_context) |

### Utilities Layer
| File | Logic Change |
|------|--------------|
| `src/personal_context/utils/fusion.py` | Reciprocal Rank Fusion algorithm for combining multi-source results, content deduplication using Jaccard similarity, time decay scoring |
| `src/personal_context/utils/relevance.py` | Relevance scoring with source weights (Obsidian=0.9, Git=0.7, KAS=0.8), query boost calculation, result interleaving for diversity |
| `src/personal_context/utils/entities.py` | Entity extraction using regex patterns for technologies, projects, file paths; entity mention finding with fuzzy matching |

### Tests
| File | Logic Change |
|------|--------------|
| `tests/conftest.py` | Pytest fixtures creating temporary Obsidian vault with test notes |
| `tests/test_obsidian.py` | 12 tests covering search, read, backlinks, tags, recent notes |
| `tests/test_git.py` | 8 tests covering commit search, repo context, file history, diff |
| `tests/test_kas.py` | 7 tests covering offline behavior, result conversion |
| `tests/test_aggregation.py` | 13 tests covering RRF fusion, deduplication, entity extraction, relevance scoring |

### Documentation
| File | Logic Change |
|------|--------------|
| `README.md` | Complete documentation with architecture diagram, tool reference table, usage examples |

---

## C. Trade-Off Defense

### 1. **Python over TypeScript**
*Decision:* Built new Python MCP server instead of extending existing TypeScript KAS MCP
*Rationale:* FastMCP decorator syntax is cleaner, Mem0 memory layer is Python-native, direct integration with KAS Python modules possible. The existing KAS MCP remains as fallback.

### 2. **Lazy Adapter Initialization**
*Decision:* Adapters are instantiated on first use via getter functions, not at module load
*Rationale:* Prevents startup failures if one source (e.g., KAS) is unavailable. Each adapter can fail independently without breaking the entire server.

### 3. **Reciprocal Rank Fusion over Raw Score Fusion**
*Decision:* Used RRF (1/(k+rank)) instead of normalizing and combining raw scores
*Rationale:* RRF is robust to different score scales across sources. Obsidian returns 0-1 scores, Git returns match counts, KAS returns similarity distances. RRF handles this heterogeneity elegantly.

### 4. **Subprocess for Git over libgit2**
*Decision:* Shell out to `git` CLI instead of using a Git library
*Rationale:* Git CLI is universally available, handles all edge cases, and output parsing is straightforward. Avoids dependency on native bindings that may have compilation issues.

### 5. **Simple Regex Entity Extraction over NER Model**
*Decision:* Used pattern matching for known technologies and project names instead of ML-based NER
*Rationale:* Lower latency (<10ms vs 500ms+), no model loading overhead, sufficient accuracy for technical content. Can upgrade to LLM extraction later if needed.

### 6. **Source Weights as Configuration**
*Decision:* Hardcoded default weights (Obsidian=0.9, Git=0.7, KAS=0.8)
*Rationale:* Personal notes (Obsidian) are more immediately relevant than commit history. Weights can be overridden if needed. Avoided premature optimization of learning weights.

### 7. **Skipped Mem0 Integration**
*Decision:* Implemented custom entity extraction and relevance scoring instead of Mem0
*Rationale:* Mem0 adds external dependency (Qdrant, Ollama) and latency. Current implementation meets requirements. Mem0 can be added in Phase 6 if cross-session memory becomes critical.

---

## D. The Audit Mandate

> **Codex, please review my work and generate these 7 specific reports based on FACTS and LOGIC, not assumptions:**
>
> 1. **Security Issues Summary** - Analyze file path handling, subprocess calls, HTTP client usage, and any potential injection vectors
> 2. **Code Quality Report** - Evaluate adherence to PEP8, type hints usage, error handling patterns, and code duplication
> 3. **Architecture Assessment** - Review adapter abstraction, separation of concerns, dependency injection, and extensibility
> 4. **Test Coverage Analysis** - Identify untested code paths, missing edge cases, and test quality metrics
> 5. **Performance Observation** - Flag any N+1 patterns, blocking I/O, memory leaks, or inefficient algorithms
> 6. **Risk Assessment** - Evaluate failure modes, graceful degradation, and operational concerns
> 7. **Improvement Recommendations** - Prioritized list of enhancements with effort/impact analysis

---

## Files for Review

```
personal-context-layer/
├── pyproject.toml
├── .env
├── README.md
├── src/personal_context/
│   ├── __init__.py
│   ├── __main__.py
│   ├── server.py            # 17 MCP tools
│   ├── config.py
│   ├── schema.py
│   ├── adapters/
│   │   ├── base.py
│   │   ├── obsidian.py
│   │   ├── git.py
│   │   └── kas.py
│   └── utils/
│       ├── fusion.py
│       ├── relevance.py
│       └── entities.py
└── tests/
    ├── conftest.py
    ├── test_obsidian.py
    ├── test_git.py
    ├── test_kas.py
    └── test_aggregation.py
```

---

*End of Brief*
