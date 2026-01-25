# KAS Integration Guide

## Overview

This project is connected to the Knowledge Activation System (KAS), enabling:
- Semantic search across your entire knowledge base
- AI-powered Q&A with confidence scoring
- Automatic knowledge capture from project learnings

## Prerequisites

Ensure KAS is running:

```bash
# Check KAS health
curl http://localhost:8000/api/v1/health | jq

# Expected response
{
  "status": "healthy",
  "stats": {
    "total_content": 189,
    "total_chunks": 951
  }
}
```

## MCP Server Setup

The MCP server is pre-configured in `.claude/mcp_settings.json`. After starting a new Claude Code session, the following tools are available:

### kas_search
Search your knowledge base with semantic + keyword hybrid search.

**Parameters:**
- `query` (required): Search query
- `limit` (optional): Max results (default: 5)
- `namespace` (optional): Filter by namespace

**Example:**
```
Search for: "React hooks best practices"
```

### kas_ask
Ask questions and get AI-synthesized answers with citations.

**Parameters:**
- `query` (required): Your question
- `context_limit` (optional): Number of context chunks (default: 5)

**Example:**
```
Ask: "How do I implement authentication in FastAPI?"
```

### kas_capture
Save new learnings discovered during this project.

**Parameters:**
- `title` (required): Brief title
- `content` (required): The knowledge content
- `namespace` (optional): Where to store (default: "captured")
- `content_type` (optional): Type (default: "note")

**Example:**
```
Capture:
  title: "PostgreSQL Connection Pooling Pattern"
  content: "When using asyncpg with FastAPI..."
  namespace: "projects/my-project"
```

### kas_stats
Check KAS health and statistics.

**Example Output:**
```
KAS Statistics:
- Total Documents: 189
- Total Chunks: 951
- Review Items Due: 5
```

## Capture Workflow

When you solve a non-trivial problem or learn something valuable:

1. **Identify the learning**: What did you figure out?
2. **Capture it**: Use `kas_capture` with clear title and content
3. **Namespace it**: Use `projects/{project-name}` for project-specific knowledge
4. **Review later**: Items appear in spaced repetition queue

## Namespace Convention

```
projects/{project-name}     # Project-specific learnings
frameworks/{name}           # Framework knowledge
tools/{name}                # Tool-specific tips
best-practices              # General best practices
decisions                   # Architectural decisions
```

## Troubleshooting

### MCP Server Not Available
```bash
# Check if built
ls /Users/d/claude-code/personal/knowledge-activation-system/mcp-server/dist/index.js

# Rebuild if needed
cd /Users/d/claude-code/personal/knowledge-activation-system/mcp-server
npm run build
```

### KAS API Not Running
```bash
# Start KAS
cd /Users/d/claude-code/personal/knowledge-activation-system
uv run uvicorn knowledge.api.main:app --host 0.0.0.0 --port 8000
```

### Empty Search Results
- Check if content exists: `curl http://localhost:8000/api/v1/content?page_size=5`
- Try broader query terms
- Check namespace filter isn't too restrictive
