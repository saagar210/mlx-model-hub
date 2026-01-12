# Unified MLX Inference Server

> Part of [MLX Model Hub](../README.md) - the inference engine for local AI on Apple Silicon.

A unified interface for local AI inference on Apple Silicon, combining text generation, vision analysis, speech synthesis, and speech recognition.

## Features

- **Text Generation** - Chat with Qwen2.5-7B-Instruct (4-bit quantized)
- **Vision Analysis** - Image understanding with Qwen2-VL-2B
- **Speech Synthesis** - Text-to-speech with OuteTTS
- **Speech Recognition** - Audio transcription with Whisper

## Quick Start

### Option 1: Modern React Frontend (Recommended)

Start the backend API server:
```bash
pip install -e .
python -m unified_mlx_app.main --api-only
```

In a separate terminal, start the frontend:
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 in your browser.

### Option 2: Legacy Gradio UI

```bash
pip install -e .
unified-mlx
```

Open http://localhost:7860 in your browser.

## API

OpenAI-compatible API available at http://localhost:8080/v1

### Endpoints

- `GET /health` - Health check with model status
- `GET /v1/models` - List available models
- `POST /v1/chat/completions` - Chat completions (streaming supported)
- `POST /v1/audio/speech` - Text-to-speech
- `POST /v1/audio/transcriptions` - Speech-to-text

### Example: Chat Completion

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mlx-community/Qwen2.5-7B-Instruct-4bit",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

## Architecture

```
mlx-model-hub/
├── inference-server/          # This directory (inference engine)
│   ├── src/unified_mlx_app/   # Python backend
│   │   ├── api/               # FastAPI routes
│   │   ├── services/          # Business logic
│   │   ├── models/            # MLX model management
│   │   └── ui/                # Legacy Gradio UI
│   └── frontend/              # Inference-specific UI (optional)
├── backend/                   # Model Hub Python backend
├── frontend/                  # Model Hub Next.js UI (primary)
└── docs/                      # Consolidated documentation
```

## Development

### Backend
```bash
pip install -e ".[dev]"
pytest tests/
```

### Frontend
```bash
cd frontend
npm install
npm run dev    # Development
npm run build  # Production build
```

## Requirements

- macOS with Apple Silicon (M1/M2/M3/M4)
- Python 3.11+
- Node.js 18+ (for React frontend)
