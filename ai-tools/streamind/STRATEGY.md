# StreamMind - Strategy Plan

## Executive Summary
Build an AI assistant that can see your screen in real-time. When you ask "What's that error?" it looks at your screen and answers. 100% local, instant response, privacy-first. The multimodal trend personified.

---

## The Vision

### What StreamMind Does
```
┌─────────────────────────────────────────────────────────────┐
│                     Your Mac Screen                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  VS Code with error                                  │    │
│  │  TypeError: Cannot read property 'map' of undefined │    │
│  │      at UserList.render (UserList.jsx:45)           │    │
│  └─────────────────────────────────────────────────────┘    │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    StreamMind                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  "What's that error?"                                │    │
│  │                                                      │    │
│  │  StreamMind: "That's a TypeError in UserList.jsx    │    │
│  │  line 45. You're calling .map() on 'users' but it's │    │
│  │  undefined. Check if the API response is being      │    │
│  │  awaited properly, or add a fallback: users || []"  │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Why It's Powerful
- **No more copy-pasting errors** - Just ask
- **No more screenshots** - AI sees what you see
- **Context-aware** - Understands what app you're in
- **100% local** - Nothing leaves your Mac
- **Always available** - Menu bar, always watching (when enabled)

---

## Technical Architecture

### High-Level Flow
```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    Screen    │     │   Vision     │     │  Reasoning   │
│   Capture    │────►│   Model      │────►│    Model     │
│  (periodic)  │     │ (analysis)   │     │  (response)  │
└──────────────┘     └──────────────┘     └──────────────┘
       │                    │                    │
       └────────────────────┼────────────────────┘
                            ▼
                   ┌──────────────┐
                   │   Context    │
                   │    Store     │
                   │  (history)   │
                   └──────────────┘
```

### Component Breakdown

#### 1. Screen Capture Engine
```python
# Options:
# - macOS ScreenCaptureKit (Swift, most efficient)
# - Python mss library (cross-platform, simpler)
# - PyObjC for native macOS APIs

class ScreenCapture:
    def __init__(self, interval: float = 1.0):
        """Capture screen at interval (seconds)"""
        self.interval = interval
        self.last_frame = None

    def capture(self) -> Image:
        """Capture current screen state"""
        # Intelligent capture:
        # - Skip if screen hasn't changed (hash comparison)
        # - Focus on active window
        # - Respect privacy (blur sensitive windows option)

    def get_active_window(self) -> WindowInfo:
        """Get info about currently focused window"""
        # Returns: app name, window title, bounds
```

#### 2. Vision Analysis Engine
```python
class VisionEngine:
    def __init__(self):
        self.model = "llama3.2-vision:11b"
        self.ollama_url = "http://localhost:11434"

    async def analyze(self, image: Image, query: str) -> str:
        """Analyze screenshot with query"""
        # 1. Encode image to base64
        # 2. Send to Ollama with vision model
        # 3. Include context about active window
        # 4. Return analysis

    async def detect_content_type(self, image: Image) -> ContentType:
        """Detect what's on screen: code, terminal, browser, etc."""
        # Enables specialized prompts per content type
```

#### 3. Context Manager
```python
class ContextManager:
    def __init__(self):
        self.history = []  # Recent screen states
        self.entities = {}  # Extracted entities (errors, files, etc.)

    def add_frame(self, frame: ScreenFrame):
        """Add captured frame to context"""
        # - Store frame with timestamp
        # - Extract entities (error messages, file names, etc.)
        # - Link to previous frames

    def get_context(self, query: str) -> Context:
        """Get relevant context for query"""
        # - Recent frames
        # - Extracted entities
        # - Active application context
```

#### 4. Reasoning Engine
```python
class ReasoningEngine:
    def __init__(self):
        self.model = "deepseek-r1:14b"

    async def reason(self,
                     vision_analysis: str,
                     context: Context,
                     query: str) -> str:
        """Deep reasoning about what's on screen"""
        # 1. Combine vision analysis + context
        # 2. Apply reasoning model for complex queries
        # 3. Generate actionable response
```

### UI Options

#### Option A: Menu Bar App (Recommended)
```
Menu Bar: 👁️ (eye icon, indicates watching)

Click dropdown:
├── Status: Watching (click to pause)
├── Ask StreamMind... (opens query input)
├── Recent Analyses
│   ├── "Error in UserList.jsx" (2 min ago)
│   └── "API response structure" (15 min ago)
├── Settings
│   ├── Capture interval
│   ├── Privacy zones (apps to ignore)
│   └── Model selection
└── Quit
```

#### Option B: Floating Window
```
┌─────────────────────────────────┐
│ StreamMind                   ─ □ │
├─────────────────────────────────┤
│ [Ask anything about your screen] │
│                                  │
│ Recent:                          │
│ • "What's that error?" (2m ago)  │
│ • "Explain this code" (10m ago)  │
└─────────────────────────────────┘
```

---

## Feature Roadmap

### MVP (Week 1-2)
- [ ] Screen capture with change detection
- [ ] Basic vision analysis via Ollama
- [ ] Simple CLI interface: `streamind ask "What's that error?"`
- [ ] SQLite storage for history

### v1.0 (Week 3)
- [ ] Menu bar app UI
- [ ] Active window detection
- [ ] Context-aware prompts (code vs browser vs terminal)
- [ ] History browsing

### v1.5 (Week 4+)
- [ ] Knowledge System integration (searchable screenshot archive)
- [ ] Multi-monitor support
- [ ] Hotkey activation (⌘+Shift+S → Ask)
- [ ] Session recording (create shareable demos)

### Future Expansion
- [ ] Voice integration (Wispr Flow trigger → StreamMind analysis)
- [ ] Training data generation (screen + action pairs for LoRA)
- [ ] Team sharing (record sessions for async code review)

---

## Implementation Plan

### Week 1: Core Engine
| Day | Task |
|-----|------|
| 1 | Project setup, screen capture with mss library |
| 2 | Ollama vision API integration, basic analysis |
| 3 | Change detection (skip unchanged frames) |
| 4 | Context manager (store history, extract entities) |
| 5 | CLI interface, basic queries working |

### Week 2: Polish & Reasoning
| Day | Task |
|-----|------|
| 1 | Add deepseek-r1 for complex reasoning |
| 2 | Active window detection (PyObjC) |
| 3 | Content-type specific prompts |
| 4 | History storage (SQLite), session management |
| 5 | Error handling, performance optimization |

### Week 3: UI & Integration
| Day | Task |
|-----|------|
| 1-2 | Menu bar app (SwiftUI or Electron) |
| 3 | Settings panel, privacy controls |
| 4 | Knowledge System integration (optional) |
| 5 | Testing, README, demo video, ship |

---

## Privacy & Security

### Privacy-First Design
```
Privacy Controls:
├── App Blocklist: Never capture these apps
│   ├── 1Password
│   ├── Banking apps
│   └── Custom list
├── Blur Sensitive: Automatically blur detected PII
├── Local Only: All processing on-device
├── Auto-Delete: Clear history after X days
└── Pause Mode: Hotkey to disable capture
```

### What's Captured vs Not
| Captured | NOT Captured |
|----------|--------------|
| Screen pixels | Keystrokes |
| Active window name | Passwords |
| Timestamp | Clipboard |
| Your query | Audio |

---

## Technical Decisions

### Why Ollama + llama3.2-vision?
- **Installed**: You already have it from the system audit
- **Local**: No data leaves your Mac
- **Fast**: <3 second response for most queries
- **Quality**: 11B vision model is very capable

### Why Not MLX Native Vision?
- Qwen2-VL (MLX) is blocked by PyTorch issues
- llama3.2-vision:11b via Ollama works NOW
- Can migrate to MLX later when issues resolved

### Capture Strategy
```python
# Intelligent capture to save resources
if frame_hash == last_frame_hash:
    skip()  # No change, don't process
elif idle_time > 30_seconds:
    reduce_interval()  # User idle, capture less
elif active_window_changed:
    capture_immediately()  # Context changed, capture now
```

---

## Market Positioning

### Competitive Analysis
| Product | Approach | Limitation |
|---------|----------|------------|
| Rewind.ai | Records everything | Cloud-based, privacy concerns |
| ChatGPT Vision | Upload screenshots | Manual, requires copy-paste |
| Claude Vision | Upload screenshots | Manual, requires copy-paste |
| **StreamMind** | **Real-time local** | **None** |

### Target Users
1. **Developers** - "What's that error?" use case
2. **Designers** - "What's wrong with this layout?"
3. **Support Engineers** - "Explain this log output"
4. **Students** - "Explain what's on my screen"

### Virality Potential
- Demo videos: "Watch AI understand my screen in real-time"
- Screenshots: "StreamMind just saved me 10 minutes of debugging"
- Word of mouth: "You need to try this app"

---

## Success Metrics

### Technical Goals
- [ ] <3 second response time
- [ ] <500MB memory usage
- [ ] <5% CPU when idle
- [ ] Works offline (no internet required)

### User Goals
- [ ] "What's that error?" works 90% of the time
- [ ] Natural language queries feel natural
- [ ] Privacy controls are clear and trustworthy

### Business Goals
- [ ] 1K downloads first month
- [ ] Featured on Hacker News
- [ ] 50+ GitHub stars

---

## Getting Started

### Prerequisites Check
```bash
# Vision model installed
ollama run llama3.2-vision:11b "describe this image" --image test.png

# Reasoning model installed
ollama run deepseek-r1:14b "Hello"

# Screen capture works (test)
python -c "import mss; print(mss.mss().monitors)"
```

### First Steps
1. Create project structure
2. Implement basic screen capture
3. Test vision model with static screenshot
4. Add query interface
5. Iterate from there

---

## Expansion Paths

### Path 1: Knowledge Integration
StreamMind → captures screenshots → indexes in Knowledge System → searchable visual history

### Path 2: Training Data
StreamMind → records screen + your actions → generates LoRA training pairs → Unified MLX App trains on them

### Path 3: Team Collaboration
StreamMind → records debugging session → shareable replay → async code review

All paths leverage your existing projects!
