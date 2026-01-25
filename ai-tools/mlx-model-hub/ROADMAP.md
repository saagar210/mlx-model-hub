# MLX Model Hub - Development Roadmap

**Last Updated:** 2026-01-12
**Current Version:** 0.1.0 (Development)
**Target Version:** 1.0.0 (Production)

---

## Vision

MLX Model Hub becomes the **central nervous system** for local AI on Apple Silicon - a production-grade platform that manages, trains, and serves LLMs while integrating seamlessly with your entire local AI ecosystem.

---

## Current State

| Component | Status | Notes |
|-----------|--------|-------|
| Backend API | 80% | Model registry, training, datasets |
| Inference Server | 100% | OpenAI-compatible, KV cache |
| Frontend Dashboard | 80% | All major features |
| Security | 20% | **CRITICAL GAP** - Auth disabled |
| Testing | 57% | Backend only, no E2E |
| Documentation | 80% | Good but fragmented |

---

## Roadmap Overview

```
Q1 2026
├─ Week 1-2:  Security Hardening (CRITICAL)
├─ Week 2-4:  Testing & Quality
├─ Week 4-6:  Integration Layer
├─ Week 6-8:  Developer Experience
└─ Week 8-12: Advanced Features

Q2 2026
├─ Multi-node inference
├─ Model marketplace
└─ Enterprise features
```

---

## Phase 1: Security Hardening
**Timeline:** 1-2 days | **Priority:** CRITICAL

### Tasks

- [ ] **Enable Authentication by Default**
  ```python
  # config.py
  require_auth: bool = True
  api_key: str = Field(..., env="API_KEY")
  ```

- [ ] **Register Auth Middleware**
  ```python
  # main.py
  from mlx_hub.security import APIKeyAuthMiddleware
  app.add_middleware(APIKeyAuthMiddleware)
  ```

- [ ] **Restrict CORS**
  ```python
  allow_origins=["http://localhost:3005", "http://127.0.0.1:3005"]
  allow_methods=["GET", "POST", "DELETE", "OPTIONS"]
  ```

- [ ] **Require Strong Passwords**
  ```yaml
  # docker-compose.yml
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Required}
  GRAFANA_PASSWORD: ${GRAFANA_PASSWORD:?Required}
  ```

- [ ] **Add Rate Limiting**
  ```bash
  pip install slowapi
  ```

### Success Criteria
- [ ] All endpoints require API key
- [ ] CORS restricted to frontend origin
- [ ] No default passwords in docker-compose
- [ ] Rate limiting on admin endpoints

---

## Phase 2: Testing & Quality
**Timeline:** 1-2 weeks | **Priority:** HIGH

### Tasks

- [ ] **E2E Tests with Playwright**
  - Model list/create/delete flow
  - Training job lifecycle
  - Inference chat completion
  - Dashboard navigation
  - Error handling scenarios

- [ ] **Security Tests**
  - SQL injection attempts
  - Auth bypass attempts
  - Rate limit enforcement
  - Path traversal protection

- [ ] **Pre-commit Hooks**
  ```yaml
  # .pre-commit-config.yaml
  repos:
    - repo: https://github.com/zricethezav/gitleaks
    - repo: https://github.com/psf/black
    - repo: https://github.com/astral-sh/ruff-pre-commit
    - repo: https://github.com/pre-commit/mirrors-mypy
  ```

- [ ] **CI/CD Pipeline**
  - GitHub Actions workflow
  - Run tests on PR
  - Build Docker images
  - Deploy to staging

### Success Criteria
- [ ] 80%+ test coverage
- [ ] All PRs must pass CI
- [ ] Pre-commit hooks enforced
- [ ] E2E tests for critical paths

---

## Phase 3: Integration Layer
**Timeline:** 2-4 weeks | **Priority:** HIGH

### Tasks

#### LocalCrew Integration
Connect agent workflows to MLX inference

```python
# In LocalCrew, use MLX Hub inference
from openai import OpenAI

mlx_client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key=os.environ["MLX_HUB_API_KEY"]
)

# Agents automatically benefit from prompt caching
response = mlx_client.chat.completions.create(
    model="mlx-community/Qwen2.5-7B-Instruct-4bit",
    messages=messages
)
```

#### KAS Integration
Augment training data with knowledge retrieval

```python
# Query KAS for relevant context
context = await kas_client.search(training_example)

# Augment training data
augmented_example = {
    "instruction": example["instruction"],
    "context": context,
    "response": example["response"]
}
```

#### ccflare Fallback
Route to Claude API when local fails

```python
# Configure ccflare to proxy MLX Hub
# with Claude API fallback
BACKENDS = [
    {"url": "http://localhost:8080", "priority": 1},  # Local MLX
    {"url": "https://api.anthropic.com", "priority": 2}  # Claude fallback
]
```

#### Unified Observability
Single Grafana dashboard for all services

```yaml
# prometheus.yml - scrape all services
scrape_configs:
  - job_name: 'mlx-hub-backend'
    static_configs:
      - targets: ['localhost:8002']
  - job_name: 'mlx-hub-inference'
    static_configs:
      - targets: ['localhost:8080']
  - job_name: 'localcrew'
    static_configs:
      - targets: ['localhost:8001']
  - job_name: 'kas'
    static_configs:
      - targets: ['localhost:8003']
```

### Success Criteria
- [ ] LocalCrew uses MLX Hub for inference
- [ ] KAS integrated with training pipeline
- [ ] ccflare fallback configured
- [ ] Single observability dashboard

---

## Phase 4: Developer Experience
**Timeline:** 2-3 weeks | **Priority:** MEDIUM

### Tasks

- [ ] **CLI Tool (`mlx-hub`)**
  ```bash
  # Model management
  mlx-hub models list
  mlx-hub models download mlx-community/Qwen2.5-7B-Instruct-4bit

  # Training
  mlx-hub train --model qwen --dataset mydata.jsonl --epochs 3

  # Inference
  mlx-hub chat --model qwen

  # Cache management
  mlx-hub cache warmup --system-prompt "You are a helpful assistant"
  mlx-hub cache stats
  ```

- [ ] **Model Benchmark Suite**
  ```bash
  mlx-hub benchmark --model qwen --prompts benchmark_prompts.json
  # Output: TTFT, throughput, memory usage, latency percentiles
  ```

- [ ] **Documentation Consolidation**
  - Merge plan files into single ROADMAP.md
  - Create architecture diagram
  - Add troubleshooting guide
  - Video walkthrough

- [ ] **Quick Start Scripts**
  ```bash
  # One-liner setup
  curl -fsSL https://raw.githubusercontent.com/user/mlx-model-hub/main/install.sh | bash
  ```

### Success Criteria
- [ ] CLI tool published to PyPI
- [ ] Benchmark suite for performance tracking
- [ ] Single documentation source
- [ ] <5 minute setup for new users

---

## Phase 5: Advanced Features
**Timeline:** 1-2 months | **Priority:** LOW

### Tasks

- [ ] **MLXCache Integration**
  - Shared model weight cache across projects
  - Reduce disk space by 40%+
  - Faster model switching

- [ ] **StreamMind Vision Integration**
  - Screen capture analysis via MLX Hub
  - Error diagnosis from screenshots
  - UI testing automation

- [ ] **Multi-node Inference (Experimental)**
  - Distribute large models across devices
  - Parallel prompt processing
  - Automatic load balancing

- [ ] **Model Marketplace**
  - Browse community fine-tuned models
  - One-click download and deploy
  - Rating and reviews

- [ ] **Training Templates Library**
  - Pre-configured LoRA settings
  - Task-specific templates (chat, code, etc.)
  - Best practices baked in

### Success Criteria
- [ ] Shared cache operational
- [ ] Vision analysis working
- [ ] Documentation for advanced features

---

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Your Local AI Ecosystem                     │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   LocalCrew   │    │     KAS       │    │  StreamMind   │
│ (Agent Tasks) │    │ (Knowledge)   │    │  (Vision)     │
└───────┬───────┘    └───────┬───────┘    └───────┬───────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                             ▼
              ┌──────────────────────────┐
              │      MLX Model Hub       │
              │  ┌────────────────────┐  │
              │  │ Inference Server   │  │
              │  │ + KV Cache         │  │
              │  │ + Model Registry   │  │
              │  │ + Training         │  │
              │  └────────────────────┘  │
              └────────────┬─────────────┘
                           │
                           ▼
              ┌──────────────────────────┐
              │     Apple Silicon GPU    │
              │   (M1/M2/M3/M4 + MLX)   │
              └──────────────────────────┘
                           │
                           │ Fallback
                           ▼
              ┌──────────────────────────┐
              │   ccflare → Claude API   │
              │   (Cloud Backup)         │
              └──────────────────────────┘
```

---

## Resource Requirements

### Development Time
| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Security | 1-2 days | None |
| Testing | 1-2 weeks | Security complete |
| Integration | 2-4 weeks | Security complete |
| DX | 2-3 weeks | Integration started |
| Advanced | 1-2 months | All prior phases |

### Infrastructure
- **Database:** PostgreSQL 16 (existing)
- **Cache:** Consider Redis for rate limiting
- **Observability:** Prometheus + Grafana (existing)
- **CI/CD:** GitHub Actions (new)

### Skills Needed
- Python/FastAPI (backend)
- TypeScript/Next.js (frontend)
- MLX framework (inference)
- Playwright (E2E testing)
- Docker/Kubernetes (deployment)

---

## Milestones

### v0.2.0 - Security Ready
- [ ] Authentication enabled
- [ ] Rate limiting active
- [ ] CORS restricted
- [ ] Strong passwords required

### v0.3.0 - Quality Gate
- [ ] 80% test coverage
- [ ] E2E tests passing
- [ ] CI/CD pipeline active
- [ ] Pre-commit hooks enforced

### v0.4.0 - Integration Hub
- [ ] LocalCrew connected
- [ ] KAS integrated
- [ ] Unified dashboard
- [ ] MCP server available

### v1.0.0 - Production Ready
- [ ] CLI tool published
- [ ] Full documentation
- [ ] Benchmark suite
- [ ] Community adoption

---

## Quick Wins (This Week)

1. **Fix Auth (2 hours)**
   - Add config fields
   - Register middleware
   - Update .env.example

2. **Add Rate Limiting (2 hours)**
   - Install slowapi
   - Decorate admin endpoints

3. **Restrict CORS (30 min)**
   - Update middleware config

4. **LocalCrew Integration (4 hours)**
   - Point agents to MLX Hub
   - Test prompt caching benefit

5. **Update Documentation (1 hour)**
   - Mark security fixes in README
   - Update startup instructions

---

## Contributing

1. Pick a task from roadmap
2. Create feature branch
3. Implement with tests
4. Submit PR for review
5. Merge after CI passes

---

*This roadmap is a living document. Update as priorities shift.*
