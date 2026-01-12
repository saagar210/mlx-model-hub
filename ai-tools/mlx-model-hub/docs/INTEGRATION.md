# MLX Model Hub + Unified MLX App + KAS Integration

This document describes the integration between mlx-model-hub (model management & training), unified-mlx-app (inference server), and KAS (Knowledge Activation System for RAG).

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Frontend (Next.js)                                  │
│                          localhost:3005                                      │
├────────────────────┬────────────────────────┬───────────────────────────────┤
│                    │                        │                               │
│  mlx-model-hub API │  unified-mlx-app API   │    KAS API                   │
│  localhost:8002    │  localhost:8080        │    localhost:8000            │
│                    │                        │                               │
│  - Model CRUD      │  - OpenAI-compatible   │    - Hybrid search           │
│  - Training jobs   │  - /v1/chat/completions│    - Q&A with citations      │
│  - Dataset mgmt    │  - /v1/models          │    - Content ingestion       │
│  - Export          │  - /admin/* (registry) │    - /api/v1/* (integration) │
│                    │                        │                               │
└────────────────────┴────────────────────────┴───────────────────────────────┘
          │                    │                        │
          ▼                    ▼                        ▼
┌─────────────────┐   ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │   │   MLX Models    │    │  ChromaDB +     │
│   localhost:5434│   │   (HuggingFace) │    │  SQLite (KAS)   │
└─────────────────┘   └─────────────────┘    └─────────────────┘
```

## Service Ports

| Service | Port | Purpose |
|---------|------|---------|
| mlx-model-hub frontend | 3005 | Web UI |
| mlx-model-hub backend | 8002 | Model management API |
| unified-mlx-app | 8080 | Inference server |
| KAS (Knowledge Activation System) | 8000 | Knowledge retrieval / RAG |
| PostgreSQL (Docker) | 5434 | Database (mlx-model-hub) |
| Grafana | 3001 | Metrics dashboards |
| Prometheus | 9090 | Metrics collection |
| MLflow | 5001 | Experiment tracking |

## API Integration

### 1. Model Registration Flow

When a model is trained in mlx-model-hub, it can be exported to the inference server:

```
Training Complete → Export Bundle → Register with unified-mlx-app
```

**Export Bundle Structure:**
```
storage/models/exports/<model-name>/
├── adapters.safetensors   # LoRA weights
├── config.json            # Training config
└── metadata.json          # Model metadata
```

**Registration Payload:**
```json
{
  "name": "my-fine-tuned-model",
  "base_model": "mlx-community/Llama-3.2-3B-Instruct-4bit",
  "adapter_path": "/path/to/adapters.safetensors",
  "type": "lora",
  "config": {
    "lora_rank": 16,
    "lora_alpha": 32
  },
  "metadata": {...},
  "registered_by": "mlx-model-hub",
  "model_id": "uuid-from-mlx-model-hub"
}
```

### 2. Admin API Endpoints (unified-mlx-app)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/health` | GET | Server health check |
| `/admin/models` | GET | List all registered models |
| `/admin/models?registered_by=mlx-model-hub` | GET | Filter by source |
| `/admin/models/{name}/status` | GET | Get model status |
| `/admin/models/{name}` | DELETE | Unregister model |
| `/admin/models/{name}/preload` | POST | Load model into memory |
| `/admin/scan` | POST | Scan exports directory |

### 3. Inference API (OpenAI-compatible)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/models` | GET | List available models |
| `/v1/chat/completions` | POST | Chat completion (streaming) |
| `/v1/completions` | POST | Text completion |

**Example Chat Request:**
```json
{
  "model": "mlx-community/Qwen2.5-7B-Instruct-4bit",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "max_tokens": 512,
  "temperature": 0.7,
  "stream": true
}
```

## Frontend Features

### Registry Page (`/registry`)

- **Filter Toggle**: Show all models or only mlx-model-hub models
- **Batch Operations**: Select multiple models for bulk pre-load/unregister
- **Loading States**: Spinner indicators during async operations
- **Chat Button**: Quick link to inference with selected model

### Model Detail Page (`/models/[id]`)

- **Use in Chat**: Export model and navigate to inference
- **Registry Status**: Shows if model is registered and loaded
- **Pre-load/Unregister**: Manage model in inference server

### Inference Page (`/inference`)

- **Server Status**: Shows online/offline indicator
- **Error Handling**: Retry button when server unreachable
- **Query Params**: `?model=<name>` pre-selects model
- **Streaming**: Real-time token generation with stats
- **RAG Mode**: Toggle to enable knowledge-augmented responses
- **Knowledge Panel**: Search KAS and add context to prompts

## Configuration

### Backend (.env)
```env
DATABASE_URL=postgresql+asyncpg://mlxhub:mlxhub@localhost:5434/mlxhub
INFERENCE_SERVER_URL=http://localhost:8080
INFERENCE_AUTO_REGISTER=true
CORS_ORIGINS=["http://localhost:3000","http://localhost:3005"]
```

### Frontend (.env.local)
```env
NEXT_PUBLIC_API_URL=http://localhost:8002
NEXT_PUBLIC_INFERENCE_URL=http://localhost:8080
NEXT_PUBLIC_KAS_URL=http://localhost:8000
```

## Traceability

Models registered by mlx-model-hub include tracking fields:

- `registered_by: "mlx-model-hub"` - Identifies registration source
- `model_id: "<uuid>"` - Links to mlx-model-hub model record

This enables:
- Filtering registry to show only mlx-model-hub models
- Audit trail for model origins
- Future: automatic cleanup when models are deleted

## Error Handling

The integration handles these scenarios:

| Error | Response | UI Handling |
|-------|----------|-------------|
| Server offline | Connection refused | Show retry button |
| Model not found (404) | Model doesn't exist | Show error toast |
| Already registered (409) | Duplicate registration | Show info toast |
| Invalid config (400) | Bad request | Show validation error |

## Starting the Stack

```bash
# All commands assume you're in the mlx-model-hub root directory

# 1. Start Docker containers (PostgreSQL, Grafana, etc.)
docker-compose up -d

# 2. Start inference server (in a terminal)
cd inference-server && \
  source .venv/bin/activate && \
  python -m unified_mlx_app.main --api-only

# 3. Start KAS (Knowledge Activation System for RAG - optional)
cd ~/claude-code/personal/knowledge-activation-system && \
  source .venv/bin/activate && \
  uvicorn knowledge.api.main:app --host 127.0.0.1 --port 8000

# 4. Start Model Hub backend (in a terminal)
cd backend && \
  source .venv/bin/activate && \
  uvicorn mlx_hub.main:app --host 127.0.0.1 --port 8002

# 5. Start frontend (in a terminal)
cd frontend && npm run dev -- -p 3005
```

## Testing the Integration

```bash
# Check backend health
curl http://localhost:8002/health

# Check inference server health
curl http://localhost:8080/admin/health

# List registered models
curl http://localhost:8080/admin/models

# Test inference
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"mlx-community/Qwen2.5-7B-Instruct-4bit","messages":[{"role":"user","content":"Hi"}],"max_tokens":50}'
```

## KAS (Knowledge Activation System) Integration

### Overview

KAS provides knowledge retrieval capabilities for RAG (Retrieval-Augmented Generation). The MLX Model Hub frontend can search KAS and inject relevant context into prompts before sending to the inference server.

### KAS API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/health` | GET | Health check with stats |
| `/api/v1/search?q=<query>&limit=10` | GET | Search knowledge base |
| `/api/v1/stats` | GET | Database statistics |
| `/search/ask` | POST | Q&A with citations |

### RAG Workflow

```
User Query → KAS Search → Select Context → Augment Prompt → MLX Inference → Response
```

1. User opens Knowledge Panel (book icon) in inference page
2. Search the knowledge base for relevant content
3. Click results to add them to context
4. Enable RAG toggle to include context in prompts
5. Send message - context is automatically prepended

### Example KAS Search Response

```json
{
  "results": [
    {
      "content_id": "uuid",
      "title": "React Server Components",
      "content_type": "article",
      "score": 0.92,
      "chunk_text": "Server components run on the server..."
    }
  ],
  "query": "react server components",
  "total": 5,
  "source": "knowledge-activation-system"
}
```

### Starting KAS

```bash
cd knowledge-activation-system
source .venv/bin/activate
uvicorn knowledge.api.main:app --host 127.0.0.1 --port 8000
```

### Testing KAS Integration

```bash
# Check KAS health
curl http://localhost:8000/api/v1/health

# Search knowledge base
curl "http://localhost:8000/api/v1/search?q=react+hooks&limit=5"

# Get stats
curl http://localhost:8000/api/v1/stats
```
