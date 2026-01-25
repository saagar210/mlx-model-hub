# AI Command Center - Implementation Plan

> **Status:** Updated After Review
> **Created:** 2026-01-25
> **Updated:** 2026-01-25
> **Version:** 2.0
> **Authors:** Claude (Opus 4.5), Codex (review)

---

## Executive Summary

AI Command Center is a local LLM gateway for your Mac that offers OpenAI-compatible access to local Ollama models with smart routing, observability, and caching. It is the shared entry point for LocalCrew, n8n, Dify, and future apps, while Claude Code remains direct to Claude Max and does not traverse this system.

**Key Design Decisions:**
1. Local-first routing: sensitive data never leaves the machine
2. Two-layer gateway: Smart Router (content-aware) in front of LiteLLM (provider-aware)
3. Observability by default: all requests traced to Langfuse with redaction
4. Redis-backed caching with graceful degradation
5. macOS-native runtime: LaunchAgents for always-on services

---

## Goals, Non-Goals, and Constraints

**Goals**
- Provide a stable OpenAI-compatible endpoint at `http://localhost:4000`
- Route requests based on privacy, complexity, and availability
- Capture traces, latency, and routing decisions in Langfuse
- Improve latency for repeat requests via caching

**Non-Goals**
- Routing Claude Code through this gateway
- Multi-tenant authentication or billing
- Cloud-hosted providers in the initial release

**Constraints**
- Must run locally on macOS
- Ollama and Redis already running
- Docker installed, but not always running

---

## Current Environment

### Verified Components

| Component | Status | Details |
|-----------|--------|---------|
| LiteLLM | ✅ Installed | `/Users/d/.local/share/mise/installs/python/3.12.12/bin/litellm` |
| Ollama | ✅ Running | qwen2.5:14b, deepseek-r1:14b, llama3.2, nomic-embed-text, bge-reranker |
| Docker | ✅ Installed | v29.1.3 (not currently running) |
| Redis | ✅ Running | Homebrew service |
| PostgreSQL | ❌ Not installed | Will use Docker for Langfuse only |

### Hardware

- MacBook Pro M4 Pro (48GB RAM)
- Sufficient for running multiple 14B parameter models concurrently

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           AI COMMAND CENTER                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CONSUMERS (OpenAI-compatible API at localhost:4000)                         │
│  ─────────────────────────────────────────────────────                       │
│  LocalCrew │ n8n Workflows │ Dify │ Python Scripts │ Future Apps              │
│                                                                              │
│  NOTE: Claude Code stays direct (Claude Max) - NOT routed through here       │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                 SMART ROUTER (FastAPI, localhost:4000)                   │ │
│  │                                                                         │ │
│  │  • Privacy detection + redaction                                        │ │
│  │  • Complexity classification                                            │ │
│  │  • Injection detection (flag/block)                                     │ │
│  │  • Semantic cache (Redis)                                               │ │
│  └──────────────────────────────┬──────────────────────────────────────────┘ │
│                                 │                                              │
│  ┌──────────────────────────────┴──────────────────────────────────────────┐ │
│  │                    LiteLLM PROXY (localhost:4001)                       │ │
│  │                                                                         │ │
│  │  • Provider routing + retries                                           │ │
│  │  • Exact cache (Redis)                                                  │ │
│  │  • Request logging -> Langfuse                                          │ │
│  └──────────────────────────────┬──────────────────────────────────────────┘ │
│                                 │                                              │
│  ┌──────────────────────────────┴──────────────────────────────────────────┐ │
│  │                          LOCAL PROVIDERS                                 │
│  │                                                                          │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │
│  │  │  Ollama :11434   │  │   MLX (optional) │  │   OpenAI (opt)   │        │
│  │  │                  │  │                  │  │                  │        │
│  │  │  qwen2.5:14b     │  │  unified-mlx-app │  │  Future use      │        │
│  │  │  deepseek-r1:14b │  │  (if HTTP API)   │  │                  │        │
│  │  │  llama3.2        │  │                  │  │                  │        │
│  │  │  nomic-embed-text│  │                  │  │                  │        │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘        │
│  └──────────────────────────────────────────────────────────────────────────┘
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                    OBSERVABILITY (Langfuse in Docker)                   │ │
│  │                                                                         │ │
│  │  Traces │ Token Usage │ Latency │ Routing Decisions │ Prompt Versions   │ │
│  │                                                                         │ │
│  │  Dashboard: http://localhost:3001                                       │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                          INFRASTRUCTURE                                 │ │
│  │                                                                         │
│  │  Redis (Homebrew) │ PostgreSQL (Docker) │ SQLite (usage backup)          │
│  └─────────────────────────────────────────────────────────────────────────┘
└──────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. Consumer sends request to `localhost:4000/v1/chat/completions`
2. Smart Router evaluates privacy, complexity, and injection signals
3. Router forwards to LiteLLM on `localhost:4001` with selected model
4. LiteLLM handles retries, fallbacks, and exact cache
5. Langfuse receives traces (redacted where required)
6. Response returned to consumer

---

## Technology Stack

### Core Components

| Component | Purpose | Port | Notes |
|-----------|---------|------|-------|
| Smart Router (FastAPI) | Content-aware routing | 4000 | OpenAI-compatible facade |
| LiteLLM Proxy | Provider routing, retries, cache | 4001 | Internal-only localhost |
| Langfuse | Observability, tracing | 3001 | Self-hosted in Docker |
| Redis | Caching, session state | 6379 | Homebrew service |
| PostgreSQL | Langfuse database | 5432 | Docker only |
| TensorZero | Optional fast path | 8000 | Optional later phase |

### Optional/Supporting Libraries

- `fastapi`, `uvicorn`, `httpx`, `pydantic` for the Smart Router
- `redis` for semantic cache index
- `python-dotenv` for `.env` loading

---

## Implementation Phases

### Phase 1: Scaffolding and Secrets
**Goal:** Establish directories, environment file, and local secrets handling

**Deliverables:**
- `~/.config/ai-command-center/.env`
- `~/.config/ai-command-center/` directory structure

**Validation:**
- `.env` exists and is loaded by start scripts
- `mkdir -p ~/.config/ai-command-center/{logs,routing,caching,security,monitoring,resilience,integrations,experimentation}`

---

### Phase 2: LiteLLM Proxy Baseline
**Goal:** Run LiteLLM on localhost:4001 with Ollama models

**Deliverables:**
- `~/.config/ai-command-center/config.yaml`
- `~/.config/ai-command-center/start_litellm.sh`

**Validation:**
```bash
litellm --config ~/.config/ai-command-center/config.yaml --port 4001
curl http://localhost:4001/health
curl http://localhost:4001/v1/chat/completions \
  -H "Authorization: Bearer $AICC_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen-local", "messages": [{"role": "user", "content": "Hello"}]}'
```

---

### Phase 3: Langfuse Stack
**Goal:** Deploy Langfuse + PostgreSQL with Docker and create API keys

**Deliverables:**
- `~/.config/ai-command-center/docker-compose.yml`
- Langfuse project + API keys

**Validation:**
- `docker compose up -d`
- Dashboard accessible at `http://localhost:3001`

---

### Phase 4: Observability Wiring
**Goal:** Connect LiteLLM to Langfuse and enable redaction

**Deliverables:**
- `.env` additions: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`
- Router redaction policy

**Validation:**
- Run a request through LiteLLM and confirm a trace appears in Langfuse
- Verify redaction on sensitive fields in traces

---

### Phase 5: Smart Router (Privacy + Complexity + Injection)
**Goal:** Implement content-aware routing and protection logic

**Deliverables:**
- `~/.config/ai-command-center/routing/smart_router.py`
- `~/.config/ai-command-center/routing/privacy_router.py`
- `~/.config/ai-command-center/routing/complexity_router.py`
- `~/.config/ai-command-center/security/injection_detector.py`
- `~/.config/ai-command-center/routing/policy.yaml`

**Validation:**
- Requests with secrets route to `llama-fast`
- Complex prompts route to `deepseek-local`
- Injection attempts are flagged or blocked based on policy

---

### Phase 6: Caching (Exact + Semantic)
**Goal:** Reduce repeat latency using Redis-backed caching

**Deliverables:**
- LiteLLM exact cache enabled (Redis)
- `~/.config/ai-command-center/caching/semantic_cache.py`

**Validation:**
- Same request returns cached response within 50ms
- Semantic cache hit for paraphrased prompts above similarity threshold

---

### Phase 7: Integration Layer
**Goal:** Point LocalCrew, n8n, and Dify to the gateway

**Deliverables:**
- `~/.config/ai-command-center/integrations/README.md`
- Example configs for LocalCrew, n8n, Dify

**Validation:**
- Each tool completes a request through `http://localhost:4000`

---

### Phase 8: Resilience and Rate Limits
**Goal:** Add circuit breakers, retries, and concurrency limits

**Deliverables:**
- `~/.config/ai-command-center/resilience/circuit_breaker.py`
- `~/.config/ai-command-center/monitoring/health_check.py`

**Validation:**
- Simulated Ollama failure triggers fallback within 2 retries
- Health endpoint returns status for Redis, Ollama, LiteLLM, Langfuse

---

### Phase 9: Experimentation Framework
**Goal:** Enable A/B prompt testing for safe changes

**Deliverables:**
- `~/.config/ai-command-center/experimentation/ab_test.py`

**Validation:**
- Deterministic variant assignment by user_id
- Langfuse tags per variant

---

### Phase 10: Operations Runbook
**Goal:** Define backup, recovery, scaling, and retention procedures

**Deliverables:**
- `~/.config/ai-command-center/operations/runbook.md`
- `~/.config/ai-command-center/monitoring/alerts.py`

**Validation:**
- Backup process documented for Postgres and config
- Log rotation configured

---

### Phase 11: LaunchAgents Deployment
**Goal:** Auto-start Smart Router and LiteLLM on boot

**Deliverables:**
- `~/Library/LaunchAgents/com.aicommandcenter.router.plist`
- `~/Library/LaunchAgents/com.aicommandcenter.litellm.plist`

**Validation:**
- `launchctl load` starts both services
- Logs written to `~/.config/ai-command-center/logs/`

---

### Phase 12: Testing and Optional TensorZero
**Goal:** Validate end-to-end behavior and add fast path if needed

**Deliverables:**
- `tests/` suite with routing, caching, and integrations
- Optional `tensorzero.toml` + routing hook

**Validation:**
- `pytest` passes core tests
- Optional TensorZero endpoint responds on `:8000`

---

## Configuration Reference

### Environment File (`.env`)

```
AICC_MASTER_KEY=sk-command-center-local
AICC_LITELLM_PORT=4001
AICC_ROUTER_PORT=4000
LANGFUSE_HOST=http://localhost:3001
LANGFUSE_PUBLIC_KEY=lf_pk_...
LANGFUSE_SECRET_KEY=lf_sk_...
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
OLLAMA_BASE_URL=http://localhost:11434
```

### LiteLLM Config (`config.yaml`)

```yaml
model_list:
  - model_name: qwen-local
    litellm_params:
      model: ollama/qwen2.5:14b
      api_base: ${OLLAMA_BASE_URL}
  - model_name: deepseek-local
    litellm_params:
      model: ollama/deepseek-r1:14b
      api_base: ${OLLAMA_BASE_URL}
  - model_name: llama-fast
    litellm_params:
      model: ollama/llama3.2:latest
      api_base: ${OLLAMA_BASE_URL}
  - model_name: embed-local
    litellm_params:
      model: ollama/nomic-embed-text
      api_base: ${OLLAMA_BASE_URL}
  - model_name: rerank-local
    litellm_params:
      model: ollama/bge-reranker-v2-m3
      api_base: ${OLLAMA_BASE_URL}

litellm_settings:
  cache: true
  cache_params:
    type: redis
    host: ${REDIS_HOST}
    port: ${REDIS_PORT}
    ttl: 3600
    namespace: aicc
  callbacks: ["langfuse"]

router_settings:
  num_retries: 2
  timeout: 120
  fallbacks:
    - qwen-local: [deepseek-local, llama-fast]
    - deepseek-local: [qwen-local, llama-fast]

general_settings:
  master_key: ${AICC_MASTER_KEY}
  database_url: sqlite:////Users/d/.config/ai-command-center/usage.db
```

### Smart Router Policy (`routing/policy.yaml`)

```yaml
privacy:
  pii_regexes:
    - (?i)\\b\"?ssn\"?\\b
    - (?i)password
    - (?i)api[_-]?key
    - (?i)secret
    - (?i)private[_-]?key
  entropy_threshold: 3.5
  min_token_length: 24

complexity:
  simple_max_tokens: 256
  medium_max_tokens: 1024
  code_signals: ["```", "def ", "class ", "function ", "const "]
  reasoning_signals: ["why", "prove", "derive", "design", "tradeoff"]

routing:
  privacy_route: llama-fast
  simple_route: llama-fast
  medium_route: qwen-local
  complex_route: deepseek-local
  injection_route: llama-fast
  block_on_injection: false
```

### Smart Router Start Script (`start_router.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail
source "${HOME}/.config/ai-command-center/.env"
uvicorn routing.smart_router:app --host 127.0.0.1 --port "${AICC_ROUTER_PORT}" --workers 1
```

### Docker Compose (`docker-compose.yml`)

```yaml
version: '3.8'
services:
  langfuse-server:
    image: langfuse/langfuse:latest
    depends_on:
      langfuse-db:
        condition: service_healthy
    ports:
      - "3001:3000"
    environment:
      DATABASE_URL: postgresql://langfuse:langfuse@langfuse-db:5432/langfuse
      NEXTAUTH_URL: http://localhost:3001
      NEXTAUTH_SECRET: ${LANGFUSE_NEXTAUTH_SECRET}
      SALT: ${LANGFUSE_SALT}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "-", "http://localhost:3000/api/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  langfuse-db:
    image: postgres:15
    environment:
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: langfuse
      POSTGRES_DB: langfuse
    volumes:
      - langfuse-db:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U langfuse"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  langfuse-db:
```

### LaunchAgents (`com.aicommandcenter.*.plist`)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.aicommandcenter.router</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>${HOME}/.config/ai-command-center/start_router.sh</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${HOME}/.config/ai-command-center/logs/router.out.log</string>
  <key>StandardErrorPath</key>
  <string>${HOME}/.config/ai-command-center/logs/router.err.log</string>
</dict>
</plist>
```

---

## Observability and Monitoring

- Langfuse traces every request with routing metadata (model, route reason, cache hit)
- Router writes structured logs to `~/.config/ai-command-center/logs/`
- Health checks validate Ollama, Redis, LiteLLM, and Langfuse
- Alerts trigger for error rate > 5%, p95 latency > 10s, or cache hit rate < 5%
- Retention target: 14-30 days of Langfuse traces, rotate logs weekly

---

## Operational Procedures

### Backup
- Postgres: `pg_dump` from `langfuse-db` container to `~/.config/ai-command-center/backups/langfuse/`
- Config: tarball of `~/.config/ai-command-center/`
- Redis: optional snapshot (cache can be rebuilt)

### Recovery
- Restore Postgres dump into container
- Recreate `.env` and config files
- Restart LaunchAgents

### Scaling
- Set `OLLAMA_MAX_LOADED_MODELS` and `OLLAMA_NUM_PARALLEL` to manage memory
- Limit concurrent requests in LiteLLM and Router
- Prefer `llama-fast` for high QPS or low-latency tasks

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Availability | 99%+ local uptime | LaunchAgent + health checks |
| Router Overhead (p95) | <30ms | Router logs + Langfuse |
| LiteLLM Overhead (p95) | <50ms | Langfuse traces |
| Trace Coverage | 95%+ of requests | Langfuse dashboard |
| Cache Hit Rate | 15-35% (steady state) | Redis stats |
| Injection Flag Accuracy | >90% known-pattern recall | Security tests |
| Integration Coverage | 3+ consumers | LocalCrew, n8n, Dify |

---

## Risk Assessment

### High Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Smart routing not enforced (content-based routing missing) | Privacy leakage | Put Smart Router in front of LiteLLM and block bypass |
| Langfuse unavailable | Loss of traces, slowdowns | Non-blocking logging and retries |
| Secrets/logs leak to traces | Compliance risk | Redaction + allowlist logging fields |

### Medium Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Docker not running | No observability | Health checks + manual restart steps |
| Memory exhaustion from multiple 14B models | Slow responses or crashes | Limit parallelism, prefer llama-fast |
| Redis down | Cache disabled | Graceful bypass with metrics |
| Model name mismatch | Requests fail | Validation script to list models |

### Low Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Port conflicts | Service fails to bind | Configurable ports |
| Log file growth | Disk pressure | Log rotation |
| SQLite contention | Metrics write delay | Reduce write frequency |

---

## Failure Modes and Edge Cases

- Streaming responses must pass through without buffering
- Tool/function calling in OpenAI format must preserve JSON schema
- Extremely long prompts may exceed model context limits
- Ollama cold start can add 10-30s latency
- Redis eviction can reduce cache hit rate
- Docker updates can reset Langfuse containers

---

## Future Extensions

1. Claude API routing (if programmatic access needed)
2. OpenRouter/OpenAI fallback providers
3. DSPy optimization from Langfuse traces
4. Prometheus + Grafana metrics
5. Multi-tenant isolation

---

## Open Questions

1. Should injection detection block by default or only log and route locally?
2. Is semantic caching worth the added complexity, or should we start with exact cache only?
3. Should we expose the router on localhost only, or allow LAN for other devices?

---

## File Structure Summary

```
~/.config/ai-command-center/
├── .env
├── config.yaml
├── docker-compose.yml
├── start_litellm.sh
├── start_router.sh
├── logs/
│   ├── router.out.log
│   └── router.err.log
├── routing/
│   ├── policy.yaml
│   ├── privacy_router.py
│   ├── complexity_router.py
│   └── smart_router.py
├── caching/
│   └── semantic_cache.py
├── security/
│   └── injection_detector.py
├── resilience/
│   └── circuit_breaker.py
├── monitoring/
│   ├── health_check.py
│   └── alerts.py
├── integrations/
│   └── README.md
└── experimentation/
    └── ab_test.py

~/Library/LaunchAgents/
├── com.aicommandcenter.router.plist
└── com.aicommandcenter.litellm.plist

tests/
├── test_routing.py
├── test_integration.py
├── test_langfuse.py
├── test_caching.py
├── test_security.py
└── load_test.py
```

---

## Approval Checklist

Before implementation begins, please confirm:

- [ ] Architecture is sound and addresses all requirements
- [ ] Phase ordering is logical (dependencies respected)
- [ ] Technology choices are appropriate
- [ ] Success metrics are realistic and measurable
- [ ] Risks are adequately identified and mitigated
- [ ] Open questions have been resolved or deferred appropriately

---

*Plan updated by Codex review on 2026-01-25*
