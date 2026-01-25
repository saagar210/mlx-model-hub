# AI Command Center

A local LLM gateway for macOS that provides OpenAI-compatible API access to Ollama models with smart routing, observability, and caching.

## Features

- **Smart Routing**: Content-aware routing based on privacy, complexity, and injection detection
- **Local-First**: Sensitive content never leaves your machine
- **Observability**: Full tracing via Langfuse
- **Caching**: Redis-backed exact and semantic caching
- **High Availability**: Circuit breakers and fallback chains

## Architecture

```
Consumers (LocalCrew, n8n, Dify, Scripts)
              │
              ▼
    Smart Router (:4000)
    - Privacy detection
    - Complexity classification
    - Injection detection
              │
              ▼
    LiteLLM Proxy (:4001)
    - Provider routing
    - Retries & fallbacks
    - Caching
              │
              ▼
    Ollama (:11434)
    - qwen2.5:14b
    - deepseek-r1:14b
    - llama3.2
```

## Quick Start

### Prerequisites

- macOS with Apple Silicon
- Ollama installed and running
- Redis (via Homebrew)
- Docker (for Langfuse)
- Python 3.12+

### Installation

1. **Start Langfuse** (observability):
   ```bash
   cd ~/.config/ai-command-center
   docker compose up -d
   ```

2. **Start LiteLLM** (proxy):
   ```bash
   ~/.config/ai-command-center/start_litellm.sh &
   ```

3. **Start Smart Router** (gateway):
   ```bash
   ~/.config/ai-command-center/start_router.sh &
   ```

### Usage

```bash
# Chat completion
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-command-center-local" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-local",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Health Check

```bash
curl http://localhost:4000/health
```

## Configuration

Configuration files are in `~/.config/ai-command-center/`:

| File | Purpose |
|------|---------|
| `.env` | Environment variables |
| `config.yaml` | LiteLLM model configuration |
| `docker-compose.yml` | Langfuse stack |
| `routing/policy.yaml` | Routing rules |

## Available Models

| Model | Alias | Best For |
|-------|-------|----------|
| llama3.2 | `llama-fast` | Quick responses, simple tasks |
| qwen2.5:14b | `qwen-local` | General tasks, medium complexity |
| deepseek-r1:14b | `deepseek-local` | Complex reasoning, code |

## Routing Behavior

The Smart Router automatically selects models based on content:

1. **Privacy**: Sensitive content (passwords, API keys, PII) → `llama-fast`
2. **Complexity**: Reasoning tasks → `deepseek-local`
3. **Injection**: Potential attacks are flagged and routed safely

## Documentation

- [Implementation Plan](IMPLEMENTATION_PLAN.md) - Full technical details
- [Integration Guide](~/.config/ai-command-center/integrations/README.md) - How to connect tools
- [Operations Runbook](~/.config/ai-command-center/operations/runbook.md) - Maintenance procedures

## Testing

```bash
# Unit tests
python -m pytest tests/test_routing.py -v

# Integration tests (requires running services)
python -m pytest tests/test_integration.py -v
```

## License

MIT
