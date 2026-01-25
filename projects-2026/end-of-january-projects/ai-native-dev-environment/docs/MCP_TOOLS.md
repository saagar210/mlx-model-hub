# MCP Tools Reference

Complete reference for all Universal Context Engine MCP tools.

## Core Context Tools

### save_context

Save a context item with semantic embedding for later retrieval.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `content` | string | Yes | The content to save |
| `context_type` | string | No | One of: session, decision, pattern, context, blocker, error (default: context) |
| `project` | string | No | Project name or path (auto-detected from git) |
| `metadata` | object | No | Additional metadata |

**Example:**
```
save_context(
    content="Use JWT with 24h expiration for API authentication",
    context_type="decision",
    project="knowledge-engine",
    metadata={"category": "security", "rationale": "Balance security with UX"}
)
```

---

### search_context

Search saved context using natural language queries.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | Yes | Natural language search query |
| `type_filter` | string | No | Filter by type: session, decision, pattern, context, blocker, error |
| `project` | string | No | Filter by project (auto-detected if not provided) |
| `limit` | integer | No | Max results (default: 5) |

**Example:**
```
search_context(
    query="authentication decisions",
    project="knowledge-engine",
    limit=5
)
```

---

### get_recent

Get recent context items, optionally filtered.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project` | string | No | Filter by project (auto-detected if not provided) |
| `hours` | integer | No | Time window in hours (default: 24) |
| `type_filter` | string | No | Filter by type: session, decision, pattern, context, blocker, error |
| `limit` | integer | No | Max results (default: 10) |

**Example:**
```
get_recent(project="knowledge-engine", hours=48, limit=10)
```

---

### recall_work

Get a summary of recent work. Answers "What was I working on?"

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project` | string | No | Filter by project |
| `hours` | integer | No | Time window (default: 24) |

**Example:**
```
recall_work(project="knowledge-engine")
```

**Returns:**
A natural language summary of recent sessions, decisions, and blockers.

---

### context_stats

Get statistics about stored context.

**Parameters:** None

**Returns:**
```json
{
  "by_type": {
    "session": 15,
    "decision": 8,
    "blocker": 3
  },
  "total": 26
}
```

---

## Session Management Tools

### start_session

Initialize a new development session with context loading.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project` | string | No | Project path override (auto-detected from git if not provided) |

**Example:**
```
start_session(project="/Users/d/projects/my-app")
```

**Returns:**
Recent context relevant to the project including recent sessions, decisions, and blockers.

---

### end_session

End the current session, generating a summary.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `conversation_excerpt` | string | No | Key points or summary of what was done |
| `files_modified` | array | No | List of files that were modified |

**Example:**
```
end_session(
    conversation_excerpt="Implemented OAuth flow and fixed redirect bug",
    files_modified=["auth.py", "routes.py"]
)
```

**Returns:**
Generated session summary that gets persisted to ChromaDB.

---

### capture_decision

Record an architectural or design decision.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `decision` | string | Yes | The decision made |
| `rationale` | string | No | Why this decision was made |
| `category` | string | No | Category (architecture, security, etc.) |

**Example:**
```
capture_decision(
    decision="Use PostgreSQL instead of SQLite",
    rationale="Need concurrent writes and full-text search",
    category="database"
)
```

---

### capture_blocker

Record a blocker or issue for follow-up.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `description` | string | Yes | Description of the blocker |
| `severity` | string | No | low, medium, high (default: medium) |
| `context` | string | No | Additional context |

**Example:**
```
capture_blocker(
    blocker="OAuth redirect not working in production",
    severity="high",
    context="Works locally, fails with 302 on deployed version"
)
```

---

### get_blockers

List unresolved blockers.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `project` | string | No | Filter by project |
| `include_resolved` | boolean | No | Include resolved blockers |

**Example:**
```
get_blockers(project="knowledge-engine")
```

---

## Integration Tools

### unified_search

Search across both local context and KAS knowledge base.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | Yes | Search query |
| `sources` | array | No | Sources to search: ["context", "kas"] |
| `limit` | integer | No | Max results per source |

**Example:**
```
unified_search(
    query="how to implement rate limiting",
    sources=["context", "kas"]
)
```

---

### research

Trigger a LocalCrew research crew for deep research.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `topic` | string | Yes | Research topic |
| `depth` | string | No | shallow, medium, deep (default: medium) |

**Example:**
```
research(topic="GraphRAG implementation patterns", depth="deep")
```

**Returns:**
Research results from the LocalCrew research crew.

---

### decompose_task

Break a complex task into subtasks using LocalCrew.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `task` | string | Yes | Task description |
| `context` | string | No | Additional context |

**Example:**
```
decompose_task(
    task="Implement user authentication with OAuth2",
    context="Python FastAPI backend, React frontend"
)
```

---

### ingest_to_kas

Add content to the KAS knowledge base.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `content` | string | Yes | Content to ingest |
| `title` | string | Yes | Document title |
| `tags` | array | No | Tags for categorization |
| `source` | string | No | Content source |

**Example:**
```
ingest_to_kas(
    content="Full OAuth2 implementation guide...",
    title="OAuth2 Implementation Guide",
    tags=["oauth", "security", "authentication"]
)
```

---

### service_status

Check health status of all integrated services.

**Parameters:** None

**Returns:**
```json
{
  "ollama": {"status": "healthy", "url": "http://localhost:11434"},
  "kas": {"status": "healthy", "url": "http://localhost:8000"},
  "localcrew": {"status": "degraded", "error": "Connection refused"},
  "redis": {"status": "healthy"},
  "chromadb": {"status": "healthy", "items": 156}
}
```

---

## Intent Routing Tools

### smart_request

Automatically route a natural language request to the appropriate system.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `request` | string | Yes | Natural language request |
| `project` | string | No | Project context |

**Example:**
```
smart_request(request="Research how to implement caching in FastAPI")
```

**Routing Logic:**
- "Research..." → LocalCrew research crew
- "What was I..." → Context recall
- "Find..." → Unified search
- "Break down..." → Task decomposition
- "Error..." → Error analysis

---

### explain_routing

Show how a request would be routed without executing.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `request` | string | Yes | The request to analyze |

**Example:**
```
explain_routing(request="Research caching strategies")
```

**Returns:**
```json
{
  "intent": "RESEARCH",
  "confidence": 0.92,
  "handler": "research",
  "reason": "Matched pattern: 'research'"
}
```

---

## Feedback Tools

### feedback_helpful

Mark the last interaction as helpful.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `interaction_id` | string | No | Specific interaction ID |

**Example:**
```
feedback_helpful()
```

---

### feedback_not_helpful

Mark the last interaction as not helpful with optional reason.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `interaction_id` | string | No | Specific interaction ID |
| `reason` | string | No | Why it wasn't helpful |

**Example:**
```
feedback_not_helpful(reason="Results were not relevant to my query")
```

---

### quality_stats

Get quality metrics from feedback data.

**Parameters:** None

**Returns:**
```json
{
  "total_interactions": 234,
  "helpful_count": 198,
  "not_helpful_count": 12,
  "feedback_rate": 0.897,
  "helpful_rate": 0.943,
  "avg_latency_ms": 245,
  "by_tool": {
    "search_context": 89,
    "unified_search": 56,
    "research": 23
  }
}
```

---

### export_feedback_data

Export feedback data for training optimization.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `tool` | string | No | Filter by specific tool |
| `format` | string | No | dspy, jsonl (default: jsonl) |
| `min_examples` | integer | No | Minimum examples required |

**Example:**
```
export_feedback_data(tool="search_context", format="dspy")
```

---

## Context Types

| Type | Description | Use Case |
|------|-------------|----------|
| `session` | Session summaries | End of work session |
| `decision` | Architectural decisions | ADRs, design choices |
| `pattern` | Code patterns | Reusable solutions |
| `context` | General context | Notes, observations |
| `blocker` | Blockers/issues | Problems to resolve |
| `error` | Error information | Debugging context |

## Error Responses

All tools return errors in a consistent format:

```json
{
  "error": "Service unavailable",
  "service": "localcrew",
  "details": "Connection refused at localhost:8001"
}
```

Common error types:
- Service unavailable
- Invalid parameters
- Not found
- Rate limited
