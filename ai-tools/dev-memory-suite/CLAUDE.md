# Developer Memory & Context Suite

## Project Overview
A suite of 3 interconnected tools that capture, organize, and surface your development knowledge. Built on top of your existing Knowledge Activation System, creating a powerful developer-specific knowledge layer.

## The Suite
1. **DevMemory** - Personal developer knowledge graph (Weeks 1-3)
2. **CodeMCP** - MCP server for codebase understanding (Weeks 4-5)
3. **ContextLens** - Smart context window manager (Weeks 6-7)

## Why This Stack
- Every developer needs this (huge market)
- Leverages your Knowledge Activation System (70% done)
- Each tool feeds data to the others
- Solves YOUR daily problems
- Natural fit with Claude Code usage

## Tech Stack
- **DevMemory**: Python + FastAPI + PostgreSQL + pgvector (extends Knowledge System)
- **CodeMCP**: Python + MCP SDK + AST parsing
- **ContextLens**: Python + Claude API integration

## Prerequisites (Already Installed)
- Knowledge Activation System (PostgreSQL + pgvector + hybrid search)
- LlamaIndex, Instructor, DSPy
- Ollama models (deepseek-r1, qwen2.5-coder, nomic-embed-text)
- MCP servers in ~/.claude.json

## Success Metrics
- DevMemory: "Find that fix from last month" works 90% of the time
- CodeMCP: Claude Code can semantically query any repo
- ContextLens: 40%+ context token savings

## Commands
```bash
# Development
cd /Users/d/claude-code/ai-tools/dev-memory-suite

# Run DevMemory
python -m devmemory serve

# Test CodeMCP
mcp-inspector codemcp

# Run tests
pytest
```

## Related Projects
- `/Users/d/claude-code/personal/knowledge-activation-system/` - Foundation
- MCP servers in `~/.claude.json` (postgres, memory)
