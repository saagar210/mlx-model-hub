# AI Command Center
## Unified Gateway + Monitoring Dashboard for All AI Infrastructure

---

## Project Overview

### What This Is
A single Go/Rust service that acts as the master router for all LLM requests on your machine, combined with a lightweight web dashboard showing real-time status. Every AI tool you run points to `localhost:4000` and the Command Center decides where each request actually goes.

### Current Status
**Phase**: Planning
**Priority**: Medium-High (foundational infrastructure)
**Estimated Effort**: 2-3 focused sessions for core, ongoing refinement

---

## Context & Motivation

### Your Current Situation
You're on the **Claude Max plan** with no API costs, so cost optimization isn't the primary driver. However, this project remains valuable for:

1. **Future-Proofing**: If you ever hit rate limits during intensive sessions, or want to experiment with other providers, the infrastructure is ready
2. **Local Model Integration**: Route simple queries to your local Qwen 2.5 14B for instant responses while reserving Claude for complex work
3. **Development Expansion**: As you build more AI-powered tools, having a unified gateway simplifies integration
4. **Privacy Routing**: Automatically route sensitive content to local models
5. **Visibility**: Even without cost concerns, seeing all AI traffic in one dashboard provides valuable insights

### Why This Matters
Every AI application you build (LocalCrew, Knowledge Engine, automations, future projects) needs LLM access. Currently, each configures its own connection. With the Command Center:
- Configure once, use everywhere
- Switch providers without touching application code
- See all AI activity in one place
- Add fallback logic for resilience

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AI COMMAND CENTER                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CONSUMERS                      ROUTER                    PROVIDERS          │
│  ─────────                      ──────                    ─────────          │
│                                                                              │
│  ┌─────────────┐           ┌──────────────┐          ┌─────────────────┐   │
│  │ Claude Code │──────────▶│              │─────────▶│ Claude API      │   │
│  └─────────────┘           │              │          │ (via ccflare)   │   │
│  ┌─────────────┐           │   LiteLLM    │          └─────────────────┘   │
│  │ OpenCode    │──────────▶│   PROXY      │          ┌─────────────────┐   │
│  └─────────────┘           │              │─────────▶│ Local MLX       │   │
│  ┌─────────────┐           │  • Routing   │          │ (unified-mlx)   │   │
│  │ LocalCrew   │──────────▶│  • Fallback  │          └─────────────────┘   │
│  └─────────────┘           │  • Logging   │          ┌─────────────────┐   │
│  ┌─────────────┐           │  • Metrics   │─────────▶│ Ollama          │   │
│  │ Automations │──────────▶│              │          │ (qwen, deepseek)│   │
│  └─────────────┘           └──────┬───────┘          └─────────────────┘   │
│  ┌─────────────┐                  │                  ┌─────────────────┐   │
│  │ Future Apps │──────────▶       │        ─────────▶│ OpenAI          │   │
│  └─────────────┘                  │                  │ (optional)      │   │
│                                   │                  └─────────────────┘   │
│                                   ▼                                         │
│                          ┌──────────────┐                                   │
│                          │  DASHBOARD   │                                   │
│                          │              │                                   │
│                          │ • Requests   │                                   │
│                          │ • Latency    │                                   │
│                          │ • Model Use  │                                   │
│                          │ • Errors     │                                   │
│                          │ • Routing    │                                   │
│                          └──────────────┘                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Technical Specification

### Core Technology
- **LiteLLM**: Python SDK and Proxy Server for 100+ LLM providers
- **Database**: SQLite for usage tracking and metrics
- **Dashboard**: LiteLLM's built-in UI or custom Next.js dashboard
- **Protocol**: OpenAI-compatible API at `localhost:4000/v1/`

### Why LiteLLM?
- Already supports all your providers (Anthropic, Ollama, local models)
- OpenAI-compatible API means drop-in replacement for any app
- Built-in usage tracking and logging
- Active development, 38k+ GitHub stars
- Self-hosted, all data stays local

### Provider Configuration

```yaml
# ~/.config/litellm/config.yaml

model_list:
  # Claude via Max plan
  - model_name: claude-sonnet
    litellm_params:
      model: anthropic/claude-sonnet-4-5-20250929
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: claude-opus
    litellm_params:
      model: anthropic/claude-opus-4-5-20251101
      api_key: os.environ/ANTHROPIC_API_KEY

  # Local models via Ollama
  - model_name: local-qwen
    litellm_params:
      model: ollama/qwen2.5:14b
      api_base: http://localhost:11434

  - model_name: local-deepseek
    litellm_params:
      model: ollama/deepseek-r1:14b
      api_base: http://localhost:11434

  - model_name: local-fast
    litellm_params:
      model: ollama/llama3.2:latest
      api_base: http://localhost:11434

  # Local embeddings
  - model_name: local-embed
    litellm_params:
      model: ollama/nomic-embed-text
      api_base: http://localhost:11434

# Routing configuration
router_settings:
  routing_strategy: simple-shuffle  # or latency-based, cost-based

  # Fallback chain
  fallbacks:
    - claude-sonnet: [local-qwen, local-fast]
    - claude-opus: [claude-sonnet, local-qwen]

general_settings:
  master_key: sk-command-center-local
  database_url: sqlite:///~/.config/litellm/usage.db
```

### Routing Rules (Future Enhancement)

```yaml
# Smart routing based on content and requirements
routing_rules:
  # Privacy-sensitive content stays local
  - match:
      contains: ["password", "secret", "private", "confidential", "personal"]
    route_to: local-qwen

  # Simple completions use fast local model
  - match:
      max_tokens: 500
      system_prompt_length: < 1000
    route_to: local-fast

  # Code generation uses Claude
  - match:
      contains: ["```", "function", "class", "def ", "const "]
    route_to: claude-sonnet

  # Complex reasoning uses Opus
  - match:
      system_prompt_contains: ["architect", "design", "plan"]
    route_to: claude-opus
```

---

## Implementation Plan

### Phase 1: Core Proxy Setup (Session 1)
**Goal**: Get LiteLLM running as a local proxy

```bash
# Install LiteLLM with proxy support
uv tool install "litellm[proxy]"

# Create config directory
mkdir -p ~/.config/litellm

# Create initial config (see above)
# Start proxy
litellm --config ~/.config/litellm/config.yaml --port 4000
```

**Validation**:
```bash
# Test the proxy
curl http://localhost:4000/v1/models

# Test a completion
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-command-center-local" \
  -H "Content-Type: application/json" \
  -d '{"model": "local-qwen", "messages": [{"role": "user", "content": "Hello"}]}'
```

### Phase 2: Provider Integration (Session 1-2)
**Goal**: Connect all your model providers

1. **Claude (Max Plan)**
   - Configure Anthropic API key
   - Test claude-sonnet and claude-opus models

2. **Ollama (Local)**
   - Verify Ollama is running on 11434
   - Test qwen2.5:14b, deepseek-r1:14b, llama3.2

3. **unified-mlx-app (Your MCP)**
   - Optional: Add as additional local provider
   - For MLX-optimized inference

### Phase 3: Dashboard Setup (Session 2)
**Goal**: Visual monitoring of all AI traffic

**Option A: LiteLLM Built-in UI**
```bash
# Access at http://localhost:4000/ui
# Shows: Models, Usage, Logs, Settings
```

**Option B: Custom Dashboard** (if you want more control)
```typescript
// dashboard/pages/index.tsx
import { useQuery } from 'react-query';

export default function Dashboard() {
  const { data: stats } = useQuery('stats', async () => {
    const res = await fetch('/api/stats');
    return res.json();
  });

  return (
    <div className="grid grid-cols-3 gap-4">
      <StatCard title="Requests Today" value={stats?.requests} />
      <StatCard title="Avg Latency" value={`${stats?.avgLatency}ms`} />
      <StatCard title="Models Used" value={stats?.modelBreakdown} />
    </div>
  );
}
```

### Phase 4: Application Integration (Session 3)
**Goal**: Point your tools at the Command Center

```bash
# For Claude Code (when using API mode)
export ANTHROPIC_BASE_URL="http://localhost:4000"

# For OpenCode
export OPENAI_BASE_URL="http://localhost:4000"
export OPENAI_API_KEY="sk-command-center-local"

# For LocalCrew - update config
# litellm_api_base: http://localhost:4000

# For Python applications
import openai
client = openai.OpenAI(
    base_url="http://localhost:4000/v1",
    api_key="sk-command-center-local"
)
```

### Phase 5: Systemd/Launchd Service (Session 3)
**Goal**: Auto-start on boot

```xml
<!-- ~/Library/LaunchAgents/com.aicommandcenter.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.aicommandcenter</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/d/.local/bin/litellm</string>
        <string>--config</string>
        <string>/Users/d/.config/litellm/config.yaml</string>
        <string>--port</string>
        <string>4000</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

---

## Integration Points

### With Other Projects
| Project | Integration |
|---------|-------------|
| **Personal Context Layer** (Project 2) | MCP servers can use Command Center for LLM calls |
| **Autonomous Automation** (Project 3) | n8n workflows call Command Center |
| **Visual Knowledge Platform** (Project 4) | Dify uses Command Center as model provider |
| **Self-Improving Agents** (Project 6) | DSPy optimization calls through Command Center |
| **AI Operations Dashboard** (Project 8) | Langfuse traces Command Center requests |
| **Universal Context Engine** (Project 9) | Context formatting LLM calls via Command Center |
| **AI-Native Dev Environment** (Project 10) | All coding tools use Command Center |

### With Existing Infrastructure
- **ccflare**: Can be upstream provider for Claude if you want additional load balancing
- **unified-mlx-app**: Alternative local inference backend
- **Ollama**: Primary local model provider

---

## Builds On Existing

| Component | Location | Status |
|-----------|----------|--------|
| ccflare | ~/claude-code/ai-tools/ccflare | Cloned, working |
| unified-mlx-app | MCP server | Configured, active |
| Ollama | brew install | Running, models loaded |
| LiteLLM | To be installed | - |

---

## Success Criteria

1. **Functional**: All requests from any tool successfully route through Command Center
2. **Reliable**: 99%+ uptime with automatic restarts
3. **Observable**: Dashboard shows all traffic with <1 minute delay
4. **Flexible**: Can add new providers or routing rules without code changes
5. **Integrated**: At least 3 applications using Command Center

---

## Future Enhancements

- [ ] Smart routing based on content analysis
- [ ] Request caching for repeated queries
- [ ] Prompt injection detection
- [ ] Cost tracking (when API usage resumes)
- [ ] Multi-user support (if ever needed)
- [ ] Rate limiting for local models
- [ ] A/B testing different models

---

## Resources

- [LiteLLM Documentation](https://docs.litellm.ai/)
- [LiteLLM GitHub](https://github.com/BerriAI/litellm)
- [Claude Code LLM Gateway Docs](https://code.claude.com/docs/en/llm-gateway)
- [LiteLLM + Claude Code Tutorial](https://medium.com/@niklas-palm/claude-code-with-litellm-24b3fb115911)
