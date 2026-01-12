# MLX Model Hub

A comprehensive platform for managing, training, and deploying MLX models on Apple Silicon.

## Overview

MLX Model Hub provides a full-stack solution for working with MLX models:

- **Backend API**: FastAPI service for model management, training, and inference
- **Frontend Dashboard**: Next.js web interface for managing models and jobs
- **Infrastructure**: Docker Compose stack with PostgreSQL, MLflow, Prometheus, and Grafana

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js 15)                       │
│  Dashboard │ Models │ Training │ Inference │ Metrics           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Backend API (FastAPI)                        │
│  REST API │ Model Cache │ Training Manager │ Inference Engine  │
└─────────────────────────────────────────────────────────────────┘
        │           │              │               │
        ▼           ▼              ▼               ▼
┌───────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────────┐
│PostgreSQL │ │  MLflow  │ │ Prometheus │ │     Grafana      │
│(metadata) │ │(tracking)│ │ (metrics)  │ │  (dashboards)    │
└───────────┘ └──────────┘ └────────────┘ └──────────────────┘
```

## Features

### Model Management
- Download models from Hugging Face (mlx-community)
- Local model caching with LRU eviction
- Model loading/unloading for memory management
- Support for quantized models (4-bit, 8-bit)

### Training
- LoRA fine-tuning with configurable parameters
- Real-time training metrics via MLflow
- Background job processing
- Support for JSONL datasets

### Inference
- Text generation with streaming support
- Configurable parameters (temperature, top_p, max_tokens)
- Performance metrics (TTFT, tokens/second)
- Request correlation and tracing

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
uv run uvicorn mlx_hub.main:app --reload
```

Backend will be available at `http://localhost:8000`.

### 3. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at `http://localhost:3000`.

## Services

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | Web dashboard |
| Backend API | http://localhost:8000 | REST API |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Grafana | http://localhost:3001 | Metrics dashboards |
| Prometheus | http://localhost:9090 | Metrics storage |
| MLflow | http://localhost:5001 | Experiment tracking |
| PostgreSQL | localhost:5434 | Database |

## API Endpoints

### Models
- `GET /api/v1/models` - List models
- `GET /api/v1/models/{id}` - Get model details
- `POST /api/v1/models/download` - Download model
- `POST /api/v1/models/{id}/load` - Load model
- `POST /api/v1/models/{id}/unload` - Unload model
- `DELETE /api/v1/models/{id}` - Delete model

### Training
- `GET /api/v1/training` - List training jobs
- `GET /api/v1/training/{id}` - Get job details
- `POST /api/v1/training` - Create training job
- `POST /api/v1/training/{id}/cancel` - Cancel job

### Inference
- `POST /api/v1/inference` - Run inference
- `POST /api/v1/inference/stream` - Streaming inference

### Health
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

### Frontend Environment Variables

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
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
├── backend/
│   ├── src/mlx_hub/
│   │   ├── api/           # API routes
│   │   ├── core/          # Core modules (cache, config)
│   │   ├── ml/            # ML modules (inference, training)
│   │   ├── models/        # Database models
│   │   ├── observability/ # Metrics & tracing
│   │   └── services/      # Business logic
│   └── tests/             # Unit tests
├── frontend/
│   ├── src/
│   │   ├── app/           # Next.js pages
│   │   ├── components/    # React components
│   │   └── lib/           # API client & hooks
│   └── e2e/               # Playwright tests
├── docker/
│   ├── grafana/           # Grafana config & dashboards
│   └── prometheus/        # Prometheus config
└── docker-compose.yml     # Infrastructure stack
```

## License

MIT
