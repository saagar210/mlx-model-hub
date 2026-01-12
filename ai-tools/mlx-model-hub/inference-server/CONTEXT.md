# Unified MLX AI Application - Project Context

**Created:** January 11, 2026
**Location:** `~/claude-code/ai-tools/unified-mlx-app`
**Branch:** `feature/initial-setup`
**Status:** Enhanced with STT, persistence, hot-swapping, caching

---

## Project Overview

A unified web application that combines four MLX-based AI capabilities into a single interface:
1. **Text Generation** (mlx-lm) - Chat with Qwen2.5-7B (model hot-swapping supported)
2. **Vision Analysis** (mlx-vlm) - Image understanding with Qwen2-VL-2B
3. **Speech Synthesis** (mlx-audio TTS) - Text-to-speech with Kokoro-82M
4. **Speech-to-Text** (mlx-audio STT) - Transcription with Whisper

The app provides both a **Gradio web UI** (port 7860) and an **OpenAI-compatible API** (port 8080).

---

## Background Context

This project emerged from a comprehensive system audit of a MacBook Pro M4 Pro (48GB RAM). During that session, we:

1. Installed modern shell tools: **Starship**, **Atuin**, **mise** (replacing pyenv/nvm)
2. Installed productivity apps: **Shottr**, **Maccy**, **sops**
3. Discovered and installed MLX packages: **mlx-lm**, **mlx-vlm**, **mlx-audio**
4. Tested each package individually via CLI
5. User asked: *"Can you combine all these into one app?"*

This led to creating this unified application.

---

## Project Structure

```
unified-mlx-app/
├── .taskmaster/
│   └── docs/
│       └── prd.txt              # Full PRD document
├── src/unified_mlx_app/
│   ├── __init__.py              # Package init, version
│   ├── config.py                # Settings (env vars, model paths, ports)
│   ├── main.py                  # Entry point, launches both servers
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py            # OpenAI-compatible API endpoints
│   │   └── schemas.py           # Pydantic models for requests/responses
│   ├── models/
│   │   ├── __init__.py          # Exports ModelManager, ModelType
│   │   └── manager.py           # Lazy loading, caching, memory management
│   └── ui/
│       ├── __init__.py
│       ├── app.py               # Gradio interface (5 tabs)
│       └── theme.py             # Custom theme + 400+ lines CSS
├── pyproject.toml               # Dependencies and project config
├── run.py                       # Quick launch script
├── .gitignore
└── CONTEXT.md                   # This file
```

---

## Features Implemented

### Web UI (Gradio) - http://localhost:7860

| Tab | Description |
|-----|-------------|
| **Chat** | Streaming text generation with conversation persistence, model hot-swapping |
| **Vision** | Image upload (drag/drop, clipboard) + multi-turn analysis chat |
| **Speech** | Text-to-speech with voice selection, speed control, browser playback |
| **Transcribe** | Speech-to-text with audio upload or microphone recording |
| **Pipeline** | "Describe & Speak" - image → description → audio with progress bar |
| **Status** | Memory monitoring, model status cards with sizes, API documentation |

### API (FastAPI) - http://localhost:8080

| Endpoint | Description |
|----------|-------------|
| `POST /v1/chat/completions` | OpenAI-compatible text generation (streaming + caching) |
| `POST /v1/audio/speech` | OpenAI-compatible TTS |
| `POST /v1/audio/transcriptions` | OpenAI-compatible speech-to-text |
| `GET /v1/models` | List available models |
| `GET /health` | Health check with model status |

### UI Design System

- **Theme:** Custom `UnifiedMLXTheme` with indigo/purple gradient palette
- **Fonts:** Inter (UI), JetBrains Mono (code)
- **Components:**
  - Gradient header with glassmorphism API badge
  - Modern tab navigation with smooth transitions
  - Model cards with emoji icons and status badges
  - Pipeline step indicators
  - Character/word counters
- **CSS:** 400+ lines of custom styling for polish, animations, dark mode support

---

## Models Used

| Type | Model | Size | Purpose |
|------|-------|------|---------|
| Text | `mlx-community/Qwen2.5-7B-Instruct-4bit` | ~4GB | Chat, text generation |
| Vision | `mlx-community/Qwen2-VL-2B-Instruct-4bit` | ~1.5GB | Image analysis |
| Speech | `mlx-community/Kokoro-82M-bf16` | ~200MB | Text-to-speech |
| STT | `mlx-community/whisper-large-v3-turbo` | ~1.5GB | Speech-to-text |

Models are **lazy-loaded** on first use and can be unloaded via the Status tab to free memory.

---

## How to Run

```bash
cd ~/claude-code/ai-tools/unified-mlx-app
python run.py
```

Or with the full Python path:
```bash
~/.local/share/mise/installs/python/3.12.12/bin/python run.py
```

The app will start:
- Web UI: http://127.0.0.1:7860
- API: http://127.0.0.1:8080

---

## Dependencies

Already installed in the mise-managed Python 3.12.12:
- `fastapi`, `uvicorn` - API server
- `gradio` - Web UI
- `mlx`, `mlx-lm`, `mlx-vlm`, `mlx-audio` - ML inference
- `pydantic`, `pydantic-settings` - Configuration
- `numpy`, `pillow`, `httpx` - Utilities

---

## Git Status

```
Branch: feature/initial-setup
Commits:
1. Initial project setup: Unified MLX AI Application
2. Complete UI overhaul with modern design system
```

**Not yet merged to main** - protected by a hook that prevents direct edits to main.

---

## Configuration

Environment variables (optional, with defaults):
```bash
MLX_HOST=127.0.0.1
MLX_API_PORT=8080
MLX_UI_PORT=7860
MLX_TEXT_MODEL=mlx-community/Qwen2.5-7B-Instruct-4bit
MLX_VISION_MODEL=mlx-community/Qwen2-VL-2B-Instruct-4bit
MLX_SPEECH_MODEL=mlx-community/Kokoro-82M-bf16
MLX_MAX_TOKENS=2048
MLX_TEMPERATURE=0.7
MLX_LAZY_LOAD=true
```

---

## Connecting External Apps

To use with AnythingLLM, Open WebUI, Continue.dev, or other OpenAI-compatible clients:

```
Base URL: http://localhost:8080/v1
Model: mlx-community/Qwen2.5-7B-Instruct-4bit
API Key: (not required, leave blank)
```

---

## Known Issues / Notes

1. **Port conflicts**: If port 7860 is in use (e.g., from previous mlx-vlm session), kill it first:
   ```bash
   lsof -ti:7860 | xargs kill -9
   ```

2. **First load is slow**: Models download on first use (~4GB for text model). Subsequent loads use cache.

3. **Memory**: With all models loaded, expect ~6-7GB usage. The 48GB M4 Pro handles this easily.

4. **mlx-audio language codes**: Use `a` for American English, `b` for British (not `en`).

---

## What's Next (Potential Improvements)

1. **Model hot-swapping** - Change models without restart
2. **Conversation persistence** - Save/load chat history
3. **Voice cloning** - mlx-audio supports this but not exposed in UI
4. **More pipelines** - "Read Aloud" (take any text → speech), "Transcribe & Respond"
5. **API key support** - Optional authentication for API
6. **Docker container** - For easier deployment

---

## File Locations for Reference

- **PRD:** `.taskmaster/docs/prd.txt`
- **Theme/CSS:** `src/unified_mlx_app/ui/theme.py`
- **Main UI:** `src/unified_mlx_app/ui/app.py`
- **Model Manager:** `src/unified_mlx_app/models/manager.py`
- **API Routes:** `src/unified_mlx_app/api/routes.py`
- **Config:** `src/unified_mlx_app/config.py`

---

## CLI Commands That Still Work

The individual MLX packages can still be used via CLI:

```bash
# Text generation
mlx_lm.chat --model mlx-community/Qwen2.5-7B-Instruct-4bit

# Vision analysis
mlx_vlm.generate --model mlx-community/Qwen2-VL-2B-Instruct-4bit \
  --image path/to/image.jpg --prompt "Describe this"

# Speech synthesis
mlx_audio.tts.generate --model mlx-community/Kokoro-82M-bf16 \
  --text "Hello world" --lang_code a --play
```

---

## Session Summary

1. Started with system audit of M4 Pro MacBook
2. Installed shell tools (Starship, Atuin, mise) and apps (Shottr, Maccy)
3. Discovered and installed MLX packages (mlx-lm, mlx-vlm, mlx-audio)
4. Tested each package via CLI
5. User requested a unified app combining all three
6. Created project with PRD, FastAPI backend, Gradio UI
7. Did complete UI overhaul with custom theme and modern design
8. App is running and functional at http://localhost:7860

**The app is ready for use and further iteration.**
