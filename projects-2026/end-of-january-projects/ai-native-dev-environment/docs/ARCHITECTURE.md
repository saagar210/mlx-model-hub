# Architecture

## System Overview

The Universal Context Engine (UCE) is an MCP server that provides persistent memory and orchestration for AI-native development environments. It integrates with existing infrastructure to create a unified context layer.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Claude Code (MCP Client)                     │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Universal Context Engine (MCP Server)            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │   Context   │ │   Session   │ │   Intent    │ │  Feedback │  │
│  │    Store    │ │   Manager   │ │   Router    │ │  Tracker  │  │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └─────┬─────┘  │
│         │               │               │              │         │
│         └───────────────┴───────────────┴──────────────┘         │
│                                  │                                │
└──────────────────────────────────┼────────────────────────────────┘
                                   │
           ┌───────────────────────┼───────────────────────┐
           │                       │                       │
           ▼                       ▼                       ▼
    ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
    │  ChromaDB   │         │    Redis    │         │   Ollama    │
    │ (Persistence)│         │   (Cache)   │         │ (Embeddings)│
    └─────────────┘         └─────────────┘         └─────────────┘
                                   │
           ┌───────────────────────┼───────────────────────┐
           │                       │                       │
           ▼                       ▼                       ▼
    ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
    │  KAS API    │         │ LocalCrew   │         │  Dashboard  │
    │ (Knowledge) │         │  (Crews)    │         │   (API)     │
    └─────────────┘         └─────────────┘         └─────────────┘
```

## Core Components

### Context Store (`context_store.py`)

ChromaDB-backed persistent storage for context items.

**Collections:**
- `uce_context` - All context items (sessions, decisions, patterns, blockers)

**Key Features:**
- Semantic search using Ollama embeddings
- Metadata filtering by type, project, time
- Per-type collections for efficient queries

### Session Manager (`session.py`)

Manages session lifecycle with Redis caching.

**Session State:**
- Project path
- Git branch
- Files modified
- Conversation buffer
- Decisions made
- Blockers encountered

**Lifecycle:**
1. `start_session` - Initialize tracking, load recent context
2. Work happens (decisions, blockers captured)
3. `end_session` - Summarize with LLM, persist to ChromaDB

### Intent Router (`router/`)

Classifies natural language requests and routes to appropriate handlers.

**Intent Types:**
| Intent | Example | Handler |
|--------|---------|---------|
| RESEARCH | "Research how OAuth works" | LocalCrew research crew |
| RECALL | "What was I working on?" | Context search |
| KNOWLEDGE | "Find authentication docs" | Unified search |
| DECOMPOSE | "Break down this task" | LocalCrew decompose crew |
| DEBUG | "This error is happening" | Error analysis |
| SAVE | "Remember this decision" | Context store |

**Classification Strategy:**
1. Pattern matching for high-confidence cases
2. LLM fallback for ambiguous requests

### Feedback Tracker (`feedback/`)

Tracks interactions and collects quality feedback.

**Stored Data:**
- Tool name
- Input parameters
- Output
- Latency
- User feedback (helpful/not helpful)
- Feedback reason

**Metrics:**
- Success rate by tool
- Average latency
- Feedback rate
- Helpful rate

## Adapters

### KAS Adapter (`adapters/kas.py`)

Integrates with Knowledge Activation System (KAS) API.

**Endpoints:**
- `POST /search` - Semantic search
- `POST /ask` - Question answering
- `POST /ingest` - Content ingestion
- `GET /health` - Health check

### LocalCrew Adapter (`adapters/localcrew.py`)

Integrates with LocalCrew API for AI crews.

**Endpoints:**
- `POST /crews/research/run` - Research crew
- `POST /crews/decompose/run` - Task decomposition
- `GET /executions/{id}` - Execution status
- `GET /health` - Health check

## Data Flow

### Context Save Flow

```
User Input → Embedding (Ollama) → ChromaDB Insert → Confirmation
```

### Search Flow

```
Query → Embedding → ChromaDB Search → Metadata Filter → Results
```

### Unified Search Flow

```
Query ──┬── Context Store Search ──┬── Merge → Dedupe → Results
        └── KAS Search ────────────┘
```

### Session Flow

```
Start Session
    ↓
Load Recent Context (ChromaDB)
    ↓
Initialize Redis State
    ↓
Work (capture decisions, blockers)
    ↓
End Session
    ↓
LLM Summarization (Ollama)
    ↓
Persist to ChromaDB
```

## Storage

### ChromaDB

**Location:** `~/.local/share/universal-context/chromadb/`

**Collections:**
- `uce_context` - Main context storage
- `uce_feedback` - Interaction logs

### Redis

**Keys:**
- `session:{id}:project` - Current project
- `session:{id}:branch` - Git branch
- `session:{id}:buffer` - Message buffer
- `session:{id}:files` - Files modified
- `session:{id}:decisions` - Decisions made
- `session:{id}:blockers` - Blockers encountered

## Configuration

See `.env` for all configuration options:

```bash
# Storage
UCE_DATA_DIR=~/.local/share/universal-context
UCE_CHROMADB_PATH=${UCE_DATA_DIR}/chromadb

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
UCE_EMBEDDING_MODEL=nomic-embed-text
UCE_GENERATION_MODEL=qwen2.5:14b

# Redis
UCE_REDIS_URL=redis://localhost:6379

# External Services
UCE_KAS_BASE_URL=http://localhost:8000
UCE_LOCALCREW_BASE_URL=http://localhost:8001
```

## Error Handling

### Service Unavailability

When external services (KAS, LocalCrew, Ollama) are unavailable:
1. Health checks return degraded status
2. Tools gracefully fail with descriptive errors
3. Core functionality (context save/search) continues

### ChromaDB Conflicts

ChromaDB requires consistent settings across clients. The system uses:
- `anonymized_telemetry=False`
- `allow_reset=True`

All components share these settings to avoid conflicts.

## Performance Considerations

### HTTP Client Management

HTTP clients for Ollama and external APIs use lazy initialization - connections are created on first use and reused for subsequent requests.

### Batch Operations

Where possible, batch operations are used for efficiency.

### Future Optimizations (Planned)

- Embedding caching in Redis for frequently accessed content
- Result deduplication in unified search
- Async-safe ChromaDB access via executor

## Security

### No External Network

All services run locally:
- ChromaDB: File-based
- Redis: localhost:6379
- Ollama: localhost:11434
- KAS: localhost:8000
- LocalCrew: localhost:8001

### Sensitive Data Protection

The system includes automatic detection of potentially sensitive content:

**Detected Patterns:**
- API keys (api_key, apikey, etc.)
- Secrets and passwords
- Auth tokens (Bearer, JWT)
- Private keys
- Database credentials
- OpenAI API keys (sk-...)
- GitHub tokens (ghp_..., ghr_...)

When `UCE_WARN_ON_SENSITIVE_DATA=true` (default), the system logs a warning
if content appears to contain sensitive data. Content is not automatically
redacted - users should sanitize data before saving.

**Context items should never contain:**
- API keys
- Passwords
- Personal identifiable information (PII)
- Private keys or certificates

### Data Retention

Configurable retention policies automatically clean up old data:

| Setting | Default | Description |
|---------|---------|-------------|
| `UCE_CONTEXT_RETENTION_DAYS` | 90 | Days to keep context items |
| `UCE_FEEDBACK_RETENTION_DAYS` | 180 | Days to keep feedback logs |
| `UCE_SESSION_RETENTION_DAYS` | 30 | Days to keep session data |

Set any value to 0 to disable retention (keep forever).

Run `retention_cleanup` tool to manually trigger cleanup.

### Production Mode

Set `UCE_PRODUCTION_MODE=true` for production deployments to enable:

1. **Disable ChromaDB Reset**: Prevents accidental `reset()` calls
2. **Stricter Validation**: Additional safeguards for destructive operations
3. **Enhanced Logging**: More detailed audit logs
