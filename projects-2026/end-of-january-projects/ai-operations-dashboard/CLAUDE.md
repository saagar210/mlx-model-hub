# AI Operations Dashboard - Claude Instructions

## Project Overview
Self-hosted Langfuse LLM observability platform with:
- Kubernetes-first deployment (k3d local, Helm charts for cloud)
- DeepEval evaluation pipeline using local Qwen 2.5:14b
- Integration with LocalCrew and Knowledge Engine
- Grafana dashboards and Clawdbot alerts

## Key Locations
- Helm charts: `helm/langfuse/`
- Evaluation: `evaluation/continuous_eval.py`
- Alerts: `alerts/quality_monitor.py`
- Grafana: `monitoring/grafana/`

## Common Tasks

### Deploy/Redeploy
```bash
./scripts/deploy-local.sh
# Or manually:
helm upgrade --install langfuse ./helm/langfuse -f helm/langfuse/values.local.yaml -n langfuse
```

### Check Status
```bash
kubectl get pods -n langfuse
curl http://localhost:3002/api/public/health
```

### Run Evaluation Manually
```bash
python evaluation/continuous_eval.py
```

## Integration Files (Other Projects)
- LocalCrew: `~/claude-code/personal/crewai-automation-platform/src/localcrew/integrations/langfuse_client.py`
- Knowledge Engine: `~/claude-code/personal/knowledge-engine/src/knowledge_engine/observability/langfuse_otel.py`

## Ports
- Langfuse: 3002
- PostgreSQL: 5435
- ClickHouse: 8123
- LocalStack: 4566

## Environment Variables
Required in `.env`:
- LANGFUSE_PUBLIC_KEY
- LANGFUSE_SECRET_KEY
- LANGFUSE_HOST (default: http://localhost:3002)
- CLAWDBOT_WEBHOOK_URL (for alerts)
