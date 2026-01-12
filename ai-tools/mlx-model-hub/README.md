# MLX Model Hub

A comprehensive platform for managing, training, and deploying MLX models on Apple Silicon.

**Latest Update (2026-01-12):** ✅ KV Cache / Prompt Caching implemented for 10x faster inference

## Overview

MLX Model Hub provides a full-stack solution for working with MLX models:

- **Backend API**: FastAPI service for model management, training, and jobs (port 8002)
- **Inference Server**: OpenAI-compatible API with KV cache support (port 8080)
- **Frontend Dashboard**: Next.js 15 web interface with shadcn/ui (port 3005)
- **Infrastructure**: Docker Compose stack with PostgreSQL, MLflow, Prometheus, and Grafana

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js 15) :3005                 │
│  Dashboard │ Models │ Training │ Discover │ Inference          │
└─────────────────────────────────────────────────────────────────┘
                │                               │
                ▼                               ▼
┌───────────────────────────┐    ┌─────────────────────────────┐
│  Backend API :8002        │    │ Inference Server :8080      │
│  • Model Registry         │    │ • OpenAI-compatible API     │
│  • Training Jobs          │    │ • KV Cache (NEW)            │
│  • Data Prep              │    │ • Prompt Caching            │
│  • HuggingFace Integration│    │ • Model Manager             │
└───────────────────────────┘    └─────────────────────────────┘
        │           │
        ▼           ▼
┌───────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────────┐
│PostgreSQL │ │  MLflow  │ │ Prometheus │ │     Grafana      │
│(metadata) │ │(tracking)│ │ (metrics)  │ │  (dashboards)    │
└───────────┘ └──────────┘ └────────────┘ └──────────────────┘
```

## Features

### Model Management
- **Model Discovery**: Search and browse HuggingFace models
- **Local Caching**: LRU eviction with configurable limits
- **Memory Management**: Smart loading/unloading
- **Quantization**: 4-bit and 8-bit model support
- **Model Registry**: Track custom LoRA adapters

### Training
- **LoRA Fine-tuning**: Configurable rank, alpha, dropout
- **MLflow Integration**: Real-time metrics and artifact tracking
- **Background Jobs**: Non-blocking training execution
- **Dataset Support**: JSONL, text files, chat templates
- **Export**: Adapter export for inference server

### Inference
- **OpenAI-Compatible API**: Drop-in replacement for OpenAI SDK
- **KV Cache**: ✨ NEW - 10x faster on repeated prompts
- **Prompt Caching**: System prompt pre-computation
- **Streaming**: Real-time token generation
- **Performance Metrics**: TTFT, tokens/second tracking
- **Multi-Model**: Switch between models instantly

### Observability
- Prometheus metrics endpoint
- OpenTelemetry tracing
- Pre-built Grafana dashboards
- Health checks (liveness, readiness)

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- Apple Silicon Mac (M1/M2/M3/M4)

### 1. Start Infrastructure

```bash
# Start PostgreSQL, MLflow, Prometheus, Grafana
docker compose up -d
```

### 2. Start Backend

```bash
cd backend
uv sync
uv run uvicorn mlx_hub.main:app --reload --port 8002
```

Backend will be available at `http://localhost:8002`.

### 3. Start Inference Server

```bash
cd inference-server
uv sync
uv run python -m unified_mlx_app.main --api-only
```

Inference server will be available at `http://localhost:8080`.

### 4. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at `http://localhost:3005`.

## Services

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3005 | Next.js dashboard |
| Backend API | http://localhost:8002 | Model registry, training |
| Backend Docs | http://localhost:8002/docs | Swagger UI |
| Inference Server | http://localhost:8080 | OpenAI-compatible API |
| Inference Docs | http://localhost:8080/docs | Inference API docs |
| Grafana | http://localhost:3001 | Metrics dashboards |
| Prometheus | http://localhost:9090 | Metrics storage |
| MLflow | http://localhost:5001 | Experiment tracking |
| PostgreSQL | localhost:5434 | Database |

## API Endpoints

### Backend API (port 8002)

#### Models
- `GET /api/v1/models` - List models
- `GET /api/v1/models/{id}` - Get model details
- `POST /api/v1/models/download` - Download model from HuggingFace
- `DELETE /api/v1/models/{id}` - Delete model

#### Training
- `GET /api/v1/training` - List training jobs
- `GET /api/v1/training/{id}` - Get job details
- `POST /api/v1/training` - Create training job
- `POST /api/v1/training/{id}/cancel` - Cancel job

#### Discovery
- `GET /api/v1/discover/search` - Search HuggingFace models
- `GET /api/v1/discover/popular` - Get popular models
- `POST /api/v1/discover/download` - Download and register model

### Inference Server (port 8080)

#### OpenAI-Compatible
- `POST /v1/chat/completions` - Chat completions (streaming supported)
- `GET /v1/models` - List available models

#### Admin & Cache Management
- `GET /admin/health` - Health check
- `GET /admin/models` - List registered models
- `POST /admin/models/register` - Register custom model/adapter
- `DELETE /admin/models/{name}` - Unregister model
- `GET /admin/cache/prompts` - List cached prompts
- `GET /admin/cache/prompts/stats` - Cache statistics
- `POST /admin/cache/prompts/warmup` - Warm up cache
- `POST /admin/cache/prompts/clear` - Clear cache

### Health & Metrics
- `GET /health` - Health check
- `GET /health/live` - Liveness probe
- `GET /health/ready` - Readiness probe
- `GET /metrics` - Prometheus metrics

## Configuration

### Backend Environment Variables

```env
DATABASE_URL=postgresql://user:pass@localhost:5434/mlx_hub
MLFLOW_TRACKING_URI=http://localhost:5001
MODEL_CACHE_DIR=~/.cache/mlx-hub
MODEL_CACHE_MAX_SIZE=50GB
OTLP_ENDPOINT=http://localhost:4317
```

### Inference Server Environment Variables

```env
# Server
MLX_HOST=127.0.0.1
MLX_API_PORT=8080

# KV Cache (Prompt Caching)
MLX_PROMPT_CACHE_ENABLED=true
MLX_PROMPT_CACHE_DIR=~/.unified-mlx/cache/prompts
MLX_PROMPT_CACHE_MAX_ENTRIES=10
MLX_PROMPT_CACHE_PERSIST=true

# Model Defaults
MLX_TEXT_MODEL=mlx-community/Qwen2.5-7B-Instruct-4bit
MLX_MAX_TOKENS=2048
MLX_TEMPERATURE=0.7
```

### Frontend Environment Variables

```env
NEXT_PUBLIC_API_URL=http://localhost:8002
NEXT_PUBLIC_INFERENCE_URL=http://localhost:8080
```

## KV Cache / Prompt Caching ✨

The inference server includes intelligent KV caching for 10x faster repeated queries:

### How It Works
1. **System Prompt Detection**: Automatically extracts system prompts from conversations
2. **KV State Caching**: Pre-computes and caches key-value states for system prompts
3. **Automatic Reuse**: Subsequent requests with the same system prompt skip re-processing
4. **LRU Eviction**: Keeps top 10 most-used prompts in memory (configurable)
5. **Disk Persistence**: Survives server restarts

### Example: RAG Pipeline
```bash
# First query (cache miss) - ~2.5s TTFT
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mlx-community/Qwen2.5-7B-Instruct-4bit",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant with deep knowledge of Python programming..."},
      {"role": "user", "content": "What is a decorator?"}
    ]
  }'

# Second query (cache hit) - ~0.3s TTFT 🚀
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mlx-community/Qwen2.5-7B-Instruct-4bit",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant with deep knowledge of Python programming..."},
      {"role": "user", "content": "Explain list comprehensions"}
    ]
  }'
```

### Cache Statistics
```bash
# View cache stats
curl http://localhost:8080/admin/cache/prompts/stats

# List cached prompts
curl http://localhost:8080/admin/cache/prompts

# Clear cache
curl -X POST http://localhost:8080/admin/cache/prompts/clear
```

## Development

### Running Tests

```bash
# Backend tests
cd backend
uv run pytest

# Frontend E2E tests
cd frontend
npm run test:e2e
```

### Code Quality

```bash
# Backend
cd backend
uv run ruff check .
uv run ruff format .

# Frontend
cd frontend
npm run lint
```

## Project Structure

```
mlx-model-hub/
├── backend/                # Backend API (port 8002)
│   ├── src/mlx_hub/
│   │   ├── api/           # REST API routes
│   │   ├── core/          # Training, LoRA, data prep
│   │   ├── models/        # Database models
│   │   ├── services/      # Business logic
│   │   └── observability/ # Metrics & tracing
│   └── tests/             # Unit tests (57% coverage)
├── inference-server/       # Inference API (port 8080)
│   └── src/unified_mlx_app/
│       ├── api/           # OpenAI-compatible routes
│       ├── cache/         # KV cache + prompt cache
│       ├── models/        # Model loading/management
│       ├── services/      # Chat, generation
│       └── config.py      # Configuration
├── frontend/               # Next.js UI (port 3005)
│   ├── src/
│   │   ├── app/           # Pages (models, training, discover, inference)
│   │   ├── components/    # shadcn/ui components
│   │   └── lib/           # API client & hooks
│   └── e2e/               # Playwright tests (TODO)
├── docker/
│   ├── grafana/           # Grafana config & dashboards
│   └── prometheus/        # Prometheus config
└── docker-compose.yml     # Infrastructure stack
```

## License

MIT
