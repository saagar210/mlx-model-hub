# StreamMind - Comprehensive Implementation Plan
# Real-time Screen Analysis with Local AI

**Version:** 1.0.0
**Created:** January 12, 2026
**Hardware:** Apple M4 Pro (48GB RAM, 14 cores)
**Status:** Planning Complete

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Research Findings](#2-research-findings)
3. [System Architecture](#3-system-architecture)
4. [Technology Decisions](#4-technology-decisions)
5. [Local Assets Inventory](#5-local-assets-inventory)
6. [Project Structure](#6-project-structure)
7. [Implementation Phases](#7-implementation-phases)
8. [Detailed Task Breakdown](#8-detailed-task-breakdown)
9. [API Specifications](#9-api-specifications)
10. [Database Schema](#10-database-schema)
11. [Configuration System](#11-configuration-system)
12. [Testing Strategy](#12-testing-strategy)
13. [Performance Benchmarks](#13-performance-benchmarks)
14. [Security & Privacy](#14-security--privacy)
15. [Integration Points](#15-integration-points)
16. [Deployment & Distribution](#16-deployment--distribution)
17. [Risk Mitigation](#17-risk-mitigation)
18. [Success Metrics](#18-success-metrics)

---

## 1. Executive Summary

### 1.1 Vision
StreamMind is a macOS menu bar application that provides **real-time screen analysis** using local AI models. It captures your screen, analyzes content using vision models, and answers natural language questions about what's visible. All processing happens locally on your M4 Pro - no data ever leaves your machine.

### 1.2 Core Value Proposition
```
Your Screen → AI Vision → Instant Understanding

"What's that error?"
↓
"That's a TypeError in UserList.jsx line 45. You're calling .map()
on 'users' but it's undefined. Add a fallback: users || []"
```

### 1.3 Key Differentiators
| Feature | StreamMind | ChatGPT/Claude | Rewind.ai |
|---------|-----------|----------------|-----------|
| Processing | 100% Local | Cloud | Cloud |
| Privacy | Full | Limited | Limited |
| Latency | <3 seconds | 5-10 seconds | N/A |
| Cost | Free | $20+/month | $25/month |
| Internet | Not required | Required | Required |
| Screen Capture | Real-time | Manual upload | Passive |

### 1.4 Target Performance
- **Response Time**: <3 seconds for screen analysis
- **Memory Usage**: <500MB during active use
- **CPU Usage**: <5% when idle, <50% during analysis
- **Accuracy**: 90% correct error identification

---

## 2. Research Findings

### 2.1 Screen Capture (Web Research)

**Best Practice: Use MSS Library**
- MSS is **30x faster** than pyautogui on macOS
- Uses CoreGraphics native APIs under the hood
- Cross-platform (Windows, macOS, Linux)
- Supports multiple monitors

**For Maximum Performance (30fps):**
```python
# Native API approach via PyObjC
from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly
# Achieves 30fps on M2 Air, even faster on M4 Pro
```

**macOS Permissions:**
- Screen Recording permission required (System Preferences > Privacy)
- Users must grant permission on first launch

**Sources:**
- [MSS Documentation](https://python-mss.readthedocs.io/examples.html)
- [Native API Screenshot Gist](https://gist.github.com/mr-linch/d31024f931441a39c6a830328f8b5030)

### 2.2 Vision Models (Web Research)

**Best Practice: Ollama + llama3.2-vision:11b**
- Already installed on your system
- Supports up to 1120x1120 pixel images
- 128K context window
- Handles GIF, JPEG, PNG, WEBP formats
- Benchmark: DocVQA 88.4, VQAv2 75.2

**API Pattern:**
```python
# OpenAI-compatible endpoint
POST http://localhost:11434/v1/chat/completions
# OR native Ollama endpoint
POST http://localhost:11434/api/generate
```

**Key Insight:** Image must be base64 encoded, keep under 1120x1120 for best results.

**Sources:**
- [Ollama llama3.2-vision](https://ollama.com/library/llama3.2-vision)
- [KDnuggets Guide](https://www.kdnuggets.com/using-llama-32-vision-locally)

### 2.3 Window Detection (Web Research)

**Best Practice: NSWorkspace + Quartz**
```python
from AppKit import NSWorkspace
from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID

# Get frontmost app
active_app = NSWorkspace.sharedWorkspace().frontmostApplication()
app_name = active_app.localizedName()

# Get window list with details
windows = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
```

**Deprecated Warning:** `activeApplication()` is deprecated since macOS 10.7. Use `frontmostApplication()` instead.

**Sources:**
- [Apple Developer Docs](https://developer.apple.com/documentation/appkit/nsworkspace/frontmostapplication)
- [GitHub Gist](https://gist.github.com/ljos/3040846)

### 2.4 Menu Bar Apps (Web Research)

**Best Practice: rumps Library**
- Simple Python wrapper around PyObjC
- Supports dark mode automatically
- Timer decorators for background tasks
- No virtualenv (use venv instead)

```python
import rumps

class StreamMindApp(rumps.App):
    def __init__(self):
        super().__init__("StreamMind", icon="eye.png")

    @rumps.timer(1)  # Every 1 second
    def check_screen(self, _):
        # Background capture logic
        pass
```

**Distribution:** Use py2app for standalone .app bundle.

**Sources:**
- [rumps GitHub](https://github.com/jaredks/rumps)
- [Pomodoro Timer Tutorial](https://camillovisini.com/coding/create-macos-menu-bar-app-pomodoro)

### 2.5 Change Detection (Web Research)

**Best Practice: Perceptual Hashing with imagehash**
```python
import imagehash
from PIL import Image

# dHash is fastest and effective
hash1 = imagehash.dhash(Image.open("frame1.png"))
hash2 = imagehash.dhash(Image.open("frame2.png"))

# Hamming distance
difference = hash1 - hash2
if difference < 10:  # Same image
    skip_processing()
```

**Thresholds:**
- 0 bits: Identical images
- 1-10 bits: Likely same image with minor changes
- >10 bits: Different images

**Sources:**
- [imagehash GitHub](https://github.com/JohannesBuchner/imagehash)
- [PyImageSearch Tutorial](https://pyimagesearch.com/2017/11/27/image-hashing-opencv-python/)

### 2.6 Database (Web Research)

**Best Practice: aiosqlite with WAL Mode**
```python
import aiosqlite

async with aiosqlite.connect("streamind.db") as db:
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA synchronous=NORMAL")
    await db.execute("PRAGMA cache_size=-64000")  # 64MB cache
```

**SQLAlchemy 2.0 Integration:**
```python
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine("sqlite+aiosqlite:///streamind.db")
```

**Sources:**
- [aiosqlite GitHub](https://github.com/omnilib/aiosqlite)
- [SQLAlchemy AsyncIO Docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

### 2.7 AI Architecture Patterns (Web Research)

**Best Practice: Perception → Reasoning → Action**
```
┌────────────┐     ┌────────────┐     ┌────────────┐
│ Perception │────>│ Reasoning  │────>│   Action   │
│  (Vision)  │     │  (LLM)     │     │ (Response) │
└────────────┘     └────────────┘     └────────────┘
```

**Key Insight:** Use accessibility APIs for semantic understanding, not just pixel analysis.

**Multi-Agent Pattern (Future):**
- Parallel agents for complex analysis
- Sentiment, extraction, categorization running concurrently
- Final agent synthesizes results

**Sources:**
- [Google Cloud Agentic AI](https://cloud.google.com/architecture/choose-design-pattern-agentic-ai-system)
- [a16z AI Patterns](https://a16z.com/nine-emerging-developer-patterns-for-the-ai-era/)

---

## 3. System Architecture

### 3.1 High-Level Architecture
```
┌─────────────────────────────────────────────────────────────────────────┐
│                           StreamMind Application                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐        │
│  │   UI Layer      │   │   API Layer     │   │  CLI Layer      │        │
│  │   (Menu Bar)    │   │   (FastAPI)     │   │  (Click)        │        │
│  │   rumps/PyObjC  │   │   Port 8765     │   │  streamind cmd  │        │
│  └────────┬────────┘   └────────┬────────┘   └────────┬────────┘        │
│           │                     │                     │                  │
│           └─────────────────────┼─────────────────────┘                  │
│                                 ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                        Core Engine                                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │   │
│  │  │   Screen    │  │   Vision    │  │  Reasoning  │              │   │
│  │  │   Capture   │  │   Engine    │  │   Engine    │              │   │
│  │  │   Module    │  │  (Ollama)   │  │  (DeepSeek) │              │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │   │
│  │         │                │                │                      │   │
│  │         └────────────────┼────────────────┘                      │   │
│  │                          ▼                                        │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │                    Context Manager                           │ │   │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │ │   │
│  │  │  │   Frame     │  │   Entity    │  │   History   │         │ │   │
│  │  │  │   Buffer    │  │  Extractor  │  │   Search    │         │ │   │
│  │  │  └─────────────┘  └─────────────┘  └─────────────┘         │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                 │                                        │
│                                 ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                      Storage Layer                                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │   │
│  │  │   SQLite    │  │   Frame     │  │   Config    │              │   │
│  │  │  (History)  │  │   Cache     │  │   (TOML)    │              │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘              │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         External Services                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                     │
│  │   Ollama    │  │   macOS     │  │    KAS      │                     │
│  │  localhost  │  │   APIs      │  │ (optional)  │                     │
│  │   :11434    │  │  (PyObjC)   │  │             │                     │
│  └─────────────┘  └─────────────┘  └─────────────┘                     │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Flow Diagram
```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Screen  │───>│  Frame   │───>│  Hash    │───>│ Changed? │───>│  Vision  │
│ Capture  │    │  Buffer  │    │ Compare  │    │   Yes    │    │ Analysis │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                     │ No            │
                                                     ▼               ▼
                                                ┌──────────┐   ┌──────────┐
                                                │   Skip   │   │  Context │
                                                │Processing│   │  Update  │
                                                └──────────┘   └──────────┘
                                                                    │
        ┌──────────┐    ┌──────────┐    ┌──────────┐               │
        │ Response │<───│ Reasoning│<───│  Query   │<──────────────┘
        │ Display  │    │  Engine  │    │ Received │
        └──────────┘    └──────────┘    └──────────┘
```

### 3.3 Component Interactions
```
┌─────────────────────────────────────────────────────────────────┐
│                        Query Flow                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User: "What's that error?"                                     │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 1. CLI/Menu Bar receives query                          │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 2. Screen Capture takes current frame                   │    │
│  │    - Active window info collected                       │    │
│  │    - Frame hash computed                                │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 3. Vision Engine analyzes screenshot                    │    │
│  │    - Content type detected (code/terminal/browser)      │    │
│  │    - Specialized prompt applied                         │    │
│  │    - llama3.2-vision:11b processes image                │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 4. Context Manager enriches analysis                    │    │
│  │    - Previous frames for comparison                     │    │
│  │    - Extracted entities (errors, files, lines)          │    │
│  │    - Application context                                │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 5. Reasoning Engine (if complex query)                  │    │
│  │    - deepseek-r1:14b for "why/explain/debug"           │    │
│  │    - Chains vision output with reasoning                │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 6. Response formatted and returned                      │    │
│  │    - Streamed for better UX                             │    │
│  │    - Stored in history                                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Technology Decisions

### 4.1 Final Technology Stack

| Component | Technology | Version | Rationale |
|-----------|------------|---------|-----------|
| **Language** | Python | 3.11+ | ML ecosystem, rapid development |
| **Package Manager** | uv | 0.9.24+ | 10-100x faster than pip, already installed |
| **Screen Capture** | mss | 9.0+ | 30x faster than pyautogui on macOS |
| **Image Processing** | Pillow | 10.0+ | Standard, well-supported |
| **Vision Model** | llama3.2-vision:11b | via Ollama | Already installed, proven |
| **Reasoning Model** | deepseek-r1:14b | via Ollama | Already installed, strong reasoning |
| **Window Detection** | PyObjC (AppKit/Quartz) | 10.0+ | Native macOS APIs |
| **Menu Bar UI** | rumps | 0.4.0 | Simple, Python-native |
| **CLI Framework** | Typer + Rich | 0.21+/13.0+ | Modern CLI with type hints, better DX than Click |
| **Logging** | loguru | 0.7.3+ | Zero-config logging, already installed |
| **Retry Logic** | tenacity | 9.1+ | Automatic retries for API calls |
| **Database** | SQLite + aiosqlite | 0.22+ | Async, WAL mode |
| **HTTP Client** | httpx | 0.28+ | Async, modern |
| **Change Detection** | imagehash | 4.3+ | Perceptual hashing |
| **Data Validation** | Pydantic | 2.0+ | Type safety |
| **API Server** | FastAPI | 0.115+ | Optional, for integrations |
| **OCR (Optional)** | rapidocr-onnxruntime | 1.3+ | Already installed |

### 4.2 Decision Rationale

#### Screen Capture: MSS over alternatives
```
Performance Comparison (macOS):
┌────────────────────┬──────────────┬───────────────┐
│ Library            │ Time/Frame   │ Relative      │
├────────────────────┼──────────────┼───────────────┤
│ pyautogui          │ ~150ms       │ 1x (baseline) │
│ Pillow ImageGrab   │ ~120ms       │ 1.25x faster  │
│ mss                │ ~5ms         │ 30x faster    │
│ Native PyObjC      │ ~3ms         │ 50x faster    │
└────────────────────┴──────────────┴───────────────┘
```
**Decision:** Start with MSS for simplicity, upgrade to native if needed.

#### Vision Model: Ollama over MLX
```
┌─────────────────┬────────────────────┬────────────────────┐
│ Factor          │ Ollama             │ MLX-VLM            │
├─────────────────┼────────────────────┼────────────────────┤
│ Installation    │ Already running    │ PyTorch blocked    │
│ Model Quality   │ llama3.2-vision    │ Qwen2-VL (issues)  │
│ API Stability   │ Mature             │ Evolving           │
│ Resource Usage  │ Managed            │ Manual management  │
└─────────────────┴────────────────────┴────────────────────┘
```
**Decision:** Ollama now, consider MLX when stable.

#### Database: SQLite over PostgreSQL
```
StreamMind Requirements:
- Single user
- Local storage
- Simple queries
- Fast startup
- No server process

SQLite fits perfectly. PostgreSQL is overkill.
```

---

## 5. Local Assets Inventory

### 5.1 Hardware Specifications
```
┌─────────────────────────────────────────────────┐
│              Apple M4 Pro System                │
├─────────────────────────────────────────────────┤
│ Chip:     Apple M4 Pro                          │
│ Cores:    14 (10 performance + 4 efficiency)    │
│ Memory:   48 GB unified                         │
│ Neural:   16-core Neural Engine                 │
│ GPU:      20-core GPU                           │
│                                                  │
│ Available for AI:                               │
│ - ~40GB for model loading (leaving 8GB system) │
│ - Neural Engine for MLX acceleration           │
│ - GPU cores for parallel processing            │
└─────────────────────────────────────────────────┘
```

### 5.2 Installed Ollama Models
```bash
$ ollama list
NAME                       SIZE
llama3.2-vision:11b        7.8 GB    ✓ Primary vision model
deepseek-r1:14b            9.0 GB    ✓ Reasoning model
qwen2.5-coder:7b           4.7 GB    ✓ Code analysis backup
qwen2.5:7b                 4.7 GB    ✓ General backup
nomic-embed-text:latest    274 MB    ✓ Embeddings
```

### 5.3 Installed Python Packages (Relevant)
```
┌─────────────────────────────────────────────────────────────┐
│                    AI/ML Packages                            │
├─────────────────────────────────────────────────────────────┤
│ ollama              0.6.1    # Ollama client                │
│ mlx                 0.29.4   # Apple MLX framework          │
│ mlx-lm              0.29.1   # MLX language models          │
│ mlx-vlm             0.3.9    # MLX vision-language          │
│ mlx-whisper         0.4.3    # MLX speech-to-text           │
│ mlx-audio           0.2.9    # MLX audio processing         │
│ langchain           0.3.11   # AI orchestration             │
│ llama-index         0.14.12  # RAG framework                │
│ openai-whisper      20250625 # Whisper STT                  │
│ rapidocr-onnxruntime 1.3.24  # Fast OCR                     │
├─────────────────────────────────────────────────────────────┤
│                    Web/API Packages                          │
├─────────────────────────────────────────────────────────────┤
│ httpx               0.28.1   # Async HTTP client            │
│ fastapi             0.116.2  # API framework                │
│ pydantic            2.x      # Data validation              │
├─────────────────────────────────────────────────────────────┤
│                    Utility Packages                          │
├─────────────────────────────────────────────────────────────┤
│ click               8.2.1    # CLI framework                │
│ rich                13.x     # Terminal formatting          │
│ aiosqlite           0.22.1   # Async SQLite                 │
└─────────────────────────────────────────────────────────────┘
```

### 5.4 Reusable Code from Existing Projects

#### From inference-server/ollama_vision_service.py:
```python
# Can directly adapt this tested code:
class OllamaVisionService:
    def _encode_image(self, image_path: str | Path) -> str
    def analyze_image(self, image_path, prompt, model) -> OllamaVisionResult
    def analyze_image_base64(self, image_base64, prompt, model) -> OllamaVisionResult
    def is_available(self) -> bool
```

#### From knowledge-activation-system:
```python
# Patterns to reuse:
- pydantic-settings configuration
- asyncpg/aiosqlite patterns
- typer CLI structure
- rich console output
```

### 5.5 Related Projects for Integration
```
/Users/d/claude-code/
├── ai-tools/
│   ├── mlx-model-hub/           # Model management
│   │   └── inference-server/    # Has OllamaVisionService!
│   └── streamind/               # This project
└── personal/
    └── knowledge-activation-system/  # Could index screenshots
```

---

## 6. Project Structure

### 6.1 Complete Directory Tree
```
streamind/
├── .github/
│   └── workflows/
│       ├── ci.yml               # Lint, test, typecheck
│       └── release.yml          # Build and release
├── .taskmaster/
│   ├── config.json
│   ├── docs/
│   │   └── prd.txt              # Product requirements
│   └── tasks/
│       └── tasks.json           # Task tracking
├── src/
│   └── streamind/
│       ├── __init__.py          # Package init, version
│       ├── __main__.py          # Entry point
│       ├── cli.py               # Click CLI commands
│       │
│       ├── capture/
│       │   ├── __init__.py
│       │   ├── screen.py        # MSS screen capture
│       │   ├── window.py        # PyObjC window detection
│       │   └── hash.py          # Perceptual hashing
│       │
│       ├── vision/
│       │   ├── __init__.py
│       │   ├── engine.py        # Ollama vision client
│       │   ├── prompts.py       # Content-specific prompts
│       │   └── content_type.py  # Content type detection
│       │
│       ├── reasoning/
│       │   ├── __init__.py
│       │   └── engine.py        # DeepSeek reasoning
│       │
│       ├── context/
│       │   ├── __init__.py
│       │   ├── manager.py       # Context orchestration
│       │   ├── storage.py       # SQLite persistence
│       │   ├── entities.py      # Entity extraction
│       │   └── history.py       # History search
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── server.py        # FastAPI server
│       │   ├── routes.py        # API endpoints
│       │   └── schemas.py       # Pydantic models
│       │
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── menubar.py       # rumps menu bar app
│       │   ├── dialogs.py       # Input dialogs
│       │   └── assets/
│       │       ├── icon.png     # Menu bar icon
│       │       ├── icon_active.png
│       │       └── icon_paused.png
│       │
│       └── config/
│           ├── __init__.py
│           ├── settings.py      # Pydantic settings
│           └── defaults.toml    # Default configuration
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures
│   ├── test_capture/
│   │   ├── test_screen.py
│   │   ├── test_window.py
│   │   └── test_hash.py
│   ├── test_vision/
│   │   ├── test_engine.py
│   │   └── test_prompts.py
│   ├── test_context/
│   │   ├── test_manager.py
│   │   └── test_storage.py
│   └── test_integration/
│       └── test_e2e.py
│
├── scripts/
│   ├── demo.py                  # Demo script
│   ├── benchmark.py             # Performance benchmarks
│   └── build_app.py             # py2app builder
│
├── docs/
│   ├── USER_GUIDE.md
│   ├── DEVELOPER_GUIDE.md
│   └── API_REFERENCE.md
│
├── pyproject.toml               # Project metadata
├── README.md                    # User documentation
├── CLAUDE.md                    # AI context
├── STRATEGY.md                  # Strategy document
├── IMPLEMENTATION_PLAN.md       # This document
├── LICENSE                      # MIT License
└── .gitignore
```

### 6.2 Module Responsibilities

```
┌─────────────────────────────────────────────────────────────────┐
│                        Module Map                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  capture/                                                        │
│  ├── screen.py     → ScreenCapture class, MSS wrapper           │
│  ├── window.py     → WindowDetector, PyObjC integration         │
│  └── hash.py       → FrameHasher, change detection              │
│                                                                  │
│  vision/                                                         │
│  ├── engine.py     → VisionEngine, Ollama client                │
│  ├── prompts.py    → PromptLibrary, content-specific prompts    │
│  └── content_type.py → ContentTypeDetector                      │
│                                                                  │
│  reasoning/                                                      │
│  └── engine.py     → ReasoningEngine, DeepSeek client           │
│                                                                  │
│  context/                                                        │
│  ├── manager.py    → ContextManager, orchestration              │
│  ├── storage.py    → StorageBackend, SQLite operations          │
│  ├── entities.py   → EntityExtractor, pattern matching          │
│  └── history.py    → HistorySearch, time-based queries          │
│                                                                  │
│  api/                                                            │
│  ├── server.py     → create_app(), FastAPI factory              │
│  ├── routes.py     → /analyze, /history, /status                │
│  └── schemas.py    → Request/Response Pydantic models           │
│                                                                  │
│  ui/                                                             │
│  ├── menubar.py    → StreamMindApp(rumps.App)                   │
│  └── dialogs.py    → QueryDialog, SettingsDialog                │
│                                                                  │
│  config/                                                         │
│  ├── settings.py   → Settings(BaseSettings)                     │
│  └── defaults.toml → Default configuration values               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Implementation Phases

### 7.1 Phase Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Implementation Timeline                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Phase 1: Foundation        ████████░░░░░░░░░░░░  Tasks 1-5     │
│  Core capture + vision working                                   │
│                                                                  │
│  Phase 2: Intelligence      ░░░░░░░░████████░░░░  Tasks 6-10    │
│  Smart context + detection                                       │
│                                                                  │
│  Phase 3: Experience        ░░░░░░░░░░░░░░░░████  Tasks 11-15   │
│  Polished UI + advanced features                                 │
│                                                                  │
│  Phase 4: Ship              ░░░░░░░░░░░░░░░░░░██  Tasks 16-20   │
│  Testing + optimization + release                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Phase 1: Foundation (Tasks 1-5)

**Goal:** Basic screen capture and vision analysis working end-to-end

**Entry Criteria:**
- pyproject.toml created
- Ollama running with llama3.2-vision:11b

**Exit Criteria:**
- `streamind ask "What's on screen?"` returns accurate description
- Response time <5 seconds
- Tests passing

**Deliverables:**
1. Project scaffolding complete
2. Screen capture module functional
3. Ollama vision integration working
4. Basic CLI implemented
5. End-to-end test passing

### 7.3 Phase 2: Intelligence (Tasks 6-10)

**Goal:** Smart context management and enhanced analysis

**Entry Criteria:**
- Phase 1 complete
- Basic capture + vision working

**Exit Criteria:**
- Active window name included in analysis
- History stored in SQLite
- Unchanged frames skipped (verified by logs)
- Content-type detection 80%+ accurate

**Deliverables:**
1. Active window detection
2. SQLite storage layer
3. Context manager
4. Content-type prompts
5. Change detection

### 7.4 Phase 3: Experience (Tasks 11-15)

**Goal:** Polished interfaces and advanced features

**Entry Criteria:**
- Phase 2 complete
- Context and storage working

**Exit Criteria:**
- Menu bar app launches and stays in menu bar
- All CLI commands working
- Settings persist between sessions
- Privacy controls functional

**Deliverables:**
1. Full CLI implementation
2. Menu bar application
3. Reasoning engine integration
4. Settings system
5. Privacy controls

### 7.5 Phase 4: Ship (Tasks 16-20)

**Goal:** Production-ready release

**Entry Criteria:**
- Phase 3 complete
- All features implemented

**Exit Criteria:**
- 80%+ test coverage
- Response time <3 seconds
- Documentation complete
- Demo video created
- GitHub release published

**Deliverables:**
1. Test coverage
2. Performance optimization
3. Error handling
4. Documentation
5. Release preparation

---

## 8. Detailed Task Breakdown

### Task 1: Project Setup and Environment Configuration

**Priority:** High
**Dependencies:** None
**Estimated Effort:** 2-3 hours

**Objective:** Create complete project scaffolding with all dependencies

**Subtasks:**
```
1.1 Create pyproject.toml with all dependencies
    - Core: mss, pillow, httpx, click, rich
    - macOS: pyobjc-framework-Quartz, pyobjc-framework-AppKit, rumps
    - Storage: aiosqlite, pydantic, pydantic-settings
    - Analysis: imagehash
    - Optional: fastapi, uvicorn
    - Dev: pytest, pytest-asyncio, ruff, mypy

1.2 Create directory structure
    - src/streamind/ with all subpackages
    - tests/ with test subfolders
    - scripts/, docs/

1.3 Create __init__.py files with proper exports
    - Version in __init__.py
    - Public API exports

1.4 Create __main__.py entry point
    - Allow `python -m streamind`

1.5 Configure development tools
    - ruff configuration in pyproject.toml
    - mypy strict mode configuration
    - pytest async configuration

1.6 Verify environment
    - Test Ollama connectivity
    - Test mss import
    - Test PyObjC import

1.7 Create initial conftest.py with fixtures
```

**Acceptance Criteria:**
- [ ] `pip install -e .` succeeds
- [ ] `python -m streamind --help` shows help
- [ ] `pytest` runs (even with no tests)
- [ ] `ruff check src/` passes
- [ ] Ollama models accessible

**Code Template:**
```python
# src/streamind/__init__.py
"""StreamMind - Real-time screen analysis with local AI."""

__version__ = "0.1.0"
__all__ = ["ScreenCapture", "VisionEngine", "ContextManager"]
```

---

### Task 2: Screen Capture Module

**Priority:** High
**Dependencies:** Task 1
**Estimated Effort:** 3-4 hours

**Objective:** Implement efficient screen capture with MSS

**Subtasks:**
```
2.1 Create ScreenCapture class
    - __init__ with monitor selection
    - capture_screen() -> PIL.Image
    - capture_monitor(monitor_id) -> PIL.Image
    - get_monitors() -> list[Monitor]

2.2 Add frame caching
    - Store last N frames in memory
    - Configurable cache size

2.3 Add continuous capture mode
    - start_continuous(callback, interval)
    - stop()
    - Background thread management

2.4 Handle errors gracefully
    - Permission errors
    - Monitor not found
    - Memory issues

2.5 Write tests
    - Test single capture
    - Test multiple monitors
    - Test error handling
```

**Acceptance Criteria:**
- [ ] Single capture completes in <50ms
- [ ] Multi-monitor support works
- [ ] Continuous capture doesn't leak memory
- [ ] Tests pass

**Code Template:**
```python
# src/streamind/capture/screen.py
"""Screen capture using MSS library."""

import mss
import mss.tools
from PIL import Image
from dataclasses import dataclass
from typing import Callable, Optional
import threading
import time


@dataclass
class Monitor:
    """Monitor information."""
    id: int
    left: int
    top: int
    width: int
    height: int
    is_primary: bool


class ScreenCapture:
    """Efficient screen capture using MSS."""

    def __init__(self, cache_size: int = 10):
        self._sct = mss.mss()
        self._cache: list[Image.Image] = []
        self._cache_size = cache_size
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def get_monitors(self) -> list[Monitor]:
        """Get list of available monitors."""
        monitors = []
        for i, m in enumerate(self._sct.monitors[1:], 1):  # Skip "all monitors" entry
            monitors.append(Monitor(
                id=i,
                left=m["left"],
                top=m["top"],
                width=m["width"],
                height=m["height"],
                is_primary=(i == 1)
            ))
        return monitors

    def capture_screen(self, monitor: int = 1) -> Image.Image:
        """Capture screen and return as PIL Image.

        Args:
            monitor: Monitor ID (1 = primary, 2+ = additional)

        Returns:
            PIL Image of screen capture
        """
        sct_img = self._sct.grab(self._sct.monitors[monitor])
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

        # Cache management
        self._cache.append(img)
        if len(self._cache) > self._cache_size:
            self._cache.pop(0)

        return img

    def start_continuous(
        self,
        callback: Callable[[Image.Image], None],
        interval: float = 1.0
    ) -> None:
        """Start continuous screen capture in background thread.

        Args:
            callback: Function called with each new frame
            interval: Seconds between captures
        """
        if self._running:
            return

        self._running = True

        def capture_loop():
            while self._running:
                try:
                    frame = self.capture_screen()
                    callback(frame)
                except Exception as e:
                    # Log but don't crash
                    pass
                time.sleep(interval)

        self._thread = threading.Thread(target=capture_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop continuous capture."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def get_cached_frames(self) -> list[Image.Image]:
        """Get cached frames."""
        return self._cache.copy()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop()
```

---

### Task 3: Ollama Vision Integration

**Priority:** High
**Dependencies:** Task 1
**Estimated Effort:** 3-4 hours

**Objective:** Create async Ollama vision client

**Subtasks:**
```
3.1 Create VisionEngine class
    - Async httpx client
    - Connection pooling
    - Timeout handling

3.2 Implement analyze() method
    - Image encoding to base64
    - Request formatting
    - Response parsing

3.3 Add streaming support
    - Server-sent events parsing
    - Async generator for streaming

3.4 Add health check
    - is_available() method
    - Model availability check

3.5 Write tests
    - Mock Ollama responses
    - Test timeout handling
    - Test streaming
```

**Acceptance Criteria:**
- [ ] analyze() returns result in <5 seconds for simple images
- [ ] Streaming works correctly
- [ ] Graceful handling when Ollama unavailable
- [ ] Tests pass

**Code Template:**
```python
# src/streamind/vision/engine.py
"""Vision analysis using Ollama llama3.2-vision."""

import base64
import httpx
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncGenerator, Optional
from PIL import Image
import io

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_VISION_MODEL = "llama3.2-vision:11b"
DEFAULT_TIMEOUT = 120.0  # 2 minutes for complex analysis


@dataclass
class VisionResult:
    """Result from vision analysis."""
    text: str
    model: str
    total_duration_ms: Optional[float] = None
    tokens_generated: Optional[int] = None


class VisionEngine:
    """Async vision analysis using Ollama."""

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = DEFAULT_VISION_MODEL,
        timeout: float = DEFAULT_TIMEOUT
    ):
        self.base_url = base_url
        self.model = model
        self._client = httpx.AsyncClient(timeout=timeout)

    @staticmethod
    def encode_image(image: Image.Image) -> str:
        """Encode PIL Image to base64."""
        # Resize if too large (max 1120x1120 for llama3.2-vision)
        max_size = 1120
        if image.width > max_size or image.height > max_size:
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Ollama request failed, retrying ({retry_state.attempt_number}/3)..."
        )
    )
    async def analyze(
        self,
        image: Image.Image,
        prompt: str,
        context: Optional[str] = None
    ) -> VisionResult:
        """Analyze an image with a text prompt.

        Args:
            image: PIL Image to analyze
            prompt: Question or instruction about the image
            context: Optional additional context (e.g., active window info)

        Returns:
            VisionResult with analysis text

        Note:
            Automatically retries up to 3 times on timeout/connection errors.
        """
        image_b64 = self.encode_image(image)

        # Build full prompt with context
        full_prompt = prompt
        if context:
            full_prompt = f"Context: {context}\n\n{prompt}"

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "images": [image_b64],
            "stream": False,
        }

        try:
            response = await self._client.post(
                f"{self.base_url}/api/generate",
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            return VisionResult(
                text=data.get("response", ""),
                model=data.get("model", self.model),
                total_duration_ms=(
                    data.get("total_duration", 0) / 1_000_000
                    if data.get("total_duration") else None
                ),
                tokens_generated=data.get("eval_count"),
            )

        except httpx.TimeoutException:
            logger.error("Ollama request timed out")
            raise
        except httpx.HTTPError as e:
            logger.error(f"Ollama API error: {e}")
            raise

    async def analyze_stream(
        self,
        image: Image.Image,
        prompt: str,
        context: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Stream analysis results token by token.

        Yields:
            Text tokens as they are generated
        """
        image_b64 = self.encode_image(image)

        full_prompt = prompt
        if context:
            full_prompt = f"Context: {context}\n\n{prompt}"

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "images": [image_b64],
            "stream": True,
        }

        async with self._client.stream(
            "POST",
            f"{self.base_url}/api/generate",
            json=payload
        ) as response:
            async for line in response.aiter_lines():
                if line:
                    import json
                    data = json.loads(line)
                    if "response" in data:
                        yield data["response"]

    async def is_available(self) -> bool:
        """Check if Ollama is running and vision model available."""
        try:
            response = await self._client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
            return any(
                self.model in m.get("name", "")
                for m in models
            )
        except Exception:
            return False

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
```

---

### Task 4: Basic CLI Implementation

**Priority:** High
**Dependencies:** Tasks 2, 3
**Estimated Effort:** 2-3 hours

**Objective:** Create functional CLI with `ask` command

**Subtasks:**
```
4.1 Create CLI structure with Click
    - Main group
    - ask command
    - --help messages

4.2 Implement ask command
    - Capture current screen
    - Send to vision engine
    - Display result with Rich

4.3 Add loading indicator
    - Spinner while processing
    - Progress feedback

4.4 Add error handling
    - Ollama not available
    - Capture permission denied

4.5 Write CLI tests
```

**Acceptance Criteria:**
- [ ] `streamind ask "What's on screen?"` works
- [ ] Beautiful output with Rich
- [ ] Clear error messages
- [ ] `--help` shows usage

**Code Template:**
```python
# src/streamind/cli.py
"""StreamMind CLI interface using Typer + Rich."""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from loguru import logger

from streamind.capture.screen import ScreenCapture
from streamind.vision.engine import VisionEngine

# Initialize Typer app
app = typer.Typer(
    name="streamind",
    help="StreamMind - Real-time screen analysis with local AI",
    add_completion=False,
)
console = Console()


@app.command()
def ask(
    query: str = typer.Argument(..., help="Question about your screen"),
    monitor: int = typer.Option(1, "--monitor", "-m", help="Monitor to capture (1=primary)"),
    stream: bool = typer.Option(False, "--stream", "-s", help="Stream response tokens"),
):
    """Ask a question about your current screen.

    Example: streamind ask "What's that error?"
    """
    asyncio.run(_ask_async(query, monitor, stream))


@app.command()
def status():
    """Show StreamMind status and Ollama connectivity."""
    asyncio.run(_status_async())


@app.command()
def history(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of entries"),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Search term"),
):
    """Show analysis history."""
    asyncio.run(_history_async(limit, search))


async def _ask_async(query: str, monitor: int, stream: bool):
    """Async implementation of ask command."""
    from tenacity import retry, stop_after_attempt, wait_exponential

    # Check Ollama availability
    async with VisionEngine() as vision:
        if not await vision.is_available():
            console.print(
                "[red]Error:[/red] Ollama is not running or vision model not found.\n"
                "Start Ollama with: [cyan]ollama serve[/cyan]"
            )
            raise typer.Exit(1)

        # Capture screen
        with console.status("[cyan]Capturing screen...", spinner="dots"):
            capture = ScreenCapture()
            try:
                image = capture.capture_screen(monitor)
            except Exception as e:
                logger.error(f"Screen capture failed: {e}")
                console.print(f"[red]Error capturing screen:[/red] {e}")
                console.print(
                    "You may need to grant screen recording permission in "
                    "System Preferences > Privacy & Security > Screen Recording"
                )
                raise typer.Exit(1)

        # Analyze
        if stream:
            console.print(f"\n[bold cyan]StreamMind:[/bold cyan] ", end="")
            async for token in vision.analyze_stream(image, query):
                console.print(token, end="")
            console.print("\n")
        else:
            with console.status("[cyan]Analyzing...", spinner="dots"):
                result = await vision.analyze(image, query)

            # Display result
            console.print()
            console.print(Panel(
                result.text,
                title="[bold cyan]StreamMind[/bold cyan]",
                border_style="cyan"
            ))

            if result.total_duration_ms:
                console.print(
                    f"[dim]Processed in {result.total_duration_ms:.0f}ms "
                    f"({result.tokens_generated or '?'} tokens)[/dim]"
                )


async def _status_async():
    """Show status information."""
    async with VisionEngine() as vision:
        available = await vision.is_available()

    if available:
        console.print("[green]✓[/green] Ollama is running")
        console.print(f"[green]✓[/green] Vision model available")
    else:
        console.print("[red]✗[/red] Ollama not available")
        console.print("  Start with: [cyan]ollama serve[/cyan]")


async def _history_async(limit: int, search: Optional[str]):
    """Show analysis history."""
    from streamind.context.storage import StorageBackend
    from rich.table import Table

    async with StorageBackend() as storage:
        if search:
            records = await storage.search(search, limit)
        else:
            records = await storage.get_recent(limit)

    if not records:
        console.print("[dim]No history found[/dim]")
        return

    table = Table(title="Recent Analyses")
    table.add_column("Time", style="dim")
    table.add_column("Query")
    table.add_column("App")
    table.add_column("Response", max_width=50)

    for r in records:
        table.add_row(
            r.timestamp.strftime("%H:%M"),
            r.query[:30],
            r.app_name or "-",
            r.response[:50] + "..." if len(r.response) > 50 else r.response
        )

    console.print(table)


# Entry point
def main():
    app()


if __name__ == "__main__":
    main()
```

---

### Task 5: End-to-End Integration Testing

**Priority:** High
**Dependencies:** Task 4
**Estimated Effort:** 2-3 hours

**Objective:** Verify complete pipeline works

**Subtasks:**
```
5.1 Create integration test suite
    - Test with real Ollama (skip if unavailable)
    - Test with mock Ollama

5.2 Measure performance
    - Time capture
    - Time analysis
    - Total response time

5.3 Test various screen content
    - Code editor
    - Terminal
    - Browser
    - Plain desktop

5.4 Document findings
    - Performance characteristics
    - Edge cases discovered

5.5 Fix any issues found
```

**Acceptance Criteria:**
- [ ] Integration tests pass
- [ ] Response time <5 seconds documented
- [ ] Edge cases handled
- [ ] README updated with test results

---

### Task 6: Active Window Detection

**Priority:** Medium
**Dependencies:** Task 1
**Estimated Effort:** 3-4 hours

**Objective:** Detect currently focused window using PyObjC

**Code Template:**
```python
# src/streamind/capture/window.py
"""Active window detection using PyObjC."""

from dataclasses import dataclass
from typing import Optional
import logging

try:
    from AppKit import NSWorkspace
    from Quartz import (
        CGWindowListCopyWindowInfo,
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID,
        kCGWindowOwnerPID,
        kCGWindowOwnerName,
        kCGWindowName,
        kCGWindowBounds,
        kCGWindowLayer,
    )
    PYOBJC_AVAILABLE = True
except ImportError:
    PYOBJC_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class WindowInfo:
    """Information about a window."""
    app_name: str
    window_title: Optional[str]
    pid: int
    bounds: dict  # {X, Y, Width, Height}
    layer: int


class WindowDetector:
    """Detect active window and get window information."""

    def __init__(self):
        if not PYOBJC_AVAILABLE:
            logger.warning(
                "PyObjC not available. Window detection disabled. "
                "Install with: pip install pyobjc-framework-Quartz pyobjc-framework-AppKit"
            )

    def get_active_app(self) -> Optional[str]:
        """Get the name of the currently active application."""
        if not PYOBJC_AVAILABLE:
            return None

        try:
            active_app = NSWorkspace.sharedWorkspace().frontmostApplication()
            return active_app.localizedName()
        except Exception as e:
            logger.error(f"Error getting active app: {e}")
            return None

    def get_active_window(self) -> Optional[WindowInfo]:
        """Get information about the currently active window."""
        if not PYOBJC_AVAILABLE:
            return None

        try:
            # Get active app
            active_app = NSWorkspace.sharedWorkspace().frontmostApplication()
            active_pid = active_app.processIdentifier()
            app_name = active_app.localizedName()

            # Get windows
            windows = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly,
                kCGNullWindowID
            )

            # Find window belonging to active app
            for window in windows:
                if window.get(kCGWindowOwnerPID) == active_pid:
                    # Skip layer 0 windows (desktop, etc.)
                    if window.get(kCGWindowLayer, 0) == 0:
                        continue

                    return WindowInfo(
                        app_name=app_name,
                        window_title=window.get(kCGWindowName),
                        pid=active_pid,
                        bounds=dict(window.get(kCGWindowBounds, {})),
                        layer=window.get(kCGWindowLayer, 0)
                    )

            # Fallback if no window found
            return WindowInfo(
                app_name=app_name,
                window_title=None,
                pid=active_pid,
                bounds={},
                layer=0
            )

        except Exception as e:
            logger.error(f"Error getting active window: {e}")
            return None

    def get_all_windows(self) -> list[WindowInfo]:
        """Get information about all visible windows."""
        if not PYOBJC_AVAILABLE:
            return []

        try:
            windows = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly,
                kCGNullWindowID
            )

            result = []
            for window in windows:
                # Skip system windows (layer 0)
                if window.get(kCGWindowLayer, 0) == 0:
                    continue

                result.append(WindowInfo(
                    app_name=window.get(kCGWindowOwnerName, "Unknown"),
                    window_title=window.get(kCGWindowName),
                    pid=window.get(kCGWindowOwnerPID, 0),
                    bounds=dict(window.get(kCGWindowBounds, {})),
                    layer=window.get(kCGWindowLayer, 0)
                ))

            return result

        except Exception as e:
            logger.error(f"Error getting windows: {e}")
            return []

    def format_context(self) -> str:
        """Format window info as context string for vision model."""
        window = self.get_active_window()
        if not window:
            return ""

        parts = [f"Active application: {window.app_name}"]
        if window.window_title:
            parts.append(f"Window title: {window.window_title}")

        return "\n".join(parts)
```

---

### Task 7: SQLite Storage Layer

**Priority:** Medium
**Dependencies:** Task 1
**Estimated Effort:** 3-4 hours

**Code Template:**
```python
# src/streamind/context/storage.py
"""SQLite storage for history and context."""

import aiosqlite
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
import json
import logging

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.home() / ".streamind" / "history.db"


@dataclass
class AnalysisRecord:
    """Stored analysis record."""
    id: int
    timestamp: datetime
    query: str
    response: str
    app_name: Optional[str]
    window_title: Optional[str]
    content_type: Optional[str]
    duration_ms: Optional[float]


class StorageBackend:
    """Async SQLite storage for StreamMind."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Initialize database and create tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(self.db_path)

        # Enable WAL mode for better concurrent access
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA synchronous=NORMAL")
        await self._connection.execute("PRAGMA cache_size=-64000")  # 64MB

        # Create tables
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                query TEXT NOT NULL,
                response TEXT NOT NULL,
                app_name TEXT,
                window_title TEXT,
                content_type TEXT,
                duration_ms REAL,
                metadata TEXT
            )
        """)

        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
        """)

        # Create indexes
        await self._connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_analyses_timestamp
            ON analyses(timestamp DESC)
        """)

        await self._connection.commit()

    async def save_analysis(
        self,
        query: str,
        response: str,
        app_name: Optional[str] = None,
        window_title: Optional[str] = None,
        content_type: Optional[str] = None,
        duration_ms: Optional[float] = None,
        metadata: Optional[dict] = None
    ) -> int:
        """Save an analysis record."""
        cursor = await self._connection.execute(
            """
            INSERT INTO analyses
            (timestamp, query, response, app_name, window_title, content_type, duration_ms, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().timestamp(),
                query,
                response,
                app_name,
                window_title,
                content_type,
                duration_ms,
                json.dumps(metadata) if metadata else None
            )
        )
        await self._connection.commit()
        return cursor.lastrowid

    async def get_recent(self, limit: int = 10) -> list[AnalysisRecord]:
        """Get recent analysis records."""
        async with self._connection.execute(
            """
            SELECT id, timestamp, query, response, app_name, window_title,
                   content_type, duration_ms
            FROM analyses
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()

        return [
            AnalysisRecord(
                id=row[0],
                timestamp=datetime.fromtimestamp(row[1]),
                query=row[2],
                response=row[3],
                app_name=row[4],
                window_title=row[5],
                content_type=row[6],
                duration_ms=row[7]
            )
            for row in rows
        ]

    async def search(
        self,
        query: str,
        limit: int = 20
    ) -> list[AnalysisRecord]:
        """Search analyses by query or response text."""
        search_term = f"%{query}%"
        async with self._connection.execute(
            """
            SELECT id, timestamp, query, response, app_name, window_title,
                   content_type, duration_ms
            FROM analyses
            WHERE query LIKE ? OR response LIKE ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (search_term, search_term, limit)
        ) as cursor:
            rows = await cursor.fetchall()

        return [
            AnalysisRecord(
                id=row[0],
                timestamp=datetime.fromtimestamp(row[1]),
                query=row[2],
                response=row[3],
                app_name=row[4],
                window_title=row[5],
                content_type=row[6],
                duration_ms=row[7]
            )
            for row in rows
        ]

    async def delete_older_than(self, days: int) -> int:
        """Delete records older than N days."""
        cutoff = datetime.now().timestamp() - (days * 86400)
        cursor = await self._connection.execute(
            "DELETE FROM analyses WHERE timestamp < ?",
            (cutoff,)
        )
        await self._connection.commit()
        return cursor.rowcount

    async def clear_all(self) -> None:
        """Delete all records."""
        await self._connection.execute("DELETE FROM analyses")
        await self._connection.commit()

    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, *args):
        await self.close()
```

---

### Task 8: Context Manager Implementation

**Priority:** Medium
**Dependencies:** Tasks 6, 7
**Estimated Effort:** 3-4 hours

### Task 9: Content-Type Detection and Specialized Prompts

**Priority:** Medium
**Dependencies:** Task 3
**Estimated Effort:** 2-3 hours

**Code Template:**
```python
# src/streamind/vision/prompts.py
"""Content-specific prompts for vision analysis."""

from enum import Enum


class ContentType(Enum):
    """Types of screen content."""
    CODE = "code"
    TERMINAL = "terminal"
    BROWSER = "browser"
    DOCUMENT = "document"
    CHAT = "chat"
    UNKNOWN = "unknown"


# Prompts optimized for each content type
CONTENT_PROMPTS = {
    ContentType.CODE: {
        "default": """You are analyzing a code editor screenshot.
Focus on:
- Error messages and their locations (file, line number)
- Code syntax and structure
- Variable names and function calls
- Any highlighted or selected text

Be specific about file names, line numbers, and exact error messages when visible.""",

        "error": """Analyze this code editor screenshot for errors.
Identify:
1. The exact error message
2. The file name and line number
3. The likely cause of the error
4. A suggested fix

Be concise and actionable.""",
    },

    ContentType.TERMINAL: {
        "default": """You are analyzing a terminal/command line screenshot.
Focus on:
- Command output and exit codes
- Error messages
- File paths and directory structure
- Any warnings or important information

Quote exact output when relevant.""",

        "error": """Analyze this terminal output for errors.
Identify:
1. The command that was run
2. The error message
3. What went wrong
4. How to fix it""",
    },

    ContentType.BROWSER: {
        "default": """You are analyzing a web browser screenshot.
Focus on:
- Page content and structure
- Forms and input fields
- Error messages or notifications
- Navigation elements

Describe what the user is looking at.""",

        "error": """Analyze this browser screenshot for issues.
Look for:
1. Error pages (404, 500, etc.)
2. Form validation errors
3. JavaScript errors in console
4. Network failures""",
    },

    ContentType.DOCUMENT: {
        "default": """You are analyzing a document screenshot.
Focus on:
- Text content
- Formatting and structure
- Tables or data
- Any highlighted sections""",
    },

    ContentType.UNKNOWN: {
        "default": """Analyze this screenshot and describe what you see.
Focus on:
- Main content and purpose
- Any text or information visible
- Interactive elements
- Current state or context""",
    }
}


def get_prompt(
    content_type: ContentType,
    query_type: str = "default"
) -> str:
    """Get appropriate prompt for content type and query.

    Args:
        content_type: Type of screen content
        query_type: Type of query (default, error, etc.)

    Returns:
        System prompt string
    """
    prompts = CONTENT_PROMPTS.get(content_type, CONTENT_PROMPTS[ContentType.UNKNOWN])
    return prompts.get(query_type, prompts["default"])


def detect_query_type(query: str) -> str:
    """Detect the type of query from user input.

    Args:
        query: User's question

    Returns:
        Query type string
    """
    query_lower = query.lower()

    error_keywords = ["error", "bug", "wrong", "fail", "broken", "issue", "problem"]
    if any(kw in query_lower for kw in error_keywords):
        return "error"

    return "default"
```

---

### Task 10: Change Detection for Efficiency

**Priority:** Medium
**Dependencies:** Task 2
**Estimated Effort:** 2-3 hours

**Code Template:**
```python
# src/streamind/capture/hash.py
"""Perceptual hashing for change detection."""

import imagehash
from PIL import Image
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Threshold for considering frames different
# <10 = same image, >10 = different image
DEFAULT_THRESHOLD = 10


@dataclass
class HashResult:
    """Result of frame hashing."""
    hash_value: str
    changed: bool
    difference: int


class FrameHasher:
    """Perceptual hashing for screen change detection."""

    def __init__(self, threshold: int = DEFAULT_THRESHOLD):
        self.threshold = threshold
        self._last_hash: Optional[imagehash.ImageHash] = None

    def compute_hash(self, image: Image.Image) -> imagehash.ImageHash:
        """Compute dHash (difference hash) for image.

        dHash is fast and effective for screen change detection.
        """
        return imagehash.dhash(image)

    def has_changed(self, image: Image.Image) -> HashResult:
        """Check if image has changed from last frame.

        Args:
            image: Current frame as PIL Image

        Returns:
            HashResult with change information
        """
        current_hash = self.compute_hash(image)

        if self._last_hash is None:
            # First frame, always "changed"
            self._last_hash = current_hash
            return HashResult(
                hash_value=str(current_hash),
                changed=True,
                difference=0
            )

        # Compute Hamming distance
        difference = current_hash - self._last_hash
        changed = difference > self.threshold

        if changed:
            self._last_hash = current_hash

        return HashResult(
            hash_value=str(current_hash),
            changed=changed,
            difference=difference
        )

    def reset(self):
        """Reset hash state."""
        self._last_hash = None

    def set_threshold(self, threshold: int):
        """Update change detection threshold."""
        self.threshold = threshold
```

---

### Task 11: Full CLI Implementation

**Priority:** Medium
**Dependencies:** Tasks 4, 7

**Objective:** Complete CLI with all commands

**Subtasks:**
```
11.1 Add serve command
    - Background daemon mode
    - Configurable capture interval
    - PID file for process management

11.2 Add config command
    - Show current configuration
    - Set individual values
    - Reset to defaults

11.3 Add privacy command
    - Blocklist management
    - Pause/resume capture
    - Clear all data
```

**Code Template:**
```python
# Additional CLI commands (add to cli.py)

@app.command()
def serve(
    interval: float = typer.Option(1.0, "--interval", "-i", help="Capture interval (seconds)"),
    background: bool = typer.Option(False, "--background", "-b", help="Run in background"),
):
    """Start StreamMind daemon for continuous capture."""
    from streamind.capture.screen import ScreenCapture
    from streamind.capture.hash import FrameHasher

    if background:
        import daemon
        with daemon.DaemonContext():
            _run_daemon(interval)
    else:
        _run_daemon(interval)


def _run_daemon(interval: float):
    """Run capture daemon."""
    capture = ScreenCapture()
    hasher = FrameHasher()

    console.print(f"[green]StreamMind daemon started[/green] (interval: {interval}s)")
    console.print("Press Ctrl+C to stop")

    try:
        while True:
            frame = capture.capture_screen()
            result = hasher.has_changed(frame)
            if result.changed:
                logger.debug(f"Frame changed (diff: {result.difference})")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Daemon stopped[/yellow]")


@app.command()
def config(
    key: Optional[str] = typer.Argument(None, help="Config key to get/set"),
    value: Optional[str] = typer.Argument(None, help="Value to set"),
    reset: bool = typer.Option(False, "--reset", help="Reset to defaults"),
):
    """Manage StreamMind configuration."""
    from streamind.config.settings import Settings, save_settings

    settings = Settings()

    if reset:
        settings = Settings()
        save_settings(settings)
        console.print("[green]Configuration reset to defaults[/green]")
        return

    if key is None:
        # Show all settings
        console.print(Panel(str(settings.model_dump_json(indent=2)), title="Configuration"))
        return

    if value is None:
        # Get specific value
        val = getattr(settings, key, None)
        console.print(f"{key} = {val}")
    else:
        # Set value
        setattr(settings, key, value)
        save_settings(settings)
        console.print(f"[green]Set {key} = {value}[/green]")
```

---

### Task 12: Menu Bar Application

**Priority:** Medium
**Dependencies:** Tasks 2, 3, 6

**Objective:** Create rumps-based menu bar app

**Code Template:**
```python
# src/streamind/ui/menubar.py
"""macOS menu bar application using rumps."""

import rumps
import asyncio
from pathlib import Path
from loguru import logger

from streamind.capture.screen import ScreenCapture
from streamind.capture.window import WindowDetector
from streamind.vision.engine import VisionEngine


class StreamMindApp(rumps.App):
    """Menu bar application for StreamMind."""

    def __init__(self):
        super().__init__(
            "StreamMind",
            icon=str(Path(__file__).parent / "assets" / "icon.png"),
            quit_button=None,  # Custom quit
        )

        self.capture = ScreenCapture()
        self.window_detector = WindowDetector()
        self._paused = False
        self._last_response = None

        # Build menu
        self.menu = [
            rumps.MenuItem("Ask Question...", callback=self.ask_question),
            rumps.MenuItem("Last Response", callback=self.show_last),
            None,  # Separator
            rumps.MenuItem("Pause", callback=self.toggle_pause),
            rumps.MenuItem("Settings...", callback=self.open_settings),
            None,
            rumps.MenuItem("Quit StreamMind", callback=self.quit_app),
        ]

    @rumps.clicked("Ask Question...")
    def ask_question(self, _):
        """Open query dialog."""
        response = rumps.Window(
            title="StreamMind",
            message="What would you like to know about your screen?",
            default_text="",
            ok="Ask",
            cancel="Cancel",
            dimensions=(400, 100),
        ).run()

        if response.clicked:
            query = response.text
            if query.strip():
                self._process_query(query)

    def _process_query(self, query: str):
        """Process a query asynchronously."""
        asyncio.run(self._async_process(query))

    async def _async_process(self, query: str):
        """Async query processing."""
        # Get context
        window = self.window_detector.get_active_window()
        context = f"Active app: {window.app_name}" if window else None

        # Capture and analyze
        image = self.capture.capture_screen()

        async with VisionEngine() as vision:
            result = await vision.analyze(image, query, context)

        self._last_response = result.text

        # Show notification
        rumps.notification(
            title="StreamMind",
            subtitle=query[:50],
            message=result.text[:200],
        )

    @rumps.clicked("Pause")
    def toggle_pause(self, sender):
        """Toggle capture pause."""
        self._paused = not self._paused
        sender.title = "Resume" if self._paused else "Pause"
        self.icon = "icon_paused.png" if self._paused else "icon.png"

    @rumps.clicked("Last Response")
    def show_last(self, _):
        """Show last response in dialog."""
        if self._last_response:
            rumps.alert(
                title="Last Response",
                message=self._last_response,
            )
        else:
            rumps.alert("No recent response")

    @rumps.clicked("Quit StreamMind")
    def quit_app(self, _):
        """Quit application."""
        rumps.quit_application()


def main():
    """Run menu bar app."""
    StreamMindApp().run()


if __name__ == "__main__":
    main()
```

---

### Task 13: Reasoning Engine Integration

**Priority:** Medium
**Dependencies:** Task 3

**Objective:** Add DeepSeek R1 reasoning for complex queries

**Code Template:**
```python
# src/streamind/reasoning/engine.py
"""Reasoning engine using DeepSeek R1."""

import httpx
from dataclasses import dataclass
from typing import Optional, AsyncGenerator
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_REASONING_MODEL = "deepseek-r1:14b"

# Keywords that trigger reasoning engine
REASONING_KEYWORDS = ["why", "explain", "debug", "how", "reason", "analyze", "understand"]


@dataclass
class ReasoningResult:
    """Result from reasoning analysis."""
    text: str
    model: str
    thinking: Optional[str] = None  # DeepSeek R1 thinking process
    total_duration_ms: Optional[float] = None


def should_use_reasoning(query: str) -> bool:
    """Check if query should use reasoning engine."""
    query_lower = query.lower()
    return any(kw in query_lower for kw in REASONING_KEYWORDS)


class ReasoningEngine:
    """Reasoning engine using DeepSeek R1 for complex analysis."""

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = DEFAULT_REASONING_MODEL,
    ):
        self.base_url = base_url
        self.model = model
        self._client = httpx.AsyncClient(timeout=180.0)  # 3 minutes for reasoning

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
    async def reason(
        self,
        vision_output: str,
        query: str,
        context: Optional[str] = None,
    ) -> ReasoningResult:
        """Apply reasoning to vision analysis output.

        Args:
            vision_output: Text output from vision model
            query: Original user query
            context: Additional context (app, window, etc.)

        Returns:
            ReasoningResult with deeper analysis
        """
        prompt = f"""Based on this screen analysis, answer the user's question with detailed reasoning.

Screen Analysis:
{vision_output}

User Question: {query}

{f"Context: {context}" if context else ""}

Provide a clear, actionable answer. If this is an error, explain the cause and solution."""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        try:
            response = await self._client.post(
                f"{self.base_url}/api/generate",
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            return ReasoningResult(
                text=data.get("response", ""),
                model=data.get("model", self.model),
                total_duration_ms=data.get("total_duration", 0) / 1_000_000,
            )

        except Exception as e:
            logger.error(f"Reasoning failed: {e}")
            raise

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
```

---

### Task 14: Settings and Configuration

**Priority:** Medium
**Dependencies:** Task 1

**Objective:** Implement persistent settings with pydantic-settings

**(Already included in Section 11 - Configuration System)**

---

### Task 15: Privacy Controls

**Priority:** Medium
**Dependencies:** Task 6

**Objective:** Implement privacy features

**Code Template:**
```python
# src/streamind/privacy/manager.py
"""Privacy controls for StreamMind."""

from dataclasses import dataclass, field
from typing import Set
from pathlib import Path
import json
from loguru import logger


@dataclass
class PrivacyManager:
    """Manage privacy controls."""

    blocklist: Set[str] = field(default_factory=lambda: {"1Password", "Keychain Access"})
    auto_pause_apps: Set[str] = field(default_factory=set)
    _paused: bool = False
    _config_path: Path = Path.home() / ".streamind" / "privacy.json"

    def __post_init__(self):
        self._load()

    def should_capture(self, app_name: str) -> bool:
        """Check if capture is allowed for app."""
        if self._paused:
            logger.debug("Capture paused")
            return False
        if app_name in self.blocklist:
            logger.debug(f"App blocklisted: {app_name}")
            return False
        return True

    def add_to_blocklist(self, app_name: str):
        """Add app to blocklist."""
        self.blocklist.add(app_name)
        self._save()
        logger.info(f"Added to blocklist: {app_name}")

    def remove_from_blocklist(self, app_name: str):
        """Remove app from blocklist."""
        self.blocklist.discard(app_name)
        self._save()
        logger.info(f"Removed from blocklist: {app_name}")

    def pause(self):
        """Pause all capture."""
        self._paused = True
        logger.info("Capture paused")

    def resume(self):
        """Resume capture."""
        self._paused = False
        logger.info("Capture resumed")

    def _save(self):
        """Save privacy settings."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w") as f:
            json.dump({
                "blocklist": list(self.blocklist),
                "auto_pause_apps": list(self.auto_pause_apps),
            }, f)

    def _load(self):
        """Load privacy settings."""
        if self._config_path.exists():
            with open(self._config_path) as f:
                data = json.load(f)
                self.blocklist = set(data.get("blocklist", []))
                self.auto_pause_apps = set(data.get("auto_pause_apps", []))
```

---

### Task 16: Test Coverage

**Priority:** High
**Dependencies:** All previous tasks

**Objective:** Achieve 80%+ test coverage

**Test Structure:**
```python
# tests/conftest.py
"""Shared test fixtures."""

import pytest
import pytest_asyncio
from pathlib import Path
from PIL import Image
from unittest.mock import AsyncMock, MagicMock
import tempfile


@pytest.fixture
def sample_image():
    """Create sample test image."""
    return Image.new("RGB", (800, 600), color="white")


@pytest.fixture
def temp_db():
    """Temporary database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield Path(f.name)


@pytest_asyncio.fixture
async def mock_vision_engine():
    """Mock vision engine."""
    engine = AsyncMock()
    engine.analyze.return_value = MagicMock(
        text="Test response",
        model="llama3.2-vision:11b",
        total_duration_ms=1000,
    )
    engine.is_available.return_value = True
    return engine


# tests/test_capture/test_screen.py
"""Tests for screen capture."""

import pytest
from streamind.capture.screen import ScreenCapture, Monitor


class TestScreenCapture:
    def test_get_monitors(self):
        """Test monitor enumeration."""
        capture = ScreenCapture()
        monitors = capture.get_monitors()
        assert len(monitors) >= 1
        assert monitors[0].is_primary

    def test_capture_screen(self, sample_image):
        """Test screen capture returns image."""
        capture = ScreenCapture()
        # Note: This will fail if no display attached
        try:
            image = capture.capture_screen()
            assert image.width > 0
            assert image.height > 0
        except Exception:
            pytest.skip("No display available")


# tests/test_vision/test_engine.py
"""Tests for vision engine."""

import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_analyze_with_mock(sample_image):
    """Test vision analysis with mocked Ollama."""
    from streamind.vision.engine import VisionEngine

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock()
        mock_post.return_value.json.return_value = {
            "response": "Test analysis",
            "model": "llama3.2-vision:11b",
        }
        mock_post.return_value.raise_for_status = lambda: None

        async with VisionEngine() as engine:
            result = await engine.analyze(sample_image, "What is this?")
            assert "Test analysis" in result.text
```

---

### Task 17: Performance Optimization

**Priority:** Medium
**Dependencies:** Task 16

**Objective:** Optimize for <3 second response time

**Key Optimizations:**
1. Image size optimization (resize before encoding)
2. Response caching for identical queries
3. Connection pooling for Ollama
4. Frame buffer management

**Code:**
```python
# src/streamind/cache/response_cache.py
"""Response caching for repeated queries."""

import hashlib
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from loguru import logger


@dataclass
class CachedResponse:
    """Cached response entry."""
    response: str
    timestamp: datetime
    hits: int = 0


class ResponseCache:
    """LRU cache for vision responses."""

    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        self._cache: OrderedDict[str, CachedResponse] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds

    def _key(self, image_hash: str, query: str) -> str:
        """Generate cache key."""
        return hashlib.sha256(f"{image_hash}:{query}".encode()).hexdigest()[:16]

    def get(self, image_hash: str, query: str) -> Optional[str]:
        """Get cached response if valid."""
        key = self._key(image_hash, query)

        if key not in self._cache:
            return None

        entry = self._cache[key]
        age = (datetime.now() - entry.timestamp).total_seconds()

        if age > self._ttl:
            del self._cache[key]
            return None

        entry.hits += 1
        self._cache.move_to_end(key)
        logger.debug(f"Cache hit for {key} (hits: {entry.hits})")
        return entry.response

    def set(self, image_hash: str, query: str, response: str):
        """Cache a response."""
        key = self._key(image_hash, query)

        # Evict if full
        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)

        self._cache[key] = CachedResponse(
            response=response,
            timestamp=datetime.now(),
        )
        logger.debug(f"Cached response for {key}")

    def clear(self):
        """Clear all cached responses."""
        self._cache.clear()
```

---

### Task 18: Error Handling and Logging

**Priority:** High
**Dependencies:** All modules

**Objective:** Comprehensive error handling with loguru

**Code:**
```python
# src/streamind/logging.py
"""Logging configuration using loguru."""

import sys
from pathlib import Path
from loguru import logger


def setup_logging(
    log_dir: Path = Path.home() / ".streamind" / "logs",
    level: str = "INFO",
    rotation: str = "10 MB",
    retention: str = "7 days",
):
    """Configure loguru logging.

    Args:
        log_dir: Directory for log files
        level: Minimum log level
        rotation: When to rotate log files
        retention: How long to keep old logs
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    # Remove default handler
    logger.remove()

    # Console handler (stderr)
    logger.add(
        sys.stderr,
        format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level,
        colorize=True,
    )

    # File handler
    logger.add(
        log_dir / "streamind.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",  # Always log DEBUG to file
        rotation=rotation,
        retention=retention,
        compression="zip",
    )

    # Error file (errors only)
    logger.add(
        log_dir / "errors.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}\n{exception}",
        level="ERROR",
        rotation=rotation,
        retention=retention,
        backtrace=True,
        diagnose=True,
    )

    logger.info(f"Logging initialized: {log_dir}")
```

---

### Task 19: Documentation

**Priority:** Medium
**Dependencies:** All features complete

**Deliverables:**
1. README.md - Installation, quick start, features
2. docs/USER_GUIDE.md - Detailed usage instructions
3. docs/DEVELOPER_GUIDE.md - Architecture, contributing
4. docs/API_REFERENCE.md - API documentation

---

### Task 20: Release Preparation

**Priority:** High
**Dependencies:** All tasks complete

**Subtasks:**
```
20.1 Create demo video
    - Screen recording of StreamMind in action
    - Show "What's that error?" use case
    - 30-60 second length

20.2 Build py2app bundle
    - python scripts/build_app.py py2app
    - Test on clean macOS install
    - Verify Screen Recording permission works

20.3 GitHub release
    - Version tag
    - Release notes
    - Binary attachment (.app.zip)

20.4 Announcement
    - HN Show HN post
    - Twitter/X thread
    - Reddit r/LocalLLaMA
```

---

## 9. API Specifications

### 9.1 CLI Commands

```bash
# Core commands
streamind ask "What's that error?"          # Analyze current screen
streamind ask "Explain this code" --stream  # Stream response
streamind ask "..." --monitor 2             # Use second monitor

# Service commands
streamind serve                              # Start background daemon
streamind serve --interval 0.5               # Custom capture interval
streamind status                             # Show daemon status
streamind stop                               # Stop daemon

# History commands
streamind history                            # Show recent analyses
streamind history --limit 20                 # Limit results
streamind history --search "error"           # Search history
streamind history --clear                    # Clear all history

# Configuration
streamind config                             # Show current config
streamind config set capture.interval 1.0   # Set value
streamind config reset                       # Reset to defaults

# Privacy
streamind privacy blocklist                  # Show blocked apps
streamind privacy blocklist add 1Password   # Block app
streamind privacy pause                      # Pause capture
streamind privacy resume                     # Resume capture
streamind privacy clear                      # Clear all data
```

### 9.2 HTTP API (Optional)

```yaml
# FastAPI endpoints when running with --api flag

POST /api/analyze
  Request:
    query: string
    monitor?: number (default: 1)
    stream?: boolean (default: false)
  Response:
    text: string
    duration_ms: number
    content_type: string

GET /api/status
  Response:
    status: "running" | "paused"
    uptime_seconds: number
    analyses_count: number
    last_analysis: datetime

GET /api/history
  Query params:
    limit?: number (default: 10)
    search?: string
  Response:
    analyses: AnalysisRecord[]

DELETE /api/history
  Response:
    deleted_count: number
```

---

## 10. Database Schema

```sql
-- Main history table
CREATE TABLE analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,          -- Unix timestamp
    query TEXT NOT NULL,              -- User's question
    response TEXT NOT NULL,           -- AI response
    app_name TEXT,                    -- Active application
    window_title TEXT,                -- Window title
    content_type TEXT,                -- code/terminal/browser/etc
    duration_ms REAL,                 -- Processing time
    metadata TEXT                     -- JSON for extensibility
);

-- Settings storage
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);

-- Indexes
CREATE INDEX idx_analyses_timestamp ON analyses(timestamp DESC);
CREATE INDEX idx_analyses_app ON analyses(app_name);
CREATE INDEX idx_analyses_content_type ON analyses(content_type);

-- Full-text search (future)
CREATE VIRTUAL TABLE analyses_fts USING fts5(
    query, response,
    content='analyses',
    content_rowid='id'
);
```

---

## 11. Configuration System

### 11.1 Default Configuration (defaults.toml)

```toml
[capture]
interval = 1.0            # Seconds between captures
monitor = 1               # Primary monitor
change_threshold = 10     # Hash difference threshold

[vision]
model = "llama3.2-vision:11b"
timeout = 120             # Seconds
max_image_size = 1120     # Pixels (max dimension)

[reasoning]
enabled = true
model = "deepseek-r1:14b"
keywords = ["why", "explain", "debug", "how", "reason"]

[storage]
history_days = 30         # Days to keep history
db_path = "~/.streamind/history.db"

[privacy]
blocklist = ["1Password", "Keychain Access"]
auto_pause_apps = []      # Apps that trigger pause

[ui]
show_in_dock = false
start_on_login = false
```

### 11.2 Settings Model

```python
# src/streamind/config/settings.py
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path


class CaptureSettings(BaseSettings):
    interval: float = 1.0
    monitor: int = 1
    change_threshold: int = 10


class VisionSettings(BaseSettings):
    model: str = "llama3.2-vision:11b"
    timeout: float = 120.0
    max_image_size: int = 1120


class ReasoningSettings(BaseSettings):
    enabled: bool = True
    model: str = "deepseek-r1:14b"
    keywords: list[str] = ["why", "explain", "debug", "how", "reason"]


class StorageSettings(BaseSettings):
    history_days: int = 30
    db_path: Path = Path.home() / ".streamind" / "history.db"


class PrivacySettings(BaseSettings):
    blocklist: list[str] = ["1Password", "Keychain Access"]
    auto_pause_apps: list[str] = []


class Settings(BaseSettings):
    capture: CaptureSettings = Field(default_factory=CaptureSettings)
    vision: VisionSettings = Field(default_factory=VisionSettings)
    reasoning: ReasoningSettings = Field(default_factory=ReasoningSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)

    class Config:
        env_prefix = "STREAMIND_"
        env_nested_delimiter = "__"
```

---

## 12. Testing Strategy

### 12.1 Test Categories

```
tests/
├── unit/                    # Fast, isolated tests
│   ├── test_capture.py      # Screen capture
│   ├── test_hash.py         # Change detection
│   ├── test_window.py       # Window detection
│   ├── test_prompts.py      # Prompt generation
│   └── test_storage.py      # Database operations
│
├── integration/             # Component interactions
│   ├── test_vision.py       # Ollama integration
│   ├── test_context.py      # Context management
│   └── test_cli.py          # CLI commands
│
└── e2e/                     # Full system tests
    └── test_pipeline.py     # Capture → Vision → Response
```

### 12.2 Test Fixtures

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from pathlib import Path
from PIL import Image
import tempfile


@pytest.fixture
def sample_image():
    """Create a sample test image."""
    img = Image.new("RGB", (800, 600), color="white")
    return img


@pytest.fixture
def temp_db():
    """Create temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield Path(f.name)


@pytest_asyncio.fixture
async def storage(temp_db):
    """Initialize storage with temp database."""
    from streamind.context.storage import StorageBackend
    async with StorageBackend(temp_db) as storage:
        yield storage


@pytest.fixture
def mock_ollama(mocker):
    """Mock Ollama responses."""
    mock_response = {
        "response": "This is a test response",
        "model": "llama3.2-vision:11b",
        "total_duration": 1000000000,  # 1 second in nanoseconds
        "eval_count": 50
    }
    return mocker.patch("httpx.AsyncClient.post", return_value=mock_response)
```

### 12.3 Coverage Targets

| Module | Target | Priority |
|--------|--------|----------|
| capture/ | 90% | High |
| vision/ | 85% | High |
| context/ | 85% | Medium |
| cli.py | 80% | Medium |
| ui/ | 70% | Low |
| **Overall** | **80%** | - |

---

## 13. Performance Benchmarks

### 13.1 Target Metrics

```
┌────────────────────────────────────────────────────────────────┐
│                    Performance Targets                          │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Screen Capture                                                 │
│  ├── Full screen (1920x1080): <50ms                            │
│  ├── Full screen (5K): <100ms                                  │
│  └── Active window only: <30ms                                 │
│                                                                 │
│  Vision Analysis                                                │
│  ├── Simple query: <2 seconds                                  │
│  ├── Complex query: <5 seconds                                 │
│  └── Streaming first token: <500ms                             │
│                                                                 │
│  Total Response Time                                            │
│  ├── Simple query: <3 seconds                                  │
│  └── Complex query: <6 seconds                                 │
│                                                                 │
│  Resource Usage                                                 │
│  ├── Idle memory: <100MB                                       │
│  ├── Active memory: <500MB                                     │
│  ├── Idle CPU: <5%                                             │
│  └── Active CPU: <50%                                          │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### 13.2 Benchmark Script

```python
# scripts/benchmark.py
"""Performance benchmarks for StreamMind."""

import asyncio
import time
from streamind.capture.screen import ScreenCapture
from streamind.vision.engine import VisionEngine


async def benchmark_capture():
    """Benchmark screen capture performance."""
    capture = ScreenCapture()

    times = []
    for _ in range(100):
        start = time.perf_counter()
        capture.capture_screen()
        times.append((time.perf_counter() - start) * 1000)

    print(f"Screen Capture (100 iterations):")
    print(f"  Min: {min(times):.2f}ms")
    print(f"  Max: {max(times):.2f}ms")
    print(f"  Avg: {sum(times)/len(times):.2f}ms")


async def benchmark_vision():
    """Benchmark vision analysis performance."""
    capture = ScreenCapture()
    image = capture.capture_screen()

    async with VisionEngine() as vision:
        times = []
        for _ in range(10):
            start = time.perf_counter()
            await vision.analyze(image, "What's on screen?")
            times.append((time.perf_counter() - start) * 1000)

        print(f"\nVision Analysis (10 iterations):")
        print(f"  Min: {min(times):.0f}ms")
        print(f"  Max: {max(times):.0f}ms")
        print(f"  Avg: {sum(times)/len(times):.0f}ms")


if __name__ == "__main__":
    asyncio.run(benchmark_capture())
    asyncio.run(benchmark_vision())
```

---

## 14. Security & Privacy

### 14.1 Privacy Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Privacy Boundaries                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CAPTURED                          NOT CAPTURED                  │
│  ├── Screen pixels                 ├── Keystrokes               │
│  ├── Active window name            ├── Passwords                │
│  ├── Timestamp                     ├── Clipboard                │
│  └── Your query                    ├── Audio                    │
│                                    └── Other app data           │
│                                                                  │
│  STORED LOCALLY                    NEVER TRANSMITTED            │
│  ├── Analysis history              ├── Screenshots              │
│  ├── App usage stats               ├── Raw captures             │
│  └── Settings                      └── Any personal data        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 14.2 Privacy Controls

```python
# Privacy implementation
class PrivacyManager:
    """Manage privacy controls for StreamMind."""

    def __init__(self, settings: PrivacySettings):
        self.blocklist = set(settings.blocklist)
        self.auto_pause_apps = set(settings.auto_pause_apps)
        self._paused = False

    def should_capture(self, app_name: str) -> bool:
        """Check if capture is allowed for current app."""
        if self._paused:
            return False
        if app_name in self.blocklist:
            return False
        return True

    def should_pause(self, app_name: str) -> bool:
        """Check if capture should auto-pause."""
        return app_name in self.auto_pause_apps

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False
```

---

## 15. Integration Points

### 15.1 Knowledge Activation System (KAS)

```python
# Future integration with KAS
class KASIntegration:
    """Integration with Knowledge Activation System."""

    async def index_analysis(self, analysis: AnalysisRecord):
        """Index analysis in KAS for searchable history."""
        # POST to KAS API
        pass

    async def search_related(self, query: str) -> list[dict]:
        """Search KAS for related knowledge."""
        # Query KAS search API
        pass
```

### 15.2 Inference Server

```python
# Integration with existing inference-server
class InferenceServerIntegration:
    """Use inference-server instead of direct Ollama."""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url

    async def analyze(self, image: Image.Image, prompt: str):
        """Use inference-server vision endpoint."""
        # Uses existing OllamaVisionService from inference-server
        pass
```

---

## 16. Deployment & Distribution

### 16.1 Installation Methods

```bash
# Method 1: pip install (development)
pip install -e .

# Method 2: pip install (release)
pip install streamind

# Method 3: Homebrew (future)
brew install streamind

# Method 4: Standalone app (py2app)
# Downloads ~50MB .app bundle
```

### 16.2 py2app Build

```python
# scripts/build_app.py
"""Build standalone macOS app with py2app."""

from setuptools import setup

APP = ['src/streamind/ui/menubar.py']
DATA_FILES = [
    ('assets', ['src/streamind/ui/assets/icon.png'])
]
OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'LSUIElement': True,  # Hide from Dock
        'CFBundleName': 'StreamMind',
        'CFBundleShortVersionString': '0.1.0',
    },
    'packages': ['streamind', 'mss', 'httpx', 'PIL', 'rumps'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
```

---

## 17. Risk Mitigation

### 17.1 Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Vision model too slow | Medium | High | Optimize image size, add response caching |
| PyObjC complexity | Medium | Medium | Graceful fallback to basic window detection |
| Menu bar app crashes | Low | Medium | CLI-first approach, menu bar optional |
| Ollama API changes | Low | Low | Abstract client, version pinning |
| macOS permissions | High | Medium | Clear first-run permission flow |
| Memory leaks | Medium | Medium | Frame cache limits, regular profiling |
| User confusion | Medium | Medium | Comprehensive docs, clear error messages |

### 17.2 Fallback Strategies

```python
# Graceful degradation pattern
class VisionEngine:
    async def analyze(self, image, prompt):
        try:
            return await self._analyze_ollama(image, prompt)
        except OllamaUnavailable:
            # Fallback: return helpful message
            return VisionResult(
                text="Ollama is not available. Please start it with: ollama serve",
                model="none",
                error=True
            )
```

---

## 18. Success Metrics

### 18.1 Technical Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Response time | <3 seconds | 95th percentile |
| Memory usage | <500MB | Peak during analysis |
| CPU idle | <5% | Average over 1 hour |
| Test coverage | 80%+ | pytest-cov |
| Error rate | <1% | Failed analyses / total |

### 18.2 User Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| "What's that error?" accuracy | 90% | Manual testing |
| User satisfaction | 4.5/5 | Survey feedback |
| Daily active usage | 10+ queries | Analytics |
| Time saved per query | 2+ minutes | User reports |

### 18.3 Business Metrics

| Metric | Target | Timeline |
|--------|--------|----------|
| GitHub stars | 50+ | First month |
| Downloads | 1,000+ | First month |
| HN front page | 1 day | Launch week |
| Community contributors | 5+ | First quarter |

---

## Appendix A: Quick Reference

### Commands Cheat Sheet

```bash
# Development (using uv - 10-100x faster than pip)
cd /Users/d/claude-code/ai-tools/streamind
uv venv                           # Create virtual environment
source .venv/bin/activate
uv pip install -e ".[dev]"        # Install with dev dependencies

# Alternative: uv sync (if pyproject.toml has dependencies)
uv sync --dev

# Run StreamMind
streamind ask "What's on screen?"
streamind status
streamind history

# Testing
pytest
pytest --cov=src/streamind
ruff check src/

# Build .app bundle (REQUIRED for macOS Tahoe+)
python scripts/build_app.py py2app
```

### macOS Tahoe Permission Note

**CRITICAL:** Starting with macOS Tahoe (15.x), non-bundled Python scripts
do NOT appear in the Screen Recording permission list. You MUST build the
.app bundle with py2app for screen capture to work:

```bash
# Build the .app bundle
python scripts/build_app.py py2app

# The app will be in: dist/StreamMind.app
# Move to Applications folder
mv dist/StreamMind.app /Applications/

# First launch will prompt for Screen Recording permission
```

### Key File Locations

```
~/.streamind/
├── history.db          # SQLite database
├── config.toml         # User configuration
└── logs/               # Application logs

/Users/d/claude-code/ai-tools/streamind/
├── src/streamind/      # Source code
├── tests/              # Test suite
└── dist/               # Built app
```

---

## Appendix B: Sources & References

### Web Research Sources
- [MSS Documentation](https://python-mss.readthedocs.io/examples.html)
- [Ollama llama3.2-vision](https://ollama.com/library/llama3.2-vision)
- [rumps GitHub](https://github.com/jaredks/rumps)
- [imagehash GitHub](https://github.com/JohannesBuchner/imagehash)
- [aiosqlite GitHub](https://github.com/omnilib/aiosqlite)
- [Apple NSWorkspace Docs](https://developer.apple.com/documentation/appkit/nsworkspace)
- [Google Agentic AI Patterns](https://cloud.google.com/architecture/choose-design-pattern-agentic-ai-system)

### Local Code References
- `/Users/d/claude-code/ai-tools/mlx-model-hub/inference-server/src/unified_mlx_app/services/ollama_vision_service.py`
- `/Users/d/claude-code/personal/knowledge-activation-system/pyproject.toml`

---

**Document End**

*This implementation plan is ready for execution. Start with Task 1 (Project Setup) when ready.*
