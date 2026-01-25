# Unified Personal Context MCP
## Single MCP Server for All Personal Knowledge Sources

---

## Project Overview

### What This Is
A unified MCP server that gives Claude Code direct access to all your personal knowledge sources through both **granular** (source-specific) and **aggregate** (cross-source) tools. Instead of building 5 separate MCP servers, we build one sophisticated server that handles Obsidian, Git, AssistSupport KB, and Knowledge Engine—with built-in memory sophistication for temporal awareness and entity resolution.

### Current Status
**Phase**: Planning Complete → Ready for Implementation
**Priority**: High (daily productivity impact)
**Estimated Effort**: 5-6 sessions

### Key Decisions Made
1. **Merged Architecture**: One MCP server with granular + aggregate tools
2. **Custom Build**: Not using existing MCP servers for tighter integration
3. **Memory Research**: Spike needed to evaluate Mem0 vs Zep vs custom
4. **Scope**: Obsidian, Git, AssistSupport, Knowledge Engine (no Clipboard - no history manager)

---

## Context & Motivation

### The Problem
Every Claude Code session, you manually provide:
- **Project decisions** documented in Obsidian notes
- **Past code patterns** from git history ("I did something similar in...")
- **Recent activity context** ("What was I working on yesterday?")

This context assembly is manual, repetitive, and error-prone.

### The Solution
One MCP server with tools like:
```
@pcl search_all "authentication approach" → searches Obsidian + Git + KB
@pcl get_recent_activity 24 → last 24 hours across all sources
@pcl search_notes "project decisions" → Obsidian only
@pcl get_git_context → branch, recent commits, uncommitted changes
```

### Why This Matters

1. **Unified Context**: Cross-source queries from day one
2. **Memory Sophistication**: Temporal awareness, entity resolution, relevance ranking
3. **Leverage Existing**: Builds on AssistSupport, Knowledge Engine, Obsidian vault
4. **Tool Search Compatible**: Claude Code January 2026 loads tools dynamically

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                      UNIFIED PERSONAL CONTEXT MCP                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         AGGREGATE TOOLS                                  │ │
│  │                                                                          │ │
│  │  search_all(query)        → semantic search across all sources           │ │
│  │  get_recent_activity(hrs) → cross-source timeline                        │ │
│  │  get_working_context()    → "what am I working on?" snapshot             │ │
│  │  get_entity_context(name) → everything about an entity across sources    │ │
│  │                                                                          │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         GRANULAR TOOLS                                   │ │
│  │                                                                          │ │
│  │  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐            │ │
│  │  │   OBSIDIAN      │ │   GIT CONTEXT   │ │  ASSISTSUPPORT  │            │ │
│  │  │                 │ │                 │ │                 │            │ │
│  │  │ search_notes    │ │ get_git_context │ │ search_kb       │            │ │
│  │  │ read_note       │ │ recent_commits  │ │ get_document    │            │ │
│  │  │ get_backlinks   │ │ file_history    │ │ list_namespaces │            │ │
│  │  │ list_tags       │ │ search_commits  │ │                 │            │ │
│  │  │ recent_notes    │ │ diff_summary    │ │                 │            │ │
│  │  └────────┬────────┘ └────────┬────────┘ └────────┬────────┘            │ │
│  │           │                   │                   │                      │ │
│  │  ┌─────────────────┐                                                     │ │
│  │  │ KNOWLEDGE ENGINE│                                                     │ │
│  │  │                 │                                                     │ │
│  │  │ semantic_search │                                                     │ │
│  │  │ hybrid_retrieve │                                                     │ │
│  │  └────────┬────────┘                                                     │ │
│  │           │                                                              │ │
│  └───────────┼──────────────────────────────────────────────────────────────┘ │
│              │                                                                │
│              ▼                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         UNIFIED CONTEXT STORE                            │ │
│  │                                                                          │ │
│  │  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐                  │ │
│  │  │ Vector Index  │ │ Temporal Index│ │ Entity Graph  │                  │ │
│  │  │   (Qdrant)    │ │  (recency)    │ │ (cross-source)│                  │ │
│  │  └───────────────┘ └───────────────┘ └───────────────┘                  │ │
│  │                                                                          │ │
│  │  Memory Layer: [Mem0 | Zep | Custom] ← Research spike needed            │ │
│  │                                                                          │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                           ADAPTERS                                       │ │
│  │                                                                          │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │ │
│  │  │   Obsidian   │ │     Git      │ │ AssistSupport│ │  Knowledge   │   │ │
│  │  │   Adapter    │ │   Adapter    │ │   Adapter    │ │   Engine     │   │ │
│  │  │              │ │              │ │              │ │   Adapter    │   │ │
│  │  │ Direct file  │ │ subprocess   │ │ SQLCipher or │ │ HTTP API     │   │ │
│  │  │ access       │ │ git commands │ │ HTTP API     │ │              │   │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │ │
│  │                                                                          │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Technical Specification

### Unified Context Schema

```python
from pydantic import BaseModel
from typing import List, Dict, Optional, Literal
from datetime import datetime
from enum import Enum

class ContextSource(str, Enum):
    OBSIDIAN = "obsidian"
    GIT = "git"
    ASSISTSUPPORT = "assistsupport"
    KNOWLEDGE_ENGINE = "knowledge_engine"

class ContextType(str, Enum):
    NOTE = "note"
    COMMIT = "commit"
    DIFF = "diff"
    KB_ARTICLE = "kb_article"
    DOCUMENT_CHUNK = "document_chunk"

class RelevanceSignals(BaseModel):
    recency: float = 0.5        # 0-1, exponential decay
    frequency: float = 0.5      # 0-1, access frequency
    source_quality: float = 0.8 # 0-1, source trustworthiness
    semantic_score: float = 0.0 # 0-1, query similarity

class ContextItem(BaseModel):
    id: str
    source: ContextSource
    type: ContextType
    content: str
    title: Optional[str] = None
    embedding: Optional[List[float]] = None
    timestamp: datetime
    metadata: Dict = {}
    entities: List[str] = []
    tags: List[str] = []
    relevance: RelevanceSignals = RelevanceSignals()
    source_path: Optional[str] = None  # File path or URL in source system
```

### MCP Tool Definitions

```python
# Aggregate Tools
@server.tool("search_all")
async def search_all(
    query: str,
    sources: list[str] | None = None,  # Filter to specific sources
    hours: int | None = None,           # Limit to recent
    limit: int = 20
) -> str:
    """Search across all personal knowledge sources."""

@server.tool("get_recent_activity")
async def get_recent_activity(
    hours: int = 24,
    sources: list[str] | None = None
) -> str:
    """Get recent activity across all sources - commits, notes, KB access."""

@server.tool("get_working_context")
async def get_working_context() -> str:
    """
    Get snapshot of current work context:
    - Current git branch and uncommitted changes
    - Recently modified notes
    - Recent KB searches
    """

@server.tool("get_entity_context")
async def get_entity_context(entity: str) -> str:
    """Get everything about an entity across all sources."""

# Granular Tools - Obsidian
@server.tool("search_notes")
async def search_notes(query: str, limit: int = 10) -> str:
    """Search Obsidian vault for notes matching query."""

@server.tool("read_note")
async def read_note(path: str) -> str:
    """Read full contents of an Obsidian note."""

@server.tool("get_backlinks")
async def get_backlinks(path: str) -> str:
    """Find notes that link to this note."""

@server.tool("recent_notes")
async def recent_notes(days: int = 7, limit: int = 10) -> str:
    """Get recently modified notes."""

# Granular Tools - Git
@server.tool("get_git_context")
async def get_git_context(repo: str | None = None) -> str:
    """Get comprehensive git context: branch, status, recent commits."""

@server.tool("file_history")
async def file_history(file: str, count: int = 10) -> str:
    """Get commit history for a specific file."""

@server.tool("search_commits")
async def search_commits(query: str, limit: int = 20) -> str:
    """Search commit messages across repositories."""

# Granular Tools - AssistSupport
@server.tool("search_kb")
async def search_kb(query: str, namespace: str | None = None, limit: int = 10) -> str:
    """Search AssistSupport knowledge base."""

@server.tool("get_kb_document")
async def get_kb_document(doc_id: str) -> str:
    """Get full document from knowledge base."""

# Granular Tools - Knowledge Engine
@server.tool("ke_search")
async def ke_search(query: str, limit: int = 5) -> str:
    """Semantic search via Knowledge Engine."""
```

---

## Implementation Plan

### Session 1: Core Infrastructure + Obsidian Adapter

**Goals:**
- Set up project structure
- Implement base MCP server
- Build Obsidian adapter (direct file access)
- Test with Claude Code

**Tasks:**
1. Create project structure:
   ```
   unified-personal-context/
   ├── pyproject.toml
   ├── src/
   │   ├── __init__.py
   │   ├── server.py          # MCP server entry point
   │   ├── schema.py          # ContextItem, RelevanceSignals
   │   ├── adapters/
   │   │   ├── __init__.py
   │   │   ├── base.py        # Abstract adapter
   │   │   └── obsidian.py    # Obsidian vault adapter
   │   └── store/
   │       ├── __init__.py
   │       └── context_store.py  # In-memory for now
   └── tests/
   ```

2. Implement Obsidian adapter:
   - Configure vault path
   - `search_notes` - ripgrep or Python glob + search
   - `read_note` - frontmatter parsing
   - `get_backlinks` - wikilink regex
   - `recent_notes` - mtime sorting

3. Wire up MCP server with Obsidian tools

4. Test integration with Claude Code

**Deliverable:** Working MCP server with Obsidian search/read capabilities

---

### Session 2: Git Context Adapter + Basic Unified Search

**Goals:**
- Build Git adapter
- Implement basic `search_all` aggregate tool
- Add context store with temporal indexing

**Tasks:**
1. Implement Git adapter:
   - `get_git_context` - branch, status, recent commits
   - `file_history` - git log for file
   - `search_commits` - message search
   - Auto-detect repo from current working directory

2. Create simple context store:
   - In-memory storage with ContextItem schema
   - Temporal index (timestamp-based retrieval)
   - Basic relevance scoring

3. Implement `search_all`:
   - Query all adapters
   - Merge and rank results
   - Return formatted context

4. Implement `get_recent_activity`:
   - Recent git commits
   - Recently modified notes
   - Timeline view

**Deliverable:** Git context + cross-source search working

---

### Session 3: Memory Layer Research Spike

**Goals:**
- Evaluate Mem0, Zep, and custom approaches
- Decide on memory architecture
- Prototype integration

**Evaluation Criteria:**
1. **Memory Sophistication**
   - Temporal awareness (remembers when things happened)
   - Entity resolution (links same concept across sources)
   - Forgetting curves (relevance decay)

2. **Integration with Existing Stack**
   - Works with Qdrant (you already use it)
   - Works with Ollama (nomic-embed-text)
   - Python-native (not JavaScript/TypeScript)

**Candidates:**

| System | Pros | Cons |
|--------|------|------|
| **Mem0** | Production-ready, 90% token savings, supports Ollama, hybrid vector+graph | New dependency, SaaS-oriented |
| **Zep/Graphiti** | Temporal knowledge graphs, sophisticated | Complex, less mature |
| **Custom + Qdrant** | Simple, you control everything, no new deps | Less sophisticated, more work |

**Tasks:**
1. Install and test Mem0 with Ollama backend
2. Install and test Zep (if viable for local)
3. Prototype custom approach with Qdrant + temporal metadata
4. Compare: ingestion, retrieval latency, memory accuracy
5. Document findings and recommendation

**Deliverable:** Memory layer decision documented with benchmarks

---

### Session 4: AssistSupport Investigation + Adapter

**Goals:**
- Figure out AssistSupport data access
- Build AssistSupport adapter
- Integrate with unified search

**Investigation Tasks:**
1. Check AssistSupport config for encryption key location
2. If key available: direct SQLCipher access
3. If not: consider adding HTTP API endpoint to AssistSupport
4. Alternative: export KB to Knowledge Engine format

**Adapter Implementation:**
- `search_kb` - FTS5 search
- `get_kb_document` - full document retrieval
- `list_namespaces` - namespace enumeration

**Deliverable:** AssistSupport KB searchable from MCP

---

### Session 5: Knowledge Engine Integration + Aggregate Tools

**Goals:**
- Connect to Knowledge Engine API
- Implement sophisticated aggregate tools
- Add entity resolution

**Tasks:**
1. Knowledge Engine adapter:
   - `ke_search` - semantic search
   - `ke_hybrid` - combined vector + keyword

2. Implement remaining aggregate tools:
   - `get_working_context` - current work snapshot
   - `get_entity_context` - cross-source entity view

3. Entity resolution:
   - Extract entities from content
   - Link same entity across sources
   - Build simple entity graph

4. Relevance ranking:
   - Recency decay
   - Source quality weighting
   - Semantic similarity

**Deliverable:** Full unified context engine with all sources

---

### Session 6+: Polish & Advanced Features

**Potential Enhancements:**
- Persistent context store (Qdrant collection)
- Background sync/indexing
- MCP resources (context://recent, context://working)
- GraphRAG integration (Project 5 connection)
- Langfuse observability (Project 7 connection)

---

## Configuration

### MCP Server Configuration

```json
// ~/.claude.json addition
{
  "mcpServers": {
    "personal-context": {
      "command": "python",
      "args": ["-m", "unified_personal_context.server"],
      "env": {
        "OBSIDIAN_VAULT": "/Users/d/Documents/Obsidian",
        "ASSISTSUPPORT_DB_KEY": "your-key-here",
        "KNOWLEDGE_ENGINE_URL": "http://localhost:8000",
        "QDRANT_URL": "http://localhost:6333"
      }
    }
  }
}
```

### Environment Configuration

```python
# src/config.py
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # Obsidian
    obsidian_vault: Path = Path.home() / "Documents" / "Obsidian"

    # Git
    git_repos: list[Path] = [Path.home() / "claude-code"]

    # AssistSupport
    assistsupport_db: Path = Path.home() / "Library/Application Support/com.assistsupport/data.db"
    assistsupport_db_key: str = ""

    # Knowledge Engine
    knowledge_engine_url: str = "http://localhost:8000"

    # Vector Store
    qdrant_url: str = "http://localhost:6333"
    embedding_model: str = "nomic-embed-text"

    class Config:
        env_file = ".env"
```

---

## Builds On Existing

| Component | Location | Status |
|-----------|----------|--------|
| Obsidian Vault | ~/Documents/Obsidian (typical) | Your notes |
| Git repos | ~/claude-code | Active |
| AssistSupport | ~/Library/Application Support/com.assistsupport | Feature complete |
| Knowledge Engine | ~/claude-code/personal/knowledge-engine | In progress |
| Qdrant | Via Knowledge Engine | Running |
| nomic-embed-text | Ollama model | Loaded |

---

## Research References

### Memory Frameworks
- [Mem0](https://github.com/mem0ai/mem0) - Universal memory layer, 26% accuracy boost
- [Zep](https://www.graphlit.com/blog/survey-of-ai-agent-memory-frameworks) - Temporal knowledge graphs
- [A-MEM](https://arxiv.org/abs/2502.12110) - Zettelkasten-inspired dynamic indexing (NeurIPS 2025)
- [MemOS](https://statics.memtensor.com.cn/files/MemOS_0707.pdf) - Memory as OS resource

### Personal AI Infrastructure
- [Daniel Miessler's PAI](https://github.com/danielmiessler/Personal_AI_Infrastructure) - 10-file identity system
- [OpenMemory](https://github.com/CaviraOSS/OpenMemory) - Self-hosted cognitive memory

### MCP Best Practices
- [obsidian-claude-code-mcp](https://github.com/iansinnott/obsidian-claude-code-mcp) - Reference implementation
- [Obsidian MCP Forum Discussion](https://forum.obsidian.md/t/obsidian-mcp-servers-experiences-and-recommendations/99936)

---

## Success Criteria

1. **Session 1**: Can search and read Obsidian notes from Claude Code
2. **Session 2**: Can query git context and search across Obsidian + Git
3. **Session 3**: Memory layer decision made with benchmarks
4. **Session 4**: AssistSupport KB accessible (direct or via API)
5. **Session 5**: Full unified search with entity context working
6. **End State**: "What was I working on?" returns rich, relevant cross-source context

---

## Open Questions

1. **Obsidian vault path** - Need to confirm location
2. **AssistSupport encryption** - Key accessible or need API?
3. **Memory layer** - Final decision after Session 3 spike
4. **GraphRAG integration** - Defer to Knowledge Graph Layer project?

---

*Planning completed: January 25, 2026*
*Architecture: Unified MCP with granular + aggregate tools*
*Timeline: 5-6 sessions*
