# KAS MCP Server

Model Context Protocol server for the Knowledge Activation System. Query your personal knowledge base directly from Claude Code.

## Quick Start

1. **Ensure KAS is running:**
   ```bash
   cd /Users/d/claude-code/personal/knowledge-activation-system
   uv run uvicorn knowledge.api.main:app --host 0.0.0.0 --port 8000
   ```

2. **Restart Claude Code** to load the new MCP server.

3. **Use the tools:**
   - Search: `kas_search("How to implement RAG")`
   - Ask: `kas_ask("What's the difference between BM25 and vector search?")`
   - Capture: `kas_capture("content", "title")`
   - Stats: `kas_stats()`

## Available Tools

### `kas_search`
Search your personal knowledge base for relevant information.

**Use for:** Finding documentation, code examples, notes, and other content you've previously saved.

**Examples:**
- "How to implement RAG with LlamaIndex"
- "FastAPI dependency injection patterns"
- "Kubernetes deployment strategies"

**Returns:** Ranked results with content snippets and metadata.

### `kas_ask`
Ask a question and get a synthesized answer from your knowledge base.

**Use for:** Getting direct answers by analyzing relevant content and synthesizing information from multiple sources.

**Best for:**
- "How does X work?"
- "What's the difference between X and Y?"
- "Explain the process for doing X"

**Returns:** Answer with confidence score and source citations.

### `kas_capture`
Quickly capture content into your knowledge base for future reference.

**Use for:**
- Code snippets you want to remember
- Important information discovered during coding
- Notes and learnings from the current session

**Returns:** Confirmation with chunk count and content ID.

### `kas_stats`
Get statistics about your knowledge base.

**Returns:**
- Total documents stored
- Total chunks indexed
- System health status

## Configuration

The MCP server is registered in `~/.claude/mcp_settings.json`:

```json
{
  "mcpServers": {
    "kas": {
      "command": "node",
      "args": ["/Users/d/claude-code/personal/knowledge-activation-system/mcp-server/dist/index.js"],
      "env": {
        "KAS_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

## Development

```bash
cd /Users/d/claude-code/personal/knowledge-activation-system/mcp-server

# Install dependencies
npm install

# Build
npm run build

# Development mode
npm run dev

# Type check
npm run typecheck
```

## Testing

Test the MCP server manually:

```bash
# Test tool listing
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | node dist/index.js

# Test stats tool
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"kas_stats","arguments":{}}}' | node dist/index.js
```

## Requirements

- Node.js >= 20.0.0
- KAS API running on localhost:8000
- PostgreSQL with knowledge data

## Troubleshooting

### KAS API Not Available

If you see "KAS API is not available", ensure the API is running:

```bash
cd /Users/d/claude-code/personal/knowledge-activation-system
uv run uvicorn knowledge.api.main:app --host 0.0.0.0 --port 8000
```

### MCP Server Not Loaded

1. Check `~/.claude/mcp_settings.json` has the kas entry
2. Restart Claude Code
3. Verify the dist/index.js path is correct

### Build Errors

```bash
npm install
npm run build
```

## Architecture

```
mcp-server/
├── src/
│   ├── index.ts       # Main MCP server with tool handlers
│   └── kas-client.ts  # KAS API client
├── dist/              # Built JavaScript
├── package.json
├── tsconfig.json
└── README.md
```
