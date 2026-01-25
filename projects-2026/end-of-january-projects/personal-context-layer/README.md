# Personal Context Layer

Unified MCP server providing Claude Code with access to personal knowledge sources: Obsidian notes, Git history, and KAS knowledge base.

## Features

- **17 Tools** across 4 categories (Obsidian, Git, KAS, Aggregate)
- **Cross-source search** with Reciprocal Rank Fusion
- **Entity resolution** to find related content across sources
- **Relevance scoring** with recency decay and source weighting
- **Working context** snapshot for current project state

## Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

## Configuration

Create `.env` file:

```bash
OBSIDIAN_VAULT=/Users/d/Obsidian
GIT_REPOS=/Users/d/claude-code
KAS_API_URL=http://localhost:8000
```

Add to `~/.claude/mcp_settings.json`:

```json
{
  "mcpServers": {
    "personal-context": {
      "command": "/path/to/.venv/bin/python",
      "args": ["-m", "personal_context"],
      "cwd": "/path/to/personal-context-layer",
      "env": {
        "OBSIDIAN_VAULT": "/Users/d/Obsidian",
        "KAS_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

## Tools

### Obsidian (5 tools)

| Tool | Description |
|------|-------------|
| `search_notes` | Search notes by content and filename |
| `read_note` | Read full note with frontmatter |
| `get_backlinks` | Find notes linking to a note |
| `recent_notes` | Get recently modified notes |
| `notes_by_tag` | Find notes with specific tag |

### Git (5 tools)

| Tool | Description |
|------|-------------|
| `get_git_context` | Current branch, status, recent commits |
| `search_commits` | Search commit messages |
| `file_history` | Commit history for a file |
| `recent_commits` | Recent commits across repos |
| `git_diff` | Summary of uncommitted changes |

### KAS (3 tools)

| Tool | Description |
|------|-------------|
| `kas_search` | Search knowledge base |
| `kas_ask` | Q&A with confidence scores |
| `kas_namespaces` | List available namespaces |

### Aggregate (4 tools)

| Tool | Description |
|------|-------------|
| `search_all` | Cross-source search with RRF fusion |
| `get_recent_activity` | Timeline from all sources |
| `get_working_context` | Current work snapshot |
| `get_entity_context` | Everything about an entity |

## Usage Examples

```
# Search across all sources
search_all "authentication"

# Get current working context
get_working_context

# Find everything about OAuth
get_entity_context "OAuth"

# Search Obsidian notes
search_notes "project decisions"

# Get git context
get_git_context
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              UNIFIED PERSONAL CONTEXT MCP (Python)              │
├─────────────────────────────────────────────────────────────────┤
│  AGGREGATE TOOLS              │  GRANULAR TOOLS                 │
│  search_all(query)            │  Obsidian: search_notes,        │
│  get_recent_activity(hrs)     │           read_note, backlinks  │
│  get_working_context()        │  Git: get_git_context,          │
│  get_entity_context(name)     │       file_history, commits     │
│                               │  KAS: kas_search, kas_ask       │
├───────────────────────────────┴─────────────────────────────────┤
│                         ADAPTERS                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                        │
│  │ Obsidian │ │   Git    │ │   KAS    │                        │
│  │ ~/Obsidian│ │subprocess│ │HTTP:8000 │                        │
│  └──────────┘ └──────────┘ └──────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

## Development

```bash
# Run tests
pytest tests/ -v

# Type check
mypy src/

# Lint
ruff check src/
```

## Project Structure

```
personal-context-layer/
├── pyproject.toml
├── .env
├── src/personal_context/
│   ├── __init__.py
│   ├── __main__.py          # Entry point
│   ├── server.py            # FastMCP server (17 tools)
│   ├── config.py            # Pydantic Settings
│   ├── schema.py            # ContextItem models
│   ├── adapters/
│   │   ├── base.py          # AbstractContextAdapter
│   │   ├── obsidian.py      # Obsidian vault adapter
│   │   ├── git.py           # Git context adapter
│   │   └── kas.py           # KAS HTTP client
│   └── utils/
│       ├── fusion.py        # RRF result fusion
│       ├── relevance.py     # Scoring functions
│       └── entities.py      # Entity extraction
└── tests/
    ├── test_obsidian.py
    ├── test_git.py
    ├── test_kas.py
    └── test_aggregation.py
```

## Tests

- **40 tests** covering all adapters and utilities
- Unit tests for each adapter
- Integration tests for cross-source functionality
- Aggregation and entity extraction tests
