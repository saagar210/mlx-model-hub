# Project Templates
# Reusable starters for AI/ML and full-stack projects

## Quick Reference

See `AUDIT_AND_ROADMAP.md` for comprehensive analysis, security audit, and development roadmap.

## Current Templates (vibe-templates/)

### Production-Ready

| Template | Purpose | Stack |
|----------|---------|-------|
| **vibe-coding-template/** | Full-stack AI app | Next.js 14 + FastAPI + Supabase + OpenAI/Claude |
| **agent-starter-pack/** | Google Cloud agents | Python + GCP + Vertex AI + LangGraph |
| **langgraph-starter-kit/** | Multi-agent framework | TypeScript + LangChain + Fastify |
| **self-hosted-ai-starter-kit/** | Local AI stack | Docker + n8n + Ollama + Qdrant |

### Reference/Tools

| Template | Purpose |
|----------|---------|
| **sim/** | Visual AI workflow builder (208 MB) |
| **n8n-automation-templates-5000/** | 5000+ workflow examples |
| **vibesdk-templates/** | Cloudflare Workers generation |
| **agentics/** | GitHub Actions AI workflows |

## Planned Templates (TODO)

- [ ] `python-api/` - FastAPI + Docker + pytest
- [ ] `react-app/` - Vite + React + TypeScript + Tailwind
- [ ] `fullstack/` - Combined frontend + backend
- [ ] `exploration/` - Minimal quick starter
- [ ] `python-cli/` - Typer + Rich CLI tool
- [ ] `mcp-server/` - Model Context Protocol server
- [ ] `mlx-inference/` - Apple Silicon ML inference

## Using Templates

### vibe-coding-template (Recommended Starter)
```bash
cp -r ~/claude-code/templates/vibe-templates/vibe-coding-template ~/claude-code/ai-tools/my-project
cd ~/claude-code/ai-tools/my-project
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
# Edit .env files with your API keys
docker-compose up -d
```

### self-hosted-ai-starter-kit (Local AI)
```bash
cd ~/claude-code/templates/vibe-templates/self-hosted-ai-starter-kit
docker compose up  # Mac (CPU)
# OR: docker compose --profile gpu-nvidia up  # NVIDIA GPU
```

## Integration Points

### With Knowledge Activation System (KAS)
Templates can integrate with KAS at `http://localhost:8000` for:
- RAG context retrieval
- Knowledge search
- Content ingestion

### With MLX Model Hub
Connect to `http://localhost:8080` for:
- Local model inference on Apple Silicon
- OpenAI-compatible API

### With LocalCrew
Trigger automation via:
- Task decomposition
- Research crews
- Human review workflows

## Security Notes

**WARNING**: Run security hardening before production deployment:
- Enable TypeScript strict mode
- Pin dependency versions
- Add non-root Docker users
- Implement rate limiting
- Add security headers

See `AUDIT_AND_ROADMAP.md` for detailed security fixes.
