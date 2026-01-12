# Knowledge Activation System MCP Server

MCP (Model Context Protocol) server that exposes the Knowledge Activation System to Claude Desktop.

## Features

### Tools

| Tool | Description |
|------|-------------|
| `search_knowledge` | Search the knowledge base using hybrid search (BM25 + vector similarity) |
| `get_content` | Get full details of a content item by ID |
| `list_recent` | List recently added content items |
| `get_stats` | Get database statistics |
| `record_review` | Submit a spaced repetition review rating |
| `get_due_reviews` | Get items due for review |

### Resources

| URI | Description |
|-----|-------------|
| `knowledge://stats` | Current database statistics |
| `knowledge://recent` | Content added in the last 7 days |

## Installation

### Prerequisites

1. **PostgreSQL database** - Must have the KAS database running
2. **Python 3.11+** with the knowledge-activation-system package
3. **Ollama** - Running with `nomic-embed-text` model for embeddings

### Install Dependencies

From the project root:

```bash
# Install the MCP package
pip install mcp

# Or add to your existing venv
cd /Users/d/claude-code/personal/knowledge-activation-system
source .venv/bin/activate
pip install mcp
```

### Configure Claude Desktop

Add the following to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "knowledge-activation": {
      "command": "/Users/d/claude-code/personal/knowledge-activation-system/.venv/bin/python",
      "args": [
        "/Users/d/claude-code/personal/knowledge-activation-system/mcp-server/server.py"
      ],
      "env": {
        "KNOWLEDGE_DATABASE_URL": "postgresql://knowledge:localdev@localhost:5432/knowledge",
        "KNOWLEDGE_OLLAMA_URL": "http://localhost:11434"
      }
    }
  }
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KNOWLEDGE_DATABASE_URL` | `postgresql://knowledge:localdev@localhost:5432/knowledge` | PostgreSQL connection URL |
| `KNOWLEDGE_OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `KNOWLEDGE_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model name |
| `KNOWLEDGE_VAULT_PATH` | `~/Obsidian` | Path to Obsidian vault |

## Usage Examples

Once configured, you can use these tools in Claude Desktop:

### Search Knowledge Base

```
Use the search_knowledge tool to find information about "machine learning embeddings"
```

### Get Item Details

```
Get the full content for item ID 123e4567-e89b-12d3-a456-426614174000
```

### Review Due Items

```
What items do I need to review today?
```

### Submit a Review

```
Mark content 123e4567-e89b-12d3-a456-426614174000 as "good" (rating 3)
```

## Development

### Running Locally

```bash
# Activate venv
cd /Users/d/claude-code/personal/knowledge-activation-system
source .venv/bin/activate

# Ensure database is running
docker compose up -d

# Test the server (will wait for MCP protocol input)
python mcp-server/server.py
```

### Debugging

The server logs to stderr. To see logs while running with Claude Desktop:

1. Check Claude Desktop logs
2. Or run the server manually and observe stderr output

### Testing Tools

You can test individual tool handlers by importing them:

```python
import asyncio
from mcp_server.server import handle_search_knowledge, get_database

async def test():
    await get_database()
    result = await handle_search_knowledge({"query": "test", "limit": 5})
    print(result)

asyncio.run(test())
```

## Architecture

```
mcp-server/
├── __init__.py       # Package marker
├── server.py         # Main MCP server with tools and resources
└── README.md         # This file
```

The server integrates with the existing KAS codebase:

- `src/knowledge/db.py` - Database operations
- `src/knowledge/search.py` - Hybrid search
- `src/knowledge/review.py` - FSRS spaced repetition

## Troubleshooting

### Database Connection Failed

Ensure PostgreSQL is running:
```bash
docker compose up -d
docker compose logs postgres
```

### Ollama Not Available

Embeddings require Ollama. Ensure it's running:
```bash
ollama serve
ollama pull nomic-embed-text
```

### MCP Server Not Found in Claude Desktop

1. Verify the path in `claude_desktop_config.json` is correct
2. Ensure the Python path points to the venv with all dependencies
3. Restart Claude Desktop after config changes
