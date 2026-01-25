# Developer Memory & Context Suite - Strategy Plan

## Executive Summary
Capture everything you learn while coding, make it searchable, and surface it exactly when needed. Three tools that transform your Knowledge Activation System into a developer-specific memory engine.

---

## Phase 1: DevMemory (Personal Knowledge Graph)
**Timeline: 2-3 weeks | Priority: HIGHEST**

### What It Does
Automatically captures your development activity and builds a searchable knowledge graph. "How did I fix that Postgres timeout issue last month?" becomes answerable.

### Core Features
```
Captures:
├── Code changes (git commits, diffs)
├── Errors encountered (terminal output patterns)
├── Documentation viewed (browser history for docs sites)
├── Stack Overflow visits (questions + accepted answers)
├── Claude Code conversations (exported)
├── IDE activity (files opened, search patterns)
└── Manual notes (markdown snippets)

Queries:
├── "How did I fix the auth timeout?"
├── "What packages did I research for caching?"
├── "Show me all errors I've seen with Postgres"
└── "What did I learn about RAG last week?"
```

### Technical Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                      DevMemory                               │
├─────────────────────────────────────────────────────────────┤
│  Ingestion Layer                                            │
│  ├── GitWatcher (monitors repos, captures commits)          │
│  ├── TerminalHook (captures error patterns)                 │
│  ├── BrowserExtension (docs + SO visits)                    │
│  └── ManualCapture (CLI + hotkey)                           │
├─────────────────────────────────────────────────────────────┤
│  Processing Layer                                           │
│  ├── ChunkProcessor (semantic chunking)                     │
│  ├── EntityExtractor (functions, errors, packages)          │
│  ├── EmbeddingGenerator (nomic-embed-text)                  │
│  └── RelationshipBuilder (links related memories)           │
├─────────────────────────────────────────────────────────────┤
│  Storage Layer (Extends Knowledge Activation System)        │
│  ├── PostgreSQL + pgvector (embeddings)                     │
│  ├── Knowledge Graph (entities + relationships)             │
│  └── TimescaleDB (temporal queries)                         │
├─────────────────────────────────────────────────────────────┤
│  Query Layer                                                │
│  ├── HybridSearch (BM25 + vector + reranking)              │
│  ├── TemporalFilter ("last month", "this week")            │
│  └── GraphTraversal ("related to X")                        │
└─────────────────────────────────────────────────────────────┘
```

### Database Schema (Extends Knowledge System)
```sql
-- Core memories table
CREATE TABLE dev_memories (
    id UUID PRIMARY KEY,
    memory_type VARCHAR(50),  -- 'commit', 'error', 'doc', 'stackoverflow', 'note'
    content TEXT,
    context JSONB,            -- { repo, file, function, error_type, etc. }
    embedding vector(768),
    created_at TIMESTAMPTZ,
    source_url TEXT,
    tags TEXT[]
);

-- Entity extraction
CREATE TABLE dev_entities (
    id UUID PRIMARY KEY,
    entity_type VARCHAR(50),  -- 'function', 'package', 'error', 'concept'
    name TEXT,
    memory_ids UUID[]         -- Links to memories mentioning this entity
);

-- Relationships
CREATE TABLE dev_relationships (
    from_entity UUID REFERENCES dev_entities(id),
    to_entity UUID REFERENCES dev_entities(id),
    relationship_type VARCHAR(50),  -- 'uses', 'fixes', 'related_to'
    strength FLOAT
);
```

### Key Integrations
| Source | How It Captures |
|--------|-----------------|
| Git | File watcher on `.git` directories |
| Terminal | ZSH hook for error patterns |
| Browser | Extension for docs.*, stackoverflow.com |
| Claude Code | Export conversations via API |
| VS Code | Extension for file activity |

### Week-by-Week Plan
| Week | Focus |
|------|-------|
| Week 1 | Core schema, Git watcher, basic CLI queries |
| Week 2 | Entity extraction, relationship building, hybrid search |
| Week 3 | Browser extension, temporal queries, polish |

### Success Criteria
- [ ] Git commits auto-captured with context
- [ ] Errors linked to fixes
- [ ] "How did I fix X?" returns relevant results
- [ ] Search feels instant (<500ms)

---

## Phase 2: CodeMCP (MCP Server for Codebase)
**Timeline: 1-2 weeks | Priority: HIGH**

### What It Does
MCP server that lets Claude Code (and any MCP client) semantically query your codebase. Not just grep - understanding.

### Core Features
```
MCP Tools Exposed:
├── search_code(query) - Semantic search across repos
├── explain_function(name) - Get function explanation + usage
├── find_related(file) - Find conceptually related files
├── get_architecture(repo) - High-level repo structure
└── search_history(query) - Query DevMemory for past context
```

### Technical Architecture
```
┌────────────────────────────────────────────────────┐
│                    CodeMCP Server                   │
├────────────────────────────────────────────────────┤
│  MCP Interface                                     │
│  ├── Tool Definitions                              │
│  ├── Resource Handlers                             │
│  └── Prompt Templates                              │
├────────────────────────────────────────────────────┤
│  Code Understanding Engine                         │
│  ├── AST Parser (tree-sitter)                     │
│  ├── SemanticIndexer (embeddings per function)    │
│  ├── DependencyGraph (imports, calls)             │
│  └── DocstringExtractor                           │
├────────────────────────────────────────────────────┤
│  Storage                                           │
│  ├── Code embeddings (pgvector)                   │
│  ├── AST cache (SQLite)                           │
│  └── DevMemory integration                         │
└────────────────────────────────────────────────────┘
```

### MCP Configuration
```json
// Added to ~/.claude.json
{
  "codemcp": {
    "type": "stdio",
    "command": "python",
    "args": ["-m", "codemcp.server"],
    "env": {
      "REPOS": "/Users/d/claude-code",
      "DEVMEMORY_URL": "postgresql://..."
    }
  }
}
```

### Example Usage in Claude Code
```
User: "Find all functions that handle authentication"

Claude: [Calls codemcp.search_code("authentication handling")]

Result:
- src/auth/login.py:authenticate_user (line 45)
- src/middleware/jwt.py:verify_token (line 23)
- tests/test_auth.py:test_login_flow (line 12)

Claude: These 3 functions handle authentication...
```

### Week-by-Week Plan
| Week | Focus |
|------|-------|
| Week 1 | MCP server scaffold, AST parsing, basic search |
| Week 2 | Semantic indexing, DevMemory integration, polish |

### Success Criteria
- [ ] MCP server starts without errors
- [ ] `search_code` returns relevant functions
- [ ] Integrates with DevMemory for historical context
- [ ] Works with Claude Code out of the box

---

## Phase 3: ContextLens (Smart Context Manager)
**Timeline: 1-2 weeks | Priority: MEDIUM**

### What It Does
Intelligently manages Claude's context window. Ranks files by relevance, auto-includes what's needed, shows usage.

### Core Features
```
┌────────────────────────────────────────────────────┐
│              ContextLens Dashboard                  │
├────────────────────────────────────────────────────┤
│  Context Usage: ████████░░░░░░░░ 42K/200K (21%)    │
├────────────────────────────────────────────────────┤
│  Included Files (ranked by relevance):             │
│  ├── src/auth/login.py (0.94) - 2.1K tokens       │
│  ├── src/models/user.py (0.87) - 1.8K tokens      │
│  ├── tests/test_auth.py (0.72) - 3.2K tokens      │
│  └── + 12 more files...                            │
├────────────────────────────────────────────────────┤
│  Suggestions:                                      │
│  ├── Remove: config.py (low relevance, 800 tok)   │
│  └── Add: middleware/jwt.py (high relevance)      │
└────────────────────────────────────────────────────┘
```

### Technical Architecture
```
ContextLens
├── RelevanceScorer
│   ├── Query-file similarity (embeddings)
│   ├── Recency (recently edited = higher)
│   ├── Dependency proximity (imports)
│   └── DevMemory signals (past relevance)
├── TokenCounter
│   ├── tiktoken for accurate counts
│   └── Compression suggestions
├── ContextOptimizer
│   ├── Auto-include high-relevance
│   ├── Auto-exclude low-relevance
│   └── Summarize large files
└── UI
    ├── CLI dashboard
    ├── VS Code extension
    └── Web UI
```

### Integration with DevMemory + CodeMCP
```
User asks about "auth flow"
       ↓
ContextLens queries CodeMCP → finds relevant files
       ↓
ContextLens queries DevMemory → finds past context
       ↓
Ranks all sources by relevance
       ↓
Includes top files, summarizes rest
       ↓
Shows: "Using 42K tokens, saved 58K by excluding 15 low-relevance files"
```

### Week-by-Week Plan
| Week | Focus |
|------|-------|
| Week 1 | Relevance scoring, token counting, CLI dashboard |
| Week 2 | CodeMCP/DevMemory integration, auto-optimization |

### Success Criteria
- [ ] Shows accurate context usage
- [ ] Relevance ranking feels correct
- [ ] 30%+ token savings on average
- [ ] Integrates with CodeMCP + DevMemory

---

## How The Suite Works Together

```
                    ┌─────────────────┐
                    │    You Code     │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│   DevMemory   │   │    CodeMCP    │   │  ContextLens  │
│   (Captures)  │◄──│   (Queries)   │──►│  (Optimizes)  │
└───────┬───────┘   └───────┬───────┘   └───────────────┘
        │                   │
        └─────────┬─────────┘
                  ▼
        ┌─────────────────┐
        │ Knowledge System │
        │   (PostgreSQL)   │
        └─────────────────┘
```

**Data Flow:**
1. DevMemory captures your work → stores in Knowledge System
2. CodeMCP queries the Knowledge System + live code
3. ContextLens uses both to optimize what Claude sees

---

## Market Analysis

### Why This Stack Wins
| Factor | Status |
|--------|--------|
| Competition | Khoj is closest, but not developer-specific |
| Market Size | Every developer using AI coding tools |
| Timing | Claude Code adoption is exploding |
| Moat | Integration depth with Knowledge System |

### Target Users
1. **Heavy Claude Code users** - Want better context management
2. **Senior devs with large codebases** - Need to find past solutions
3. **Teams** - Share knowledge across developers

### Distribution Strategy
1. **DevMemory**: Launch on HN as "Personal dev knowledge graph"
2. **CodeMCP**: Blog post "Make Claude Code 10x smarter"
3. **ContextLens**: VS Code extension marketplace

---

## Getting Started

### Prerequisites
```bash
# Verify Knowledge System is running
curl http://localhost:5432 # Postgres
ollama list               # Models available

# Verify MCP setup
cat ~/.claude.json | grep mcpServers
```

### First Steps
1. Extend Knowledge System schema for dev-specific tables
2. Build GitWatcher for commit capture
3. Implement basic search
4. Ship DevMemory v0.1
