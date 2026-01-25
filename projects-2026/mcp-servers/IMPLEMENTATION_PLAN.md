# Project 3: MCP Server Suite

## Overview
A collection of Model Context Protocol (MCP) servers that expose your local infrastructure to Claude Code and other MCP-compatible clients.

## What is MCP?
MCP (Model Context Protocol) is an open standard by Anthropic that allows AI assistants to interact with external tools and data sources. It's like LSP (Language Server Protocol) but for AI.

## Servers to Build

| Server | Purpose | Priority |
|--------|---------|----------|
| **knowledge-mcp** | Query Knowledge Engine | High |
| **agent-mcp** | Trigger LangGraph workflows | High |
| **mlx-mcp** | Local model inference | Medium |
| **file-mcp** | Enhanced file operations | Medium |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Claude Code / MCP Client                      │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ MCP Protocol (JSON-RPC over stdio)
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│                        MCP Server Suite                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │ knowledge-mcp│  │  agent-mcp   │  │   mlx-mcp    │             │
│  │  (Port 3001) │  │  (Port 3002) │  │  (Port 3003) │             │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │
└─────────┼─────────────────┼─────────────────┼───────────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────┐
│  Knowledge   │  │  Agent Platform  │  │    Ollama    │
│   Engine     │  │   (LangGraph)    │  │   (MLX/LLM)  │
│ (Project 1)  │  │   (Project 2)    │  │              │
└──────────────┘  └──────────────────┘  └──────────────┘
```

## Technology Stack

| Component | Technology |
|-----------|------------|
| **Runtime** | Python 3.12 or Node.js |
| **MCP SDK** | `@modelcontextprotocol/sdk` (TS) or `mcp` (Python) |
| **Transport** | stdio (default) or SSE |

## Implementation

### Server 1: Knowledge MCP

#### Project Structure
```
mcp-servers/
├── knowledge-mcp/
│   ├── src/
│   │   ├── __init__.py
│   │   ├── server.py
│   │   ├── tools.py
│   │   └── resources.py
│   ├── pyproject.toml
│   └── README.md
```

#### Implementation
```python
# knowledge-mcp/src/server.py
from mcp.server import Server
from mcp.types import Tool, TextContent
import httpx

server = Server("knowledge-mcp")

KNOWLEDGE_ENGINE_URL = "http://localhost:8000"

@server.tool()
async def search_knowledge(query: str, top_k: int = 5) -> list[dict]:
    """Search the personal knowledge base.

    Args:
        query: The search query
        top_k: Number of results to return (default: 5)
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{KNOWLEDGE_ENGINE_URL}/api/search",
            params={"q": query, "top_k": top_k}
        )
        return response.json()

@server.tool()
async def ask_knowledge(question: str) -> str:
    """Ask a question and get an answer from the knowledge base.

    Args:
        question: The question to answer
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{KNOWLEDGE_ENGINE_URL}/api/qa",
            json={"question": question}
        )
        result = response.json()
        return result["answer"]

@server.tool()
async def ingest_url(url: str) -> dict:
    """Ingest a URL into the knowledge base.

    Args:
        url: The URL to ingest
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{KNOWLEDGE_ENGINE_URL}/api/ingest/url",
            json={"url": url}
        )
        return response.json()

@server.resource("knowledge://stats")
async def get_stats() -> str:
    """Get knowledge base statistics"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{KNOWLEDGE_ENGINE_URL}/api/stats")
        stats = response.json()
        return f"Documents: {stats['documents']}, Chunks: {stats['chunks']}"

# Entry point
if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server

    asyncio.run(stdio_server(server))
```

#### Claude Desktop Configuration
```json
// ~/.claude/claude_desktop_config.json
{
  "mcpServers": {
    "knowledge": {
      "command": "python",
      "args": ["-m", "knowledge_mcp.server"],
      "cwd": "/Users/d/claude-code/projects-2026/mcp-servers/knowledge-mcp"
    }
  }
}
```

### Server 2: Agent MCP

```python
# agent-mcp/src/server.py
from mcp.server import Server
from mcp.types import Tool
import httpx

server = Server("agent-mcp")

AGENT_PLATFORM_URL = "http://localhost:8001"

@server.tool()
async def run_task(
    task: str,
    context: str | None = None,
    wait: bool = True
) -> dict:
    """Execute a task using the agent platform.

    Args:
        task: The task to execute
        context: Optional context for the task
        wait: Whether to wait for completion (default: True)
    """
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(
            f"{AGENT_PLATFORM_URL}/api/tasks",
            json={"task": task, "context": context}
        )
        result = response.json()

        if wait:
            # Poll for completion
            task_id = result["task_id"]
            while True:
                status = await client.get(
                    f"{AGENT_PLATFORM_URL}/api/tasks/{task_id}"
                )
                status_data = status.json()
                if status_data["status"] in ["complete", "failed"]:
                    return status_data
                await asyncio.sleep(2)

        return result

@server.tool()
async def research(topic: str, depth: str = "normal") -> dict:
    """Run a research task on a topic.

    Args:
        topic: The topic to research
        depth: Research depth - "quick", "normal", or "deep"
    """
    async with httpx.AsyncClient(timeout=600) as client:
        response = await client.post(
            f"{AGENT_PLATFORM_URL}/api/research",
            json={"topic": topic, "depth": depth}
        )
        return response.json()

@server.tool()
async def list_tasks(status: str = "all") -> list[dict]:
    """List tasks from the agent platform.

    Args:
        status: Filter by status - "pending", "running", "complete", "failed", or "all"
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{AGENT_PLATFORM_URL}/api/tasks",
            params={"status": status}
        )
        return response.json()
```

### Server 3: MLX MCP

```python
# mlx-mcp/src/server.py
from mcp.server import Server
import httpx

server = Server("mlx-mcp")

OLLAMA_URL = "http://localhost:11434"

@server.tool()
async def generate(
    prompt: str,
    model: str = "deepseek-r1:14b",
    temperature: float = 0.7,
    max_tokens: int = 1024
) -> str:
    """Generate text using a local LLM.

    Args:
        prompt: The prompt to generate from
        model: Model to use (default: deepseek-r1:14b)
        temperature: Sampling temperature (default: 0.7)
        max_tokens: Maximum tokens to generate (default: 1024)
    """
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                },
                "stream": False
            }
        )
        return response.json()["response"]

@server.tool()
async def embed(texts: list[str], model: str = "nomic-embed-text") -> list[list[float]]:
    """Generate embeddings for texts.

    Args:
        texts: List of texts to embed
        model: Embedding model to use (default: nomic-embed-text)
    """
    async with httpx.AsyncClient() as client:
        embeddings = []
        for text in texts:
            response = await client.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": model, "prompt": text}
            )
            embeddings.append(response.json()["embedding"])
        return embeddings

@server.tool()
async def list_models() -> list[dict]:
    """List available local models."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{OLLAMA_URL}/api/tags")
        return response.json()["models"]

@server.tool()
async def chat(
    messages: list[dict],
    model: str = "deepseek-r1:14b",
    temperature: float = 0.7
) -> str:
    """Chat with a local LLM.

    Args:
        messages: Chat messages [{"role": "user", "content": "..."}]
        model: Model to use
        temperature: Sampling temperature
    """
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "options": {"temperature": temperature},
                "stream": False
            }
        )
        return response.json()["message"]["content"]
```

### Combined Configuration

```json
// ~/.claude/claude_desktop_config.json
{
  "mcpServers": {
    "knowledge": {
      "command": "python",
      "args": ["-m", "knowledge_mcp"],
      "cwd": "/Users/d/claude-code/projects-2026/mcp-servers/knowledge-mcp"
    },
    "agents": {
      "command": "python",
      "args": ["-m", "agent_mcp"],
      "cwd": "/Users/d/claude-code/projects-2026/mcp-servers/agent-mcp"
    },
    "mlx": {
      "command": "python",
      "args": ["-m", "mlx_mcp"],
      "cwd": "/Users/d/claude-code/projects-2026/mcp-servers/mlx-mcp"
    }
  }
}
```

---

## Usage Examples

### From Claude Code
```
User: "Search my knowledge base for RAG best practices"
Claude: [Uses knowledge-mcp search_knowledge tool]

User: "Research the latest MLX developments"
Claude: [Uses agent-mcp research tool]

User: "Generate a summary using my local model"
Claude: [Uses mlx-mcp generate tool]
```

---

## Testing

```python
# tests/test_knowledge_mcp.py
import pytest
from knowledge_mcp.server import server

@pytest.mark.asyncio
async def test_search_knowledge():
    result = await server.call_tool("search_knowledge", {
        "query": "test query",
        "top_k": 3
    })
    assert isinstance(result, list)

@pytest.mark.asyncio
async def test_ask_knowledge():
    result = await server.call_tool("ask_knowledge", {
        "question": "What is RAG?"
    })
    assert isinstance(result, str)
```

---

## Timeline

| Week | Task |
|------|------|
| Week 1 | knowledge-mcp implementation |
| Week 1 | agent-mcp implementation |
| Week 2 | mlx-mcp implementation |
| Week 2 | Testing & documentation |

**Total: 2 weeks**
