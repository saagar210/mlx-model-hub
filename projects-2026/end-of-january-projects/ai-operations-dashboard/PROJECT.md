# AI Operations Dashboard
## Langfuse LLM Observability with DeepEval, Kubernetes, and Full Integration

**Status**: Implementation Complete - Ready for Deployment

---

## Quick Start

### Prerequisites

```bash
# Install required tools
brew install k3d helm kubectl

# Ensure Docker Desktop is running
open -a Docker
```

### Deploy Langfuse Stack

```bash
cd ~/claude-code/projects-2026/end-of-january-projects/ai-operations-dashboard

# Create k3d cluster (if not exists)
k3d cluster create langfuse-dev \
  --port "3002:3000@loadbalancer" \
  --port "5435:5432@loadbalancer" \
  --port "8123:8123@loadbalancer" \
  --port "4566:4566@loadbalancer" \
  --agents 2 --servers 1

# Deploy with Helm
kubectl create namespace langfuse
helm upgrade --install langfuse ./helm/langfuse \
  -f helm/langfuse/values.local.yaml \
  --namespace langfuse --wait

# Or use the deploy script
./scripts/deploy-local.sh
```

### Verify Deployment

```bash
kubectl get pods -n langfuse
curl http://localhost:3002/api/public/health
open http://localhost:3002
```

### Configure API Keys

1. Access Langfuse UI at http://localhost:3002
2. Create account (first user becomes admin)
3. Create project → Settings → API Keys
4. Copy keys to `.env`:

```bash
cp .env.example .env
# Edit .env with your keys
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        AI OPERATIONS DASHBOARD                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    INSTRUMENTED APPLICATIONS                             │    │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                │    │
│  │  │   LocalCrew   │  │   Knowledge   │  │  AI Command   │                │    │
│  │  │   (CrewAI)    │  │    Engine     │  │    Center     │                │    │
│  │  │  Python SDK   │  │  OpenTelemetry│  │   Callbacks   │                │    │
│  │  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘                │    │
│  └──────────┴──────────────────┴──────────────────┴─────────────────────────┘    │
│                                    │                                             │
│                                    ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    K3D KUBERNETES CLUSTER                                │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │    │
│  │  │  Langfuse (2 pods) │ Worker (2 pods) │ Redis │ PostgreSQL │ CH  │    │    │
│  │  └─────────────────────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                    │                                             │
│                                    ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  EVALUATION PIPELINE: DeepEval (Qwen 2.5:14b) → Scores → Alerts         │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
ai-operations-dashboard/
├── helm/
│   └── langfuse/
│       ├── Chart.yaml              # Helm chart definition
│       ├── values.yaml             # Default values
│       ├── values.local.yaml       # Local k3d config
│       ├── values.production.yaml  # AWS/cloud config
│       └── templates/
│           ├── namespace.yaml
│           ├── secrets.yaml
│           ├── configmap.yaml
│           ├── postgresql.yaml
│           ├── clickhouse.yaml
│           ├── redis.yaml
│           ├── localstack.yaml
│           ├── langfuse-web.yaml
│           └── langfuse-worker.yaml
├── evaluation/
│   ├── continuous_eval.py         # DeepEval pipeline
│   └── cron_eval.sh               # Cron wrapper
├── alerts/
│   └── quality_monitor.py         # Clawdbot alerts
├── monitoring/
│   └── grafana/
│       ├── datasources/
│       │   └── clickhouse.yaml
│       └── dashboards/
│           └── rag_quality.json
├── scripts/
│   ├── deploy-local.sh
│   └── teardown-local.sh
├── .github/
│   └── workflows/
│       └── langfuse-deploy.yaml
├── pyproject.toml
├── .env.example
└── PROJECT.md
```

---

## Port Allocation

| Service | Port | Purpose |
|---------|------|---------|
| Langfuse Web | 3002 | Main UI and API |
| PostgreSQL | 5435 | Metadata storage |
| ClickHouse HTTP | 8123 | Analytics queries |
| LocalStack S3 | 4566 | Trace blob storage |
| Grafana | 3001 | Dashboards (existing) |
| Prometheus | 9090 | Metrics (existing) |

---

## Integration Guide

### LocalCrew Integration

```python
from localcrew.integrations import trace_crew, trace_agent, trace_generation

@trace_crew("research_crew")
async def run_research(topic: str):
    ...

@trace_agent("researcher")
async def research_task(query: str):
    ...

@trace_generation(model="mlx/qwen2.5:14b")
async def generate(prompt: str):
    ...
```

### Knowledge Engine Integration

```python
from knowledge_engine.observability import configure_langfuse_otel, RAGTracer

tracer = configure_langfuse_otel()
rag_tracer = RAGTracer(tracer)

with rag_tracer.query("What is machine learning?") as span:
    docs = retriever.search(question)
    span.set_attribute("retrieval.doc_count", len(docs))
    answer = generator.generate(question, docs)
```

---

## Evaluation Pipeline

The continuous evaluation runs every 15 minutes via cron:

```bash
# Add to crontab
*/15 * * * * ~/ai-operations-dashboard/evaluation/cron_eval.sh

# Or run manually
python evaluation/continuous_eval.py
```

Metrics evaluated:
- **Faithfulness**: Is the answer grounded in context? (threshold: 0.7)
- **Relevancy**: Does it address the question? (threshold: 0.7)
- **Hallucination**: Unsupported claims (threshold: 0.3, lower is better)

---

## Quality Alerts

Enable Clawdbot alerts:

```bash
# Set webhook URL
export CLAWDBOT_WEBHOOK_URL="https://your-webhook-url"

# Load LaunchAgent
launchctl load ~/Library/LaunchAgents/com.langfuse.quality-monitor.plist
```

Alerts trigger when:
- Faithfulness drops below 0.6
- Relevancy drops below 0.7
- Hallucination rises above 0.3

---

## Resource Requirements

| Component | CPU | Memory | Storage |
|-----------|-----|--------|---------|
| Langfuse Web (2 pods) | 0.5 | 1GB | - |
| Langfuse Worker (2 pods) | 1 | 2GB | - |
| PostgreSQL | 1 | 2GB | 10GB |
| ClickHouse | 2 | 4GB | 30GB |
| Redis | 0.25 | 512MB | - |
| LocalStack (S3) | 0.5 | 1GB | 10GB |
| **Total** | **8.25** | **16.5GB** | **50GB** |

---

## Commands Reference

```bash
# Cluster management
k3d cluster list
k3d cluster start langfuse-dev
k3d cluster stop langfuse-dev
k3d cluster delete langfuse-dev

# Helm management
helm list -n langfuse
helm upgrade --install langfuse ./helm/langfuse -f helm/langfuse/values.local.yaml -n langfuse
helm uninstall langfuse -n langfuse

# Debugging
kubectl get pods -n langfuse
kubectl logs -f deployment/langfuse-web -n langfuse
kubectl exec -it deployment/langfuse-postgresql -n langfuse -- psql -U langfuse

# Port forwarding (if k3d load balancer isn't working)
kubectl port-forward svc/langfuse-web 3002:3000 -n langfuse
```

---

## Future Integration

After core platform is stable:

1. **AI Command Center**: LiteLLM callbacks → all LLM calls traced
2. **Automation Engine**: n8n workflow traces
3. **Self-Improving Agents**: Export traces → DSPy training data
4. **Universal Context**: Index traces as searchable context

---

## Troubleshooting

### Pods not starting
```bash
kubectl describe pod <pod-name> -n langfuse
kubectl logs <pod-name> -n langfuse
```

### Database connection issues
```bash
kubectl exec -it langfuse-postgresql-0 -n langfuse -- pg_isready
```

### ClickHouse issues
```bash
kubectl exec -it langfuse-clickhouse-0 -n langfuse -- clickhouse-client --query "SELECT 1"
```

### Reset everything
```bash
./scripts/teardown-local.sh
./scripts/deploy-local.sh
```
