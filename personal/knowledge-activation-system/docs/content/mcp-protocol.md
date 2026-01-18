# Model Context Protocol (MCP): A Complete Guide

The Model Context Protocol (MCP) is an open standard that enables AI assistants to securely connect to external data sources and tools. It provides a standardized way for LLMs to interact with the world beyond their training data.

## What is MCP?

MCP is a protocol that allows AI models to:
- **Access external data** through secure server connections
- **Execute tools** on behalf of users
- **Maintain context** across conversations
- **Integrate with local resources** like files, databases, and APIs

Think of MCP as a "USB-C for AI" - a universal interface that lets any AI assistant connect to any data source or tool.

## Core Concepts

### MCP Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   AI Assistant  │────▶│   MCP Client    │────▶│   MCP Server    │
│  (Claude, etc.) │     │  (in host app)  │     │ (your service)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │  External Data  │
                                               │  (DB, API, FS)  │
                                               └─────────────────┘
```

### Key Components

1. **MCP Server**: Exposes tools, resources, and prompts to AI assistants
2. **MCP Client**: Connects to servers and manages the protocol
3. **Transport**: Communication layer (stdio, HTTP/SSE)
4. **Tools**: Functions the AI can call
5. **Resources**: Data the AI can read
6. **Prompts**: Pre-defined prompt templates

## MCP Server Structure

### Basic Server Anatomy

```typescript
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

// Create server
const server = new Server(
  {
    name: "my-mcp-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},      // Declare tool support
      resources: {},  // Declare resource support
      prompts: {},    // Declare prompt support
    },
  }
);

// Start with stdio transport
const transport = new StdioServerTransport();
await server.connect(transport);
```

### Tool Definition

```typescript
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";

// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "search_knowledge",
      description: "Search the knowledge base for relevant information",
      inputSchema: {
        type: "object",
        properties: {
          query: {
            type: "string",
            description: "Search query",
          },
          limit: {
            type: "number",
            description: "Maximum results to return",
            default: 10,
          },
        },
        required: ["query"],
      },
    },
  ],
}));

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (name === "search_knowledge") {
    const results = await searchKnowledgeBase(args.query, args.limit);
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(results, null, 2),
        },
      ],
    };
  }

  throw new Error(`Unknown tool: ${name}`);
});
```

### Resource Definition

```typescript
import { ListResourcesRequestSchema, ReadResourceRequestSchema } from "@modelcontextprotocol/sdk/types.js";

// List available resources
server.setRequestHandler(ListResourcesRequestSchema, async () => ({
  resources: [
    {
      uri: "knowledge://notes",
      name: "My Notes",
      description: "Personal knowledge base notes",
      mimeType: "application/json",
    },
  ],
}));

// Read resource content
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const { uri } = request.params;

  if (uri === "knowledge://notes") {
    const notes = await getAllNotes();
    return {
      contents: [
        {
          uri,
          mimeType: "application/json",
          text: JSON.stringify(notes),
        },
      ],
    };
  }

  throw new Error(`Unknown resource: ${uri}`);
});
```

## Creating an MCP Server

### Step 1: Project Setup

```bash
mkdir my-mcp-server
cd my-mcp-server
npm init -y
npm install @modelcontextprotocol/sdk
```

### Step 2: Server Implementation

```typescript
// src/index.ts
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const server = new Server(
  { name: "knowledge-server", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// Define tools
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "kas_search",
      description: "Search the Knowledge Activation System",
      inputSchema: {
        type: "object",
        properties: {
          query: { type: "string", description: "Search query" },
        },
        required: ["query"],
      },
    },
    {
      name: "kas_ingest",
      description: "Add content to the knowledge base",
      inputSchema: {
        type: "object",
        properties: {
          title: { type: "string", description: "Content title" },
          content: { type: "string", description: "Content body" },
          type: { type: "string", enum: ["note", "bookmark", "file"] },
        },
        required: ["title", "content"],
      },
    },
  ],
}));

// Handle tool execution
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case "kas_search":
      const results = await fetch(`http://localhost:8000/api/v1/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: args.query, limit: 10 }),
      }).then((r) => r.json());

      return {
        content: [{ type: "text", text: JSON.stringify(results) }],
      };

    case "kas_ingest":
      // Ingest content
      return { content: [{ type: "text", text: "Content ingested" }] };

    default:
      throw new Error(`Unknown tool: ${name}`);
  }
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("MCP Server running on stdio");
}

main().catch(console.error);
```

### Step 3: Configuration for Claude Code

```json
// ~/.claude/claude_desktop_config.json
{
  "mcpServers": {
    "knowledge": {
      "command": "node",
      "args": ["/path/to/my-mcp-server/dist/index.js"],
      "env": {
        "KAS_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

## Transport Types

### Stdio Transport (Default)

Best for local servers launched by the host application.

```typescript
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const transport = new StdioServerTransport();
await server.connect(transport);
```

### HTTP/SSE Transport

For remote servers or web-based deployments.

```typescript
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import express from "express";

const app = express();
const transport = new SSEServerTransport("/mcp", app);
await server.connect(transport);

app.listen(3001);
```

## Best Practices

### 1. Tool Design

```typescript
// Good: Clear name, description, and schema
{
  name: "search_documents",
  description: "Search for documents by query. Returns title, snippet, and relevance score.",
  inputSchema: {
    type: "object",
    properties: {
      query: {
        type: "string",
        description: "Natural language search query",
      },
      filter: {
        type: "string",
        description: "Optional filter by document type",
        enum: ["all", "notes", "bookmarks", "files"],
      },
    },
    required: ["query"],
  },
}
```

### 2. Error Handling

```typescript
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  try {
    // Tool logic
  } catch (error) {
    return {
      content: [
        {
          type: "text",
          text: `Error: ${error.message}`,
        },
      ],
      isError: true,
    };
  }
});
```

### 3. Resource URIs

Use meaningful, hierarchical URIs:
- `knowledge://notes/daily`
- `knowledge://bookmarks/tech`
- `file:///path/to/document.md`

## MCP in Claude Code

Claude Code uses MCP to access local tools and resources:

```
User: "Search my knowledge base for RAG patterns"
      │
      ▼
Claude Code → MCP Client → kas_search tool → KAS API
      │
      ▼
Results returned to Claude for response generation
```

## References

- MCP Specification: https://spec.modelcontextprotocol.io
- MCP TypeScript SDK: https://github.com/modelcontextprotocol/typescript-sdk
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Claude Code MCP Docs: https://docs.anthropic.com/claude-code/mcp
