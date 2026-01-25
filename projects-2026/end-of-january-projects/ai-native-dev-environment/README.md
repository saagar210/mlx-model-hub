# Universal Context Engine

Persistent memory and orchestration for AI-native development environments.

## Overview

The Universal Context Engine provides:

- **Persistent Memory**: ChromaDB-backed semantic storage that persists across Claude Code sessions
- **Context Retrieval**: Search past sessions, decisions, patterns, and blockers using natural language
- **Session Management**: Automatic capture and summarization of development sessions
- **Unified Search**: Aggregated search across local context, KAS, and other knowledge sources
- **Intent Routing**: Smart routing of natural language requests to appropriate systems
- **Quality Tracking**: Feedback collection and metrics for continuous improvement

## Quick Start

```bash
# Install dependencies
uv sync

# Start required services
./scripts/start_services.sh

# Verify installation
uv run python -c "from universal_context_engine import mcp; print('OK')"
```

## Architecture

```
Universal Context Engine (MCP Server)
├── ChromaDB (semantic search over sessions, decisions, patterns)
├── Redis (hot session cache)
├── Ollama (embeddings + summarization)
└── Adapters:
    ├── KAS API (localhost:8000) - Knowledge base
    ├── LocalCrew API (localhost:8001) - AI crews
    └── Session/Git context
```

## MCP Registration

Add to `~/.claude/mcp_settings.json`:

```json
{
  "universal-context": {
    "command": "uv",
    "args": ["run", "--directory", "/path/to/ai-native-dev-environment", "python", "-m", "universal_context_engine.server"],
    "env": {
      "UCE_DATA_DIR": "~/.local/share/universal-context",
      "OLLAMA_BASE_URL": "http://localhost:11434"
    }
  }
}
```

## MCP Tools

### Core Context (Phase 1)

| Tool | Description |
|------|-------------|
| `save_context` | Save context item with semantic embedding |
| `search_context` | Search context using natural language |
| `get_recent` | Get recent context items |
| `recall_work` | Summarize recent work ("What was I working on?") |
| `context_stats` | Get storage statistics |

### Session Management (Phase 2)

| Tool | Description |
|------|-------------|
| `start_session` | Initialize session and load recent context |
| `end_session` | Summarize and save session |
| `capture_decision` | Record an architectural decision |
| `capture_blocker` | Record a blocker for follow-up |
| `get_blockers` | List unresolved blockers |

### Integration (Phase 3)

| Tool | Description |
|------|-------------|
| `unified_search` | Search across context + KAS |
| `research` | Trigger LocalCrew research crew |
| `decompose_task` | Break task into subtasks via LocalCrew |
| `ingest_to_kas` | Add content to knowledge base |
| `service_status` | Check health of all services |

### Intent Routing (Phase 4)

| Tool | Description |
|------|-------------|
| `smart_request` | Auto-route request based on intent |
| `explain_routing` | Show how a request would be routed |

### Feedback & Quality (Phase 5)

| Tool | Description |
|------|-------------|
| `feedback_helpful` | Mark last interaction as helpful |
| `feedback_not_helpful` | Mark last interaction as not helpful |
| `quality_stats` | Get quality metrics |
| `export_feedback_data` | Export data for training |

## Dashboard API

The dashboard runs on port 8002 and provides observability endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health status of all services |
| `GET /stats` | Context storage statistics |
| `GET /quality` | Quality metrics from feedback |
| `GET /sessions` | Recent session list |
| `GET /decisions` | Recent decisions |
| `GET /blockers` | Active blockers |

Start the dashboard:
```bash
uv run uvicorn universal_context_engine.dashboard.api:app --host 0.0.0.0 --port 8002
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| KAS API | 8000 | Knowledge base |
| LocalCrew API | 8001 | AI crews |
| UCE Dashboard | 8002 | Observability |
| Ollama | 11434 | Embeddings/LLM |
| Redis | 6379 | Session cache |
| PostgreSQL | 5433 | KAS/LocalCrew DB |

## Scripts

```bash
# Start all services
./scripts/start_services.sh

# Stop all services
./scripts/stop_services.sh
```

## Requirements

- Python 3.11+
- Ollama with `nomic-embed-text` and `qwen2.5:14b` models
- Redis
- Docker (for PostgreSQL)

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [MCP Tools Reference](docs/MCP_TOOLS.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
