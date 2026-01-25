# MLX Infrastructure Suite - Expanded Implementation Plan v2.0

> **Comprehensive A-to-Z Blueprint with Full Research Integration**

**Generated:** January 12, 2026
**Last Updated:** January 12, 2026
**Target Hardware:** MacBook Pro M4 Pro (48GB RAM), macOS 26.2

---

## Table of Contents

1. [Research Summary & Key Changes](#1-research-summary--key-changes)
2. [Risk Assessment Matrix](#2-risk-assessment-matrix)
3. [Environment Deep Dive](#3-environment-deep-dive)
4. [Technology Stack Decisions (Revised)](#4-technology-stack-decisions-revised)
5. [Phase 0: Foundation & Prerequisites](#5-phase-0-foundation--prerequisites)
6. [Phase 1: MLXDash - Complete Specification](#6-phase-1-mlxdash---complete-specification)
7. [Phase 2: MLXCache - Complete Specification](#7-phase-2-mlxcache---complete-specification)
8. [Phase 3: SwiftMLX - Complete Specification](#8-phase-3-swiftmlx---complete-specification)
9. [Phase 4: Integration & Quality Assurance](#9-phase-4-integration--quality-assurance)
10. [Phase 5: Release & Distribution](#10-phase-5-release--distribution)
11. [Removed Items & Rationale](#11-removed-items--rationale)
12. [Appendices](#12-appendices)

---

## 1. Research Summary & Key Changes

### 1.1 Critical Updates from Web Research

| Finding | Impact | Source |
|---------|--------|--------|
| **@Observable is the 2025 standard** | Use `@Observable` macro, NOT `ObservableObject` | [Apple Docs](https://developer.apple.com/documentation/SwiftUI/Migrating-from-the-observable-object-protocol-to-the-observable-macro) |
| **@Observable performance benefit** | Views only re-render when accessed properties change | [avanderlee.com](https://www.avanderlee.com/swiftui/observable-macro-performance-increase-observableobject/) |
| **GRDB.swift is recommended** | Better performance, SwiftUI integration via GRDBQuery | [GRDB Wiki](https://github.com/groue/GRDB.swift/wiki/Performance) |
| **SharingGRDB from Point-Free** | Works in @Observable classes, not just SwiftUI views | [Point-Free Blog](https://www.pointfree.co/blog/posts/168-sharinggrdb-a-swiftdata-alternative) |
| **UV is the 2025 Python standard** | 10-100x faster than pip, global cache, manages Python versions | [DataCamp](https://www.datacamp.com/tutorial/python-uv) |
| **MenuBarExtra SettingsLink broken** | Use custom preferences window approach | [steipete.me](https://steipete.me/posts/2025/showing-settings-from-macos-menu-bar-items) |
| **Ollama eval_duration** | Use `eval_count / eval_duration` for tok/sec | [Ollama Docs](https://docs.ollama.com/api/usage) |
| **Swift Charts 3D in macOS 26** | New 3D visualization capabilities | WWDC 2025 |
| **Actor isolation critical** | Use actors for services, snapshot state before await | [Swift Forums](https://forums.swift.org/) |
| **Menu bar apps <50MB target** | MacMount demonstrates achievable footprint | GitHub |

### 1.2 Critical Updates from Local Analysis

| Finding | Impact | Action |
|---------|--------|--------|
| **UV 0.9.24 installed** | Use UV instead of pip/hatch | Switch to `uv` commands |
| **HuggingFace cache: 22GB** | Third source of model weights to dedupe | Add HF cache support to MLXCache |
| **Ollama cache: 25GB** | Primary dedup target | Symlink strategy confirmed |
| **mlx-hub HuggingFace service exists** | 464 lines of tested code | Reuse/adapt for MLXCache |
| **Typer 0.21.1 + Rich 14.1.0 installed** | CLI stack ready | Confirmed choice |
| **No Developer ID certificate** | BLOCKER for distribution | Must obtain first |
| **pytest, ruff, mypy installed** | Dev tooling ready | Use existing |
| **MLX 0.29.4, mlx-lm 0.29.1** | Latest stable | Confirmed |

### 1.3 Summary of Changes from v1

| Category | Old Approach | New Approach | Rationale |
|----------|--------------|--------------|-----------|
| **Swift Database** | Raw SQLite3 C API | GRDB.swift + GRDBQuery | Better performance, SwiftUI integration, type safety |
| **Swift Observation** | Could use either | Must use @Observable | Performance, modern, Apple recommended |
| **Python Packaging** | Hatchling + pip | UV | 10-100x faster, better dependency resolution |
| **HF Service** | Write from scratch | Adapt from mlx-hub | 464 lines of tested code ready |
| **Cache Sources** | Ollama + HF download | Ollama + HF download + HF cache | Additional 22GB dedup opportunity |
| **Actor Pattern** | Optional | Required | Concurrency safety, Swift 6 compliance |

---

## 2. Risk Assessment Matrix

### 2.1 Technical Risks

| Risk | Probability | Impact | Mitigation | Status |
|------|-------------|--------|------------|--------|
| **No Developer ID Certificate** | 100% | BLOCKER | Obtain from developer.apple.com before packaging | ACTION REQUIRED |
| **GPU Utilization Unavailable** | High | Low | Show "N/A", use memory proxy metrics | Planned |
| **MenuBarExtra SettingsLink Bug** | 100% | Medium | Custom preferences window, documented workaround | Planned |
| **@Observable Init Behavior** | Medium | Medium | Use @State only in owning view, document pattern | Planned |
| **IOKit Private APIs** | Medium | Medium | Stick to public APIs, accept limited metrics | Planned |
| **Ollama API Changes** | Low | Medium | Version detection, graceful degradation | Planned |
| **GRDB Learning Curve** | Medium | Low | Follow Point-Free patterns, comprehensive docs | Planned |

### 2.2 Project Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Scope Creep** | High | High | Strict MVP feature set, defer v2 features |
| **Low Initial Adoption** | Medium | Medium | Focus on genuine utility, not marketing |
| **Competitor Emergence** | Low | Medium | Move fast, establish expertise |
| **Burnout** | Medium | High | 1-week phases, ship incrementally |

### 2.3 Integration Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **mlx-cache not in PATH** | Medium | Low | MLXDash detects and handles gracefully |
| **Symlink Permission Issues** | Low | Medium | Document requirements, detect at runtime |
| **HuggingFace API Rate Limits** | Low | Low | Cache responses, exponential backoff |

---

## 3. Environment Deep Dive

### 3.1 Complete Hardware Profile

```yaml
Machine:
  Model: MacBook Pro (Mac16,7)
  Chip: Apple M4 Pro
  CPU Cores: 14 (10 performance + 4 efficiency)
  GPU Cores: 20
  Neural Engine: 16-core

Memory:
  Total: 48GB Unified Memory
  Memory Bandwidth: 273 GB/s

Storage:
  Available: Check with df -h

macOS:
  Version: 26.2 (Tahoe)
  Build: 25C56
  Supports: Neural Accelerators, Metal 4
```

### 3.2 Complete Software Inventory

#### Python Environment (3.12.12)

```
# ML Stack (Production Ready)
mlx                 0.29.4      ✓ Latest stable
mlx-lm              0.29.1      ✓ LLM support
mlx-vlm             0.3.9       ✓ Vision models
mlx-audio           0.2.9       ✓ Audio models
mlx-omni-server     0.5.1       ✓ OpenAI-compatible
mlx-tuning-fork     0.4.0       ✓ Fine-tuning
mlx-whisper         0.4.3       ✓ Speech recognition

# CLI Stack (Ready to Use)
typer               0.21.1      ✓ Modern CLI framework
click               8.2.1       ✓ Typer foundation
rich                14.1.0      ✓ Beautiful output

# HTTP & Data
httpx               0.28.1      ✓ Async HTTP
huggingface-hub     0.36.0      ✓ Model downloads
pydantic            2.11.7      ✓ Data validation
numpy               2.4.1       ✓ Arrays
aiosqlite           0.22.1      ✓ Async SQLite

# Development
pytest              9.0.2       ✓ Testing
pytest-asyncio      1.3.0       ✓ Async testing
ruff                0.14.11     ✓ Linting
mypy_extensions     1.1.0       ✓ Type checking

# Package Management
uv                  0.9.24      ✓ Modern package manager (10-100x faster)
```

#### Ollama Environment

```yaml
Version: 0.13.5
API: http://localhost:11434

Models Installed:
  - deepseek-r1:14b       (9.0 GB)   # Reasoning model
  - llama3.2-vision:11b   (7.8 GB)   # Vision model
  - qwen2.5-coder:7b      (4.7 GB)   # Code model
  - qwen2.5:7b            (4.7 GB)   # General (DUPLICATE BASE)
  - nomic-embed-text      (0.3 GB)   # Embeddings

Cache Location: ~/.ollama/models/
Cache Size: 25GB
Blob Structure: Content-addressable SHA256

Manifest Format:
  - schemaVersion: 2
  - mediaType: Docker distribution manifest
  - layers: model, template, license, params
```

#### HuggingFace Cache (DISCOVERED - Add to MLXCache)

```yaml
Location: ~/.cache/huggingface/hub/
Size: 22GB

Models Cached:
  - meta-llama/Llama-3.2-1B
  - mlx-community/Llama-3.2-1B-Instruct-4bit
  - mlx-community/Qwen2.5-0.5B-Instruct-4bit
  - mlx-community/Kokoro-82M-bf16
  - mixedbread-ai/mxbai-rerank-base-v1
  - (and more...)

Deduplication Opportunity:
  Some models exist in BOTH Ollama and HF cache
  Potential savings: 5-10GB
```

#### Development Tools

```yaml
Homebrew Packages:
  - git, gh           # Version control
  - node, pnpm        # JS ecosystem
  - lazygit           # Git TUI
  - create-dmg        # NOT INSTALLED - need to add

Xcode: (Verify with xcodebuild -version)
  - Required for Swift development
  - Swift version: 5.9+

Code Signing:
  - Developer ID: NOT CONFIGURED (BLOCKER)
  - Action: Generate at developer.apple.com
```

### 3.3 Existing Code Assets to Reuse

#### mlx-model-hub HuggingFace Service (464 lines)

**Location:** `/Users/d/claude-code/ai-tools/mlx-model-hub/backend/src/mlx_hub/services/huggingface.py`

**Reusable Components:**
```python
# Data Models (lines 26-82)
@dataclass ModelFile      # filename, size_bytes, lfs
@dataclass ModelMetadata  # Full model info with methods
@dataclass SearchResult   # Paginated search results

# Service Methods (lines 84-463)
class HuggingFaceService:
    search_models()       # Search HF with filters
    get_model_info()      # Get detailed model info
    download_model()      # Download with progress
    check_memory_compatibility()  # Memory check
    _detect_quantization()  # Parse quantization from name
    _estimate_memory()    # Memory estimation
    _validate_model_id()  # Security validation
```

**Adaptation for MLXCache:**
- Remove FastAPI dependencies
- Add CLI progress callbacks
- Add symlink creation
- Add registry integration

#### knowledge-activation-system Patterns

**Location:** `/Users/d/claude-code/personal/knowledge-activation-system/`

**Reusable Patterns:**
- Typer CLI structure
- Optional dependency groups in pyproject.toml
- async database patterns

---

## 4. Technology Stack Decisions (Revised)

### 4.1 MLXDash Technology Stack (UPDATED)

| Component | v1 Choice | v2 Choice | Rationale |
|-----------|-----------|-----------|-----------|
| **UI Framework** | SwiftUI + MenuBarExtra | SwiftUI + MenuBarExtra | No change, correct choice |
| **Observation** | @Observable/@ObservableObject | **@Observable ONLY** | Performance, modern standard |
| **Database** | Raw SQLite3 C API | **GRDB.swift** | Type-safe, SwiftUI integration, better performance |
| **SwiftUI DB Integration** | Manual | **GRDBQuery (@Query)** | Automatic observation, Point-Free patterns |
| **Charts** | Swift Charts | Swift Charts | No change, native solution |
| **Ollama Client** | Custom URLSession | Custom with **actor isolation** | Thread safety, Swift 6 compliance |
| **Settings** | SettingsLink | **Custom Window** | SettingsLink broken in MenuBarExtra |

**Swift Package Dependencies:**
```swift
dependencies: [
    .package(url: "https://github.com/groue/GRDB.swift", from: "7.0.0"),
    .package(url: "https://github.com/groue/GRDBQuery", from: "0.11.0"),
]
```

### 4.2 MLXCache Technology Stack (UPDATED)

| Component | v1 Choice | v2 Choice | Rationale |
|-----------|-----------|-----------|-----------|
| **Package Manager** | pip + hatchling | **UV** | 10-100x faster, global cache |
| **Build Backend** | hatchling | **hatchling** (via UV) | UV uses standard backends |
| **CLI Framework** | Typer | Typer | No change, already installed |
| **HF Integration** | Write new | **Adapt from mlx-hub** | 464 lines of tested code |
| **Cache Sources** | Ollama + HF download | **Ollama + HF download + HF cache** | Additional 22GB dedup |
| **Database** | SQLite | SQLite (aiosqlite for async) | No change |

**UV-based pyproject.toml:**
```toml
[project]
name = "mlx-cache"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.21.0",
    "rich>=14.0.0",
    "httpx>=0.28.0",
    "huggingface-hub>=0.36.0",
    "pyyaml>=6.0",
    "aiosqlite>=0.22.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

# Use UV for all operations:
# uv sync           - Install dependencies
# uv run mlx-cache  - Run CLI
# uv build          - Build package
# uv publish        - Publish to PyPI
```

### 4.3 SwiftMLX Technology Stack (UPDATED)

| Component | v1 Choice | v2 Choice | Rationale |
|-----------|-----------|-----------|-----------|
| **Ollama Client** | Consider ollama-swift | **Custom actor-isolated** | Full control, no external deps |
| **Observation** | @Observable | @Observable | Consistent with MLXDash |
| **UI Components** | SwiftUI | SwiftUI | No change |
| **DB Integration** | Optional | **Optional GRDB** | Consistent patterns if needed |

### 4.4 Removed Technologies

| Technology | Was In | Removed Because |
|------------|--------|-----------------|
| `ObservableObject` | MLXDash, SwiftMLX | @Observable is faster, modern |
| Raw SQLite3 C API | MLXDash | GRDB is safer, faster, better DX |
| pip install | MLXCache | UV is 10-100x faster |
| SettingsLink | MLXDash | Broken in MenuBarExtra |

---

## 5. Phase 0: Foundation & Prerequisites

### 5.1 Prerequisite Checklist (BLOCKING)

```bash
# CRITICAL - DO THESE FIRST

# 1. Developer ID Certificate (MANUAL - ~30 minutes)
#    a. Go to developer.apple.com
#    b. Account → Certificates, Identifiers & Profiles
#    c. Certificates → Create "Developer ID Application"
#    d. Download and double-click to install in Keychain
#    e. Verify:
security find-identity -v -p codesigning
# Should show: "Developer ID Application: Your Name (TEAM_ID)"

# 2. Install Missing Tools
brew install create-dmg xcbeautify

# 3. Verify Xcode
xcodebuild -version
# Expected: Xcode 16.x, Build version XXX

# 4. Verify UV
uv --version
# Expected: uv 0.9.24 or later

# 5. Verify Ollama Running
curl http://localhost:11434/api/tags
# Should return JSON with models list
```

### 5.2 Repository Structure (EXPANDED)

```
mlx-infrastructure-suite/
├── .github/
│   ├── workflows/
│   │   ├── mlxdash-ci.yml          # Build, test, lint Swift
│   │   ├── mlxcache-ci.yml         # Test, lint Python
│   │   ├── swiftmlx-ci.yml         # Build, test Swift Package
│   │   └── release.yml             # Coordinated release
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml
│   │   ├── feature_request.yml
│   │   └── config.yml
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── dependabot.yml
│
├── mlxdash/                         # Swift Menu Bar App
│   ├── MLXDash.xcodeproj/
│   │   ├── project.pbxproj
│   │   └── xcshareddata/
│   ├── MLXDash/
│   │   ├── App/
│   │   │   ├── MLXDashApp.swift     # @main, MenuBarExtra
│   │   │   ├── AppState.swift       # @Observable app state
│   │   │   └── AppDelegate.swift    # Lifecycle, permissions
│   │   ├── Views/
│   │   │   ├── MenuBar/
│   │   │   │   ├── MenuBarLabel.swift
│   │   │   │   └── MenuBarView.swift
│   │   │   ├── Metrics/
│   │   │   │   ├── MetricsView.swift
│   │   │   │   ├── ModelSection.swift
│   │   │   │   └── SystemSection.swift
│   │   │   ├── Benchmark/
│   │   │   │   ├── BenchmarkView.swift
│   │   │   │   └── BenchmarkResultCard.swift
│   │   │   ├── History/
│   │   │   │   ├── HistoryView.swift
│   │   │   │   └── HistoryChart.swift
│   │   │   ├── Preferences/
│   │   │   │   └── PreferencesWindow.swift  # NOT SettingsLink
│   │   │   └── Components/
│   │   │       ├── MetricRow.swift
│   │   │       ├── ProgressBar.swift
│   │   │       └── ConnectionIndicator.swift
│   │   ├── Services/
│   │   │   ├── OllamaService.swift   # actor, polls API
│   │   │   ├── SystemMetricsService.swift
│   │   │   ├── BenchmarkService.swift
│   │   │   └── CacheIntegration.swift  # mlx-cache --json
│   │   ├── Database/
│   │   │   ├── AppDatabase.swift     # GRDB setup
│   │   │   ├── Models/
│   │   │   │   ├── Session.swift     # GRDB Record
│   │   │   │   └── Benchmark.swift   # GRDB Record
│   │   │   └── Migrations/
│   │   │       └── DatabaseMigrations.swift
│   │   ├── Models/
│   │   │   ├── ModelInfo.swift
│   │   │   ├── SystemMetrics.swift
│   │   │   └── OllamaResponses.swift
│   │   └── Resources/
│   │       ├── Assets.xcassets/
│   │       │   ├── AppIcon.appiconset/
│   │       │   └── MenuBarIcon.imageset/
│   │       └── Info.plist
│   ├── MLXDashTests/
│   │   ├── Services/
│   │   │   ├── OllamaServiceTests.swift
│   │   │   └── BenchmarkServiceTests.swift
│   │   ├── Database/
│   │   │   └── DatabaseTests.swift
│   │   └── Mocks/
│   │       └── MockURLProtocol.swift
│   ├── Package.swift                 # For SPM dependencies
│   └── README.md
│
├── mlx-cache/                        # Python CLI Tool
│   ├── src/
│   │   └── mlx_cache/
│   │       ├── __init__.py           # __version__
│   │       ├── cli.py                # Typer app
│   │       ├── cache.py              # CacheManager
│   │       ├── registry.py           # SQLite registry
│   │       ├── config.py             # YAML config
│   │       ├── sources/
│   │       │   ├── __init__.py
│   │       │   ├── base.py           # Abstract source
│   │       │   ├── huggingface.py    # HF Hub (adapted from mlx-hub)
│   │       │   ├── huggingface_cache.py  # HF Cache dedup (NEW)
│   │       │   ├── ollama.py         # Ollama symlinks
│   │       │   └── local.py          # Local files
│   │       ├── dedup.py              # Deduplication scanner
│   │       └── utils.py              # Helpers
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py               # pytest fixtures
│   │   ├── test_cli.py
│   │   ├── test_cache.py
│   │   ├── test_registry.py
│   │   └── test_sources/
│   │       ├── test_huggingface.py
│   │       ├── test_huggingface_cache.py
│   │       └── test_ollama.py
│   ├── pyproject.toml
│   ├── uv.lock                       # UV lockfile
│   └── README.md
│
├── swiftmlx/                         # Swift Package
│   ├── Package.swift
│   ├── Sources/
│   │   ├── SwiftMLX/
│   │   │   ├── SwiftMLX.swift        # Public API
│   │   │   ├── Model/
│   │   │   │   ├── MLXModel.swift
│   │   │   │   ├── ModelLoader.swift
│   │   │   │   └── ModelRegistry.swift
│   │   │   ├── Inference/
│   │   │   │   ├── TextGeneration.swift
│   │   │   │   ├── Streaming.swift
│   │   │   │   └── VisionAnalysis.swift
│   │   │   ├── Client/
│   │   │   │   ├── OllamaClient.swift  # actor
│   │   │   │   └── JSONModels.swift
│   │   │   └── Cache/
│   │   │       └── MLXCacheClient.swift
│   │   └── SwiftMLXUI/
│   │       ├── ChatView.swift
│   │       ├── ModelPicker.swift
│   │       ├── PerformanceView.swift
│   │       ├── PromptField.swift
│   │       └── Components/
│   │           ├── MessageBubble.swift
│   │           └── StreamingText.swift
│   ├── Templates/
│   │   ├── MLX Chat App.xctemplate/
│   │   ├── MLX Document Analyzer.xctemplate/
│   │   └── MLX Image Captioner.xctemplate/
│   ├── Examples/
│   │   ├── ChatDemo/
│   │   └── VisionDemo/
│   ├── Tests/
│   │   └── SwiftMLXTests/
│   ├── install-templates.sh
│   └── README.md
│
├── shared/
│   ├── config-schema.yaml            # Shared config format
│   └── assets/
│       ├── logo.svg
│       └── screenshots/
│
├── scripts/
│   ├── setup.sh                      # First-time setup
│   ├── test-all.sh                   # Run all tests
│   ├── build-release.sh              # Build all for release
│   └── check-prerequisites.sh        # Verify environment
│
├── docs/
│   ├── architecture.md
│   ├── api-reference.md
│   ├── user-guide.md
│   └── tutorials/
│       ├── getting-started.md
│       ├── building-chat-app.md
│       └── model-management.md
│
├── .taskmaster/
│   ├── config.json
│   ├── tasks/
│   │   └── tasks.json
│   └── docs/
│       └── prd.txt
│
├── .gitignore
├── CLAUDE.md
├── STRATEGY.md
├── IMPLEMENTATION_PLAN.md            # Original plan
├── IMPLEMENTATION_PLAN_V2.md         # This document
├── README.md
├── LICENSE
├── CONTRIBUTING.md
└── CODE_OF_CONDUCT.md
```

---

## 6. Phase 1: MLXDash - Complete Specification

### 6.1 Architecture (UPDATED with GRDB + Actor)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          MLXDashApp (@main)                             │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                         AppState                                   │ │
│  │                      (@Observable)                                 │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐   │ │
│  │  │ OllamaService   │  │ SystemMetrics   │  │ BenchmarkService │   │ │
│  │  │    (actor)      │  │ Service (actor) │  │     (actor)      │   │ │
│  │  └─────────────────┘  └─────────────────┘  └──────────────────┘   │ │
│  └───────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────┤
│                              Views                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ MenuBarView  │  │ MetricsView  │  │ BenchmarkView│  │HistoryView │  │
│  │              │  │              │  │              │  │            │  │
│  │ @Environment │  │ @Query       │  │ @Environment │  │ @Query     │  │
│  │ (appState)   │  │ (GRDB)       │  │ (appState)   │  │ (GRDB)     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│                           Database (GRDB)                                │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                        AppDatabase                                 │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │  DatabasePool (thread-safe, connection pooling)             │  │  │
│  │  │  ├── sessions table                                         │  │  │
│  │  │  ├── benchmarks table                                       │  │  │
│  │  │  └── ValueObservation (auto-updates SwiftUI)                │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 GRDB Database Implementation

```swift
// File: MLXDash/Database/AppDatabase.swift
import Foundation
import GRDB

/// Shared database for MLXDash
final class AppDatabase {
    /// The database queue
    private let dbPool: DatabasePool

    /// Singleton for app-wide access
    static let shared = try! AppDatabase()

    private init() throws {
        let fileManager = FileManager.default
        let appSupport = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let dbDir = appSupport.appendingPathComponent("MLXDash", isDirectory: true)
        try fileManager.createDirectory(at: dbDir, withIntermediateDirectories: true)

        let dbPath = dbDir.appendingPathComponent("mlxdash.sqlite").path
        dbPool = try DatabasePool(path: dbPath)

        try migrator.migrate(dbPool)
    }

    /// Schema migrations
    private var migrator: DatabaseMigrator {
        var migrator = DatabaseMigrator()

        #if DEBUG
        migrator.eraseDatabaseOnSchemaChange = true
        #endif

        migrator.registerMigration("v1") { db in
            // Sessions table
            try db.create(table: "session") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("modelName", .text).notNull()
                t.column("startedAt", .datetime).notNull()
                t.column("endedAt", .datetime)
                t.column("avgTokensPerSec", .double)
                t.column("totalTokens", .integer)
                t.column("peakMemoryGB", .double)
            }

            // Benchmarks table
            try db.create(table: "benchmark") { t in
                t.autoIncrementedPrimaryKey("id")
                t.column("modelName", .text).notNull()
                t.column("ranAt", .datetime).notNull()
                t.column("avgTokensPerSec", .double).notNull()
                t.column("p50LatencyMs", .double).notNull()
                t.column("p95LatencyMs", .double).notNull()
                t.column("peakMemoryGB", .double).notNull()
                t.column("promptCount", .integer).notNull()
            }

            // Indexes
            try db.create(index: "session_on_modelName", on: "session", columns: ["modelName"])
            try db.create(index: "benchmark_on_modelName", on: "benchmark", columns: ["modelName"])
        }

        return migrator
    }
}

// MARK: - Database Access
extension AppDatabase {
    /// A database connection for reading
    var reader: DatabaseReader { dbPool }

    /// A database connection for writing
    var writer: DatabaseWriter { dbPool }
}

// File: MLXDash/Database/Models/Benchmark.swift
import Foundation
import GRDB

/// A benchmark result record
struct Benchmark: Codable, Identifiable {
    var id: Int64?
    var modelName: String
    var ranAt: Date
    var avgTokensPerSec: Double
    var p50LatencyMs: Double
    var p95LatencyMs: Double
    var peakMemoryGB: Double
    var promptCount: Int
}

extension Benchmark: FetchableRecord, MutablePersistableRecord {
    /// Update auto-generated id upon successful insertion
    mutating func didInsert(_ inserted: InsertionSuccess) {
        id = inserted.rowID
    }
}

// MARK: - Queries
extension Benchmark {
    /// Request for all benchmarks, ordered by date
    static func orderedByDate() -> QueryInterfaceRequest<Benchmark> {
        Benchmark.order(Column("ranAt").desc)
    }

    /// Request for benchmarks of a specific model
    static func filter(modelName: String) -> QueryInterfaceRequest<Benchmark> {
        Benchmark.filter(Column("modelName") == modelName)
    }

    /// Request for recent benchmarks (last 30 days)
    static func recent(days: Int = 30) -> QueryInterfaceRequest<Benchmark> {
        let cutoff = Date().addingTimeInterval(-Double(days * 24 * 60 * 60))
        return Benchmark
            .filter(Column("ranAt") >= cutoff)
            .order(Column("ranAt").desc)
    }
}

// File: MLXDash/Views/History/HistoryView.swift
import SwiftUI
import GRDB
import GRDBQuery
import Charts

struct HistoryView: View {
    /// Automatically observes database changes
    @Query(BenchmarkRequest()) private var benchmarks: [Benchmark]

    @State private var selectedTimeRange: TimeRange = .week

    enum TimeRange: String, CaseIterable {
        case day = "24h"
        case week = "7d"
        case month = "30d"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Time range picker
            Picker("Time Range", selection: $selectedTimeRange) {
                ForEach(TimeRange.allCases, id: \.self) { range in
                    Text(range.rawValue).tag(range)
                }
            }
            .pickerStyle(.segmented)

            if benchmarks.isEmpty {
                ContentUnavailableView(
                    "No Benchmarks Yet",
                    systemImage: "chart.line.uptrend.xyaxis",
                    description: Text("Run a benchmark to see history here.")
                )
            } else {
                // Performance chart
                Chart(filteredBenchmarks) { benchmark in
                    LineMark(
                        x: .value("Date", benchmark.ranAt),
                        y: .value("tok/s", benchmark.avgTokensPerSec)
                    )
                    .foregroundStyle(by: .value("Model", benchmark.modelName))

                    PointMark(
                        x: .value("Date", benchmark.ranAt),
                        y: .value("tok/s", benchmark.avgTokensPerSec)
                    )
                    .foregroundStyle(by: .value("Model", benchmark.modelName))
                }
                .frame(height: 200)
                .chartXAxis {
                    AxisMarks(values: .automatic(desiredCount: 5))
                }

                // Statistics
                StatisticsSection(benchmarks: filteredBenchmarks)
            }
        }
        .padding()
    }

    private var filteredBenchmarks: [Benchmark] {
        let cutoff: Date
        switch selectedTimeRange {
        case .day: cutoff = Date().addingTimeInterval(-24 * 60 * 60)
        case .week: cutoff = Date().addingTimeInterval(-7 * 24 * 60 * 60)
        case .month: cutoff = Date().addingTimeInterval(-30 * 24 * 60 * 60)
        }
        return benchmarks.filter { $0.ranAt >= cutoff }
    }
}

/// GRDBQuery request for benchmarks
struct BenchmarkRequest: ValueObservationQueryable {
    static var defaultValue: [Benchmark] { [] }

    func fetch(_ db: Database) throws -> [Benchmark] {
        try Benchmark.recent().fetchAll(db)
    }
}
```

### 6.3 Actor-Isolated Services

```swift
// File: MLXDash/Services/OllamaService.swift
import Foundation
import Observation

/// Actor-isolated service for Ollama API communication
///
/// Using an actor ensures thread-safe access to mutable state
/// and proper isolation for async operations.
actor OllamaService {
    // MARK: - Published State (for UI observation)

    /// Current active model info
    private(set) var activeModel: ModelInfo?

    /// List of available models
    private(set) var availableModels: [ModelInfo] = []

    /// Connection status
    private(set) var isConnected = false

    /// Current generation metrics
    private(set) var tokensPerSecond: Double = 0

    /// Whether currently generating
    private(set) var isGenerating = false

    // MARK: - Private State

    private var pollingTask: Task<Void, Never>?
    private let baseURL: URL
    private let session: URLSession
    private let decoder = JSONDecoder()

    // MARK: - Initialization

    init(baseURL: URL = URL(string: "http://localhost:11434")!) {
        self.baseURL = baseURL

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 5
        config.timeoutIntervalForResource = 30
        self.session = URLSession(configuration: config)
    }

    // MARK: - Polling Control

    func startPolling() {
        guard pollingTask == nil else { return }

        pollingTask = Task {
            while !Task.isCancelled {
                await poll()
                try? await Task.sleep(for: .seconds(1))
            }
        }
    }

    func stopPolling() {
        pollingTask?.cancel()
        pollingTask = nil
    }

    // MARK: - API Methods

    private func poll() async {
        // Snapshot: fetch running models
        let url = baseURL.appendingPathComponent("api/ps")

        do {
            let (data, response) = try await session.data(from: url)

            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else {
                isConnected = false
                activeModel = nil
                return
            }

            let psResponse = try decoder.decode(PSResponse.self, from: data)

            // Update state atomically within actor
            isConnected = true
            activeModel = psResponse.models.first.map(ModelInfo.init)

        } catch {
            isConnected = false
            activeModel = nil
        }
    }

    func fetchAvailableModels() async {
        let url = baseURL.appendingPathComponent("api/tags")

        do {
            let (data, _) = try await session.data(from: url)
            let response = try decoder.decode(TagsResponse.self, from: data)
            availableModels = response.models.map(ModelInfo.init)
        } catch {
            // Keep existing list on error
        }
    }

    /// Run a generation and measure tok/sec using Ollama's metrics
    func measureGeneration(
        prompt: String,
        model: String
    ) async -> GenerationMetrics? {
        let url = baseURL.appendingPathComponent("api/generate")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = GenerateRequest(model: model, prompt: prompt, stream: false)
        request.httpBody = try? JSONEncoder().encode(body)

        isGenerating = true
        defer { isGenerating = false }

        do {
            let (data, _) = try await session.data(for: request)
            let response = try decoder.decode(GenerateResponse.self, from: data)

            // Calculate tok/sec from Ollama's metrics
            // eval_duration is in nanoseconds
            let tokPerSec = Double(response.evalCount) / (Double(response.evalDuration) / 1_000_000_000)

            tokensPerSecond = tokPerSec

            return GenerationMetrics(
                tokensPerSecond: tokPerSec,
                totalTokens: response.evalCount,
                promptTokens: response.promptEvalCount,
                totalDuration: Double(response.totalDuration) / 1_000_000_000,
                loadDuration: Double(response.loadDuration) / 1_000_000_000
            )
        } catch {
            return nil
        }
    }
}

// MARK: - Response Types

struct PSResponse: Codable {
    let models: [PSModel]
}

struct PSModel: Codable {
    let name: String
    let model: String
    let size: Int64
    let digest: String
    let details: ModelDetails?
    let sizeVram: Int64?

    enum CodingKeys: String, CodingKey {
        case name, model, size, digest, details
        case sizeVram = "size_vram"
    }
}

struct ModelDetails: Codable {
    let family: String?
    let parameterSize: String?
    let quantizationLevel: String?

    enum CodingKeys: String, CodingKey {
        case family
        case parameterSize = "parameter_size"
        case quantizationLevel = "quantization_level"
    }
}

struct GenerateRequest: Codable {
    let model: String
    let prompt: String
    let stream: Bool
}

struct GenerateResponse: Codable {
    let response: String
    let done: Bool
    let totalDuration: Int64        // nanoseconds
    let loadDuration: Int64         // nanoseconds
    let promptEvalCount: Int        // tokens in prompt
    let promptEvalDuration: Int64   // nanoseconds
    let evalCount: Int              // generated tokens
    let evalDuration: Int64         // nanoseconds

    enum CodingKeys: String, CodingKey {
        case response, done
        case totalDuration = "total_duration"
        case loadDuration = "load_duration"
        case promptEvalCount = "prompt_eval_count"
        case promptEvalDuration = "prompt_eval_duration"
        case evalCount = "eval_count"
        case evalDuration = "eval_duration"
    }
}

struct GenerationMetrics {
    let tokensPerSecond: Double
    let totalTokens: Int
    let promptTokens: Int
    let totalDuration: Double    // seconds
    let loadDuration: Double     // seconds
}
```

### 6.4 AppState with @Observable

```swift
// File: MLXDash/App/AppState.swift
import Foundation
import Observation
import SwiftUI

/// Central app state using @Observable macro
///
/// Note: @Observable provides better performance than ObservableObject
/// because views only re-render when accessed properties change.
@Observable
final class AppState {
    // MARK: - Services (Actors)

    let ollamaService: OllamaService
    let systemMetricsService: SystemMetricsService
    let benchmarkService: BenchmarkService

    // MARK: - UI State

    var selectedTab: Tab = .metrics
    var isPreferencesOpen = false

    enum Tab: String, CaseIterable {
        case metrics = "Metrics"
        case benchmark = "Benchmark"
        case history = "History"
    }

    // MARK: - Computed Properties (from actor state)

    /// Snapshot of current model (updated by polling)
    var currentModel: ModelInfo? {
        // This will be updated via observation
        _currentModel
    }
    private var _currentModel: ModelInfo?

    var isOllamaConnected: Bool {
        _isConnected
    }
    private var _isConnected = false

    var currentTokensPerSecond: Double {
        _tokensPerSecond
    }
    private var _tokensPerSecond: Double = 0

    // MARK: - Initialization

    init() {
        self.ollamaService = OllamaService()
        self.systemMetricsService = SystemMetricsService()
        self.benchmarkService = BenchmarkService()
    }

    // MARK: - Lifecycle

    func start() {
        // Start polling tasks
        Task {
            await ollamaService.startPolling()
            await systemMetricsService.startPolling()
        }

        // Start observation loop
        Task {
            await observeServices()
        }
    }

    func stop() {
        Task {
            await ollamaService.stopPolling()
            await systemMetricsService.stopPolling()
        }
    }

    /// Observe actor state changes and update @Observable properties
    private func observeServices() async {
        // Poll actor state periodically to update observable properties
        // This bridges actor isolation with SwiftUI observation
        while true {
            _currentModel = await ollamaService.activeModel
            _isConnected = await ollamaService.isConnected
            _tokensPerSecond = await ollamaService.tokensPerSecond

            try? await Task.sleep(for: .milliseconds(500))
        }
    }
}

// File: MLXDash/App/MLXDashApp.swift
import SwiftUI

@main
struct MLXDashApp: App {
    @State private var appState = AppState()

    var body: some Scene {
        MenuBarExtra {
            MenuBarView()
                .environment(appState)
        } label: {
            MenuBarLabel()
                .environment(appState)
        }
        .menuBarExtraStyle(.window)

        // Custom preferences window (NOT Settings scene due to MenuBarExtra bug)
        Window("Preferences", id: "preferences") {
            PreferencesView()
                .environment(appState)
        }
        .windowStyle(.hiddenTitleBar)
        .windowResizability(.contentSize)
        .defaultPosition(.center)
    }

    init() {
        // Start services on launch
        appState.start()
    }
}
```

### 6.5 Implementation Task List (Phase 1)

| Day | Task ID | Task | Hours | Dependencies | Deliverable |
|-----|---------|------|-------|--------------|-------------|
| 1 | P1.1 | Create Xcode project with GRDB/GRDBQuery packages | 2 | None | Project compiles |
| 1 | P1.2 | Implement AppDatabase with GRDB migrations | 3 | P1.1 | Database creates tables |
| 1 | P1.3 | Implement Session and Benchmark GRDB records | 2 | P1.2 | CRUD operations work |
| 2 | P1.4 | Implement OllamaService actor with polling | 4 | P1.1 | Detects running models |
| 2 | P1.5 | Implement AppState with @Observable | 3 | P1.4 | State updates UI |
| 3 | P1.6 | Implement SystemMetricsService actor | 4 | P1.1 | Memory, thermal metrics |
| 3 | P1.7 | Build MenuBarLabel with dynamic display | 2 | P1.5 | Shows tok/s or idle |
| 4 | P1.8 | Build MenuBarView main container | 3 | P1.7 | Opens on click |
| 4 | P1.9 | Build MetricsView with all sections | 4 | P1.6, P1.8 | Shows all metrics |
| 5 | P1.10 | Implement BenchmarkService actor | 4 | P1.4, P1.3 | Runs 10-prompt benchmark |
| 5 | P1.11 | Build BenchmarkView with progress | 3 | P1.10 | Shows benchmark running |
| 6 | P1.12 | Build HistoryView with @Query and Charts | 4 | P1.3 | Shows historical data |
| 6 | P1.13 | Build PreferencesWindow (not SettingsLink) | 3 | P1.1 | All settings work |
| 7 | P1.14 | Create app icon and menu bar assets | 2 | None | Icons in all sizes |
| 7 | P1.15 | Write unit tests for services | 4 | All services | 80%+ coverage |
| 8 | P1.16 | Integration testing with live Ollama | 3 | All above | End-to-end works |
| 8 | P1.17 | Memory profiling with Instruments | 2 | P1.16 | <50MB footprint |
| 9 | P1.18 | Code signing configuration | 2 | Dev ID cert | Signed app |
| 9 | P1.19 | DMG creation and notarization | 3 | P1.18 | Notarized DMG |
| 10 | P1.20 | Documentation and README | 3 | P1.19 | Complete docs |

**Total: ~60 hours across 10 days**

---

## 7. Phase 2: MLXCache - Complete Specification

### 7.1 Architecture (UPDATED with HF Cache)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLI Entry (Typer)                             │
│  mlx-cache [status|add|remove|link|unlink|clean|stats|config|sync|scan]│
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
         ▼                           ▼                           ▼
┌─────────────────────┐    ┌──────────────────┐    ┌──────────────────────┐
│    CacheManager     │    │     Registry     │    │    ConfigManager     │
│                     │    │    (SQLite)      │    │       (YAML)         │
│  - add_model()      │    │                  │    │                      │
│  - remove_model()   │    │  - models table  │    │  - load()            │
│  - sync_ollama()    │    │  - apps table    │    │  - save()            │
│  - sync_hf_cache()  │◄───│  - usage table   │    │  - get/set()         │
│  - calculate_savings│    │                  │    │                      │
└─────────┬───────────┘    └────────┬─────────┘    └──────────────────────┘
          │                         │
          ▼                         │
┌─────────────────────────────────────────────────────────────────────────┐
│                              Sources                                     │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌──────────┐ │
│  │  HuggingFace  │  │ HuggingFace   │  │    Ollama     │  │  Local   │ │
│  │    (Download) │  │   (Cache)     │  │  (Symlink)    │  │ (Import) │ │
│  │               │  │    NEW!       │  │               │  │          │ │
│  │ hf://org/mod  │  │ Scans         │  │ ollama://m:t  │  │ file://  │ │
│  │               │  │ ~/.cache/     │  │               │  │          │ │
│  │ - download()  │  │ huggingface/  │  │ - symlink()   │  │ - copy() │ │
│  │ - verify()    │  │               │  │ - verify()    │  │          │ │
│  └───────────────┘  └───────────────┘  └───────────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Deduplication Engine                            │
│                                                                          │
│  Scans ALL sources:                                                      │
│  - ~/.ollama/models/           (25GB - Ollama cache)                    │
│  - ~/.cache/huggingface/hub/   (22GB - HuggingFace cache)               │
│  - ~/.mlx-cache/models/        (MLXCache managed)                       │
│                                                                          │
│  Identifies duplicates by:                                              │
│  - SHA256 checksum matching                                             │
│  - Model name/version matching                                          │
│  - File content comparison                                              │
│                                                                          │
│  Deduplication strategy:                                                │
│  - Create symlinks to canonical location                                │
│  - Track in registry with is_symlink flag                               │
│  - Calculate and display savings                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 UV-Based Project Setup

```toml
# File: mlx-cache/pyproject.toml

[project]
name = "mlx-cache"
version = "0.1.0"
description = "Unified model cache for MLX and Ollama on Apple Silicon"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
authors = [
    { name = "Your Name", email = "you@example.com" }
]
keywords = ["mlx", "ollama", "llm", "cache", "apple-silicon", "deduplication"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: MacOS",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]

dependencies = [
    "typer>=0.21.0",
    "rich>=14.0.0",
    "httpx>=0.28.0",
    "huggingface-hub>=0.36.0",
    "pyyaml>=6.0",
    "aiosqlite>=0.22.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=9.0",
    "pytest-cov>=5.0",
    "pytest-asyncio>=1.3",
    "ruff>=0.14",
    "mypy>=1.13",
]

[project.scripts]
mlx-cache = "mlx_cache.cli:app"

[project.urls]
Homepage = "https://github.com/yourusername/mlx-infrastructure-suite"
Documentation = "https://github.com/yourusername/mlx-infrastructure-suite/tree/main/mlx-cache#readme"
Repository = "https://github.com/yourusername/mlx-infrastructure-suite"
Issues = "https://github.com/yourusername/mlx-infrastructure-suite/issues"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/mlx_cache"]

[tool.ruff]
target-version = "py311"
line-length = 100
src = ["src"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "C4", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]
addopts = "-v --cov=mlx_cache --cov-report=term-missing"
```

**UV Commands:**
```bash
# Development setup
cd mlx-cache
uv sync                    # Install all dependencies
uv sync --dev              # Include dev dependencies

# Running
uv run mlx-cache --help    # Run CLI
uv run pytest              # Run tests

# Building
uv build                   # Build wheel and sdist
uv publish                 # Publish to PyPI

# Adding dependencies
uv add httpx               # Add production dep
uv add --dev pytest        # Add dev dep
```

### 7.3 HuggingFace Cache Scanner (NEW)

```python
# File: src/mlx_cache/sources/huggingface_cache.py
"""HuggingFace cache scanner - discovers models in ~/.cache/huggingface/hub/"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .base import Source, SourceResult


@dataclass
class HFCacheModel:
    """A model found in the HuggingFace cache."""

    repo_id: str              # e.g., "mlx-community/Llama-3.2-1B-Instruct-4bit"
    revision: str             # commit hash
    cache_path: Path          # full path to model snapshot
    size_bytes: int           # total size
    files: list[str]          # list of files
    has_safetensors: bool     # has .safetensors files


class HuggingFaceCacheSource(Source):
    """
    Scans the local HuggingFace cache for existing models.

    The HF cache structure is:
    ~/.cache/huggingface/hub/
    ├── models--org--model-name/
    │   ├── blobs/                # Content-addressable storage
    │   │   └── sha256-...
    │   ├── refs/
    │   │   └── main              # Points to snapshot
    │   └── snapshots/
    │       └── <commit-hash>/    # Actual model files (symlinks to blobs)
    │           ├── config.json
    │           ├── model.safetensors
    │           └── tokenizer.json
    """

    def __init__(self, cache_dir: Path | None = None):
        self.hf_cache_dir = cache_dir or Path.home() / ".cache" / "huggingface" / "hub"

    def scan(self) -> list[HFCacheModel]:
        """Scan the HuggingFace cache for all models."""
        models = []

        if not self.hf_cache_dir.exists():
            return models

        for model_dir in self.hf_cache_dir.iterdir():
            if not model_dir.is_dir():
                continue
            if not model_dir.name.startswith("models--"):
                continue

            # Parse model ID from directory name
            # models--org--model-name -> org/model-name
            parts = model_dir.name.split("--")
            if len(parts) < 3:
                continue

            repo_id = "/".join(parts[1:])

            # Find the current snapshot
            snapshot = self._get_current_snapshot(model_dir)
            if not snapshot:
                continue

            # Calculate size and list files
            size, files = self._scan_snapshot(snapshot)
            has_safetensors = any(f.endswith(".safetensors") for f in files)

            models.append(HFCacheModel(
                repo_id=repo_id,
                revision=snapshot.name,
                cache_path=snapshot,
                size_bytes=size,
                files=files,
                has_safetensors=has_safetensors,
            ))

        return models

    def _get_current_snapshot(self, model_dir: Path) -> Path | None:
        """Get the current snapshot directory for a model."""
        refs_dir = model_dir / "refs"
        snapshots_dir = model_dir / "snapshots"

        if not refs_dir.exists() or not snapshots_dir.exists():
            return None

        # Try to read the 'main' ref
        main_ref = refs_dir / "main"
        if main_ref.exists():
            commit = main_ref.read_text().strip()
            snapshot = snapshots_dir / commit
            if snapshot.exists():
                return snapshot

        # Fallback: return most recent snapshot
        snapshots = list(snapshots_dir.iterdir())
        if snapshots:
            return max(snapshots, key=lambda p: p.stat().st_mtime)

        return None

    def _scan_snapshot(self, snapshot: Path) -> tuple[int, list[str]]:
        """Scan a snapshot directory for files and total size."""
        total_size = 0
        files = []

        for item in snapshot.rglob("*"):
            if item.is_file():
                files.append(item.name)
                # Follow symlinks to get actual size
                try:
                    total_size += item.stat().st_size
                except OSError:
                    pass

        return total_size, files

    def resolve(self, repo_id: str) -> SourceResult | None:
        """
        Resolve a HuggingFace model ID to a cached location.

        Args:
            repo_id: HuggingFace model ID (e.g., "mlx-community/Llama-3.2-1B")

        Returns:
            SourceResult if found in cache, None otherwise.
        """
        # Convert repo_id to cache directory name
        dir_name = "models--" + repo_id.replace("/", "--")
        model_dir = self.hf_cache_dir / dir_name

        if not model_dir.exists():
            return None

        snapshot = self._get_current_snapshot(model_dir)
        if not snapshot:
            return None

        size, files = self._scan_snapshot(snapshot)

        return SourceResult(
            source="huggingface-cache",
            identifier=repo_id,
            local_path=snapshot,
            size_bytes=size,
            is_symlink=False,  # It's a real directory
            metadata={
                "revision": snapshot.name,
                "files": files,
            }
        )

    def find_duplicates_with_ollama(
        self,
        ollama_models: list[str]
    ) -> list[tuple[str, str, int]]:
        """
        Find HuggingFace models that might duplicate Ollama models.

        Returns list of (hf_repo_id, ollama_model, estimated_shared_bytes)
        """
        duplicates = []
        hf_models = self.scan()

        for hf_model in hf_models:
            # Simple name matching heuristic
            # e.g., "mlx-community/Llama-3.2-1B" might match "llama3.2:1b"
            hf_name_lower = hf_model.repo_id.lower()

            for ollama_model in ollama_models:
                ollama_name_lower = ollama_model.lower()

                # Extract base model name from HF
                if "/" in hf_name_lower:
                    hf_base = hf_name_lower.split("/")[-1]
                else:
                    hf_base = hf_name_lower

                # Check for common model patterns
                # This is a heuristic - could be improved with model metadata
                if self._models_might_match(hf_base, ollama_name_lower):
                    duplicates.append((
                        hf_model.repo_id,
                        ollama_model,
                        hf_model.size_bytes
                    ))

        return duplicates

    def _models_might_match(self, hf_name: str, ollama_name: str) -> bool:
        """Heuristic to check if two model names might refer to the same model."""
        # Remove common suffixes
        hf_clean = hf_name.replace("-4bit", "").replace("-8bit", "").replace("-bf16", "")
        hf_clean = hf_clean.replace("-instruct", "").replace("-chat", "")

        ollama_clean = ollama_name.replace(":latest", "").replace(":instruct", "")
        ollama_clean = ollama_clean.split(":")[0]  # Remove tag

        # Check for substring matches
        return (
            hf_clean in ollama_clean or
            ollama_clean in hf_clean or
            # Normalize llama naming
            hf_clean.replace("-", "").replace(".", "") ==
            ollama_clean.replace("-", "").replace(".", "")
        )
```

### 7.4 Adapted HuggingFace Download Service

```python
# File: src/mlx_cache/sources/huggingface.py
"""HuggingFace Hub download service - adapted from mlx-hub project."""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import httpx
from huggingface_hub import snapshot_download

logger = logging.getLogger(__name__)

HF_API_BASE = "https://huggingface.co/api"


@dataclass
class ModelFile:
    """Information about a model file."""
    filename: str
    size_bytes: int
    lfs: bool = False


@dataclass
class ModelMetadata:
    """Metadata for a HuggingFace model."""
    model_id: str
    author: str
    model_name: str
    downloads: int
    likes: int
    tags: list[str]
    pipeline_tag: str | None
    library_name: str | None
    total_size_bytes: int = 0
    quantization: str | None = None
    files: list[ModelFile] = field(default_factory=list)

    @property
    def is_mlx(self) -> bool:
        return "mlx" in self.tags or self.library_name == "mlx"

    @property
    def size_gb(self) -> float:
        return self.total_size_bytes / (1024**3)


class HuggingFaceDownloadSource:
    """
    Downloads models from HuggingFace Hub.

    Adapted from mlx-hub/services/huggingface.py (464 lines of tested code).
    """

    def __init__(self, token: str | None = None, cache_dir: Path | None = None):
        import os
        self.token = token or os.environ.get("HF_TOKEN")
        self.cache_dir = cache_dir or Path.home() / ".mlx-cache" / "models"
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._client = httpx.AsyncClient(headers=headers, timeout=30.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_model_info(self, model_id: str) -> ModelMetadata | None:
        """Get detailed information about a model."""
        if not self._validate_model_id(model_id):
            raise ValueError(f"Invalid model ID: {model_id}")

        try:
            response = await self.client.get(f"{HF_API_BASE}/models/{model_id}")
            response.raise_for_status()
            data = response.json()

            metadata = self._parse_model_metadata(data)
            if metadata:
                await self._fetch_model_files(metadata)
            return metadata

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def download(
        self,
        model_id: str,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> Path:
        """
        Download a model from HuggingFace.

        Args:
            model_id: HuggingFace model ID (e.g., "mlx-community/Llama-3.2-3B-4bit")
            progress_callback: Optional callback(filename, downloaded, total)

        Returns:
            Path to downloaded model directory.
        """
        if not self._validate_model_id(model_id):
            raise ValueError(f"Invalid model ID: {model_id}")

        # Create safe directory name
        safe_name = f"hf--{model_id.replace('/', '--')}"
        output_dir = self.cache_dir / safe_name
        output_dir.mkdir(parents=True, exist_ok=True)

        # Download using huggingface_hub
        path = await asyncio.to_thread(
            snapshot_download,
            repo_id=model_id,
            local_dir=str(output_dir),
            token=self.token,
        )

        return Path(path)

    def _validate_model_id(self, model_id: str) -> bool:
        """Validate model ID format (prevents path traversal)."""
        if not model_id or len(model_id) > 256:
            return False
        if model_id.count("/") != 1:
            return False
        pattern = r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$"
        return bool(re.match(pattern, model_id))

    def _parse_model_metadata(self, data: dict) -> ModelMetadata | None:
        """Parse API response into ModelMetadata."""
        try:
            model_id = data.get("modelId") or data.get("id", "")
            if "/" in model_id:
                author, model_name = model_id.split("/", 1)
            else:
                author, model_name = "", model_id

            tags = data.get("tags", [])
            quantization = self._detect_quantization(model_id, tags)

            return ModelMetadata(
                model_id=model_id,
                author=author,
                model_name=model_name,
                downloads=data.get("downloads", 0),
                likes=data.get("likes", 0),
                tags=tags,
                pipeline_tag=data.get("pipeline_tag"),
                library_name=data.get("library_name"),
                quantization=quantization,
            )
        except Exception as e:
            logger.warning(f"Failed to parse model metadata: {e}")
            return None

    def _detect_quantization(self, model_id: str, tags: list[str]) -> str | None:
        """Detect quantization level from model ID and tags."""
        model_lower = model_id.lower()

        patterns = [
            (r"(\d+)bit", lambda m: f"{m.group(1)}-bit"),
            (r"q(\d+)_k_m", lambda m: f"Q{m.group(1)}_K_M"),
            (r"q(\d+)", lambda m: f"Q{m.group(1)}"),
            (r"fp16", lambda _: "FP16"),
            (r"bf16", lambda _: "BF16"),
        ]

        for pattern, formatter in patterns:
            match = re.search(pattern, model_lower)
            if match:
                return formatter(match)

        for tag in tags:
            if "4bit" in tag.lower():
                return "4-bit"
            if "8bit" in tag.lower():
                return "8-bit"

        return None

    async def _fetch_model_files(self, metadata: ModelMetadata) -> None:
        """Fetch file list and calculate total size."""
        try:
            response = await self.client.get(
                f"{HF_API_BASE}/models/{metadata.model_id}/tree/main"
            )
            response.raise_for_status()
            files = response.json()

            total_size = 0
            model_files = []

            for f in files:
                if f.get("type") == "file":
                    size = f.get("size", 0)
                    lfs_info = f.get("lfs")
                    if lfs_info:
                        size = lfs_info.get("size", size)

                    model_files.append(ModelFile(
                        filename=f.get("path", ""),
                        size_bytes=size,
                        lfs=lfs_info is not None,
                    ))
                    total_size += size

            metadata.files = model_files
            metadata.total_size_bytes = total_size

        except httpx.HTTPError as e:
            logger.warning(f"Could not fetch files for {metadata.model_id}: {e}")
```

### 7.5 Implementation Task List (Phase 2)

| Day | Task ID | Task | Hours | Dependencies | Deliverable |
|-----|---------|------|-------|--------------|-------------|
| 1 | P2.1 | Create UV-based project structure | 2 | None | `uv sync` works |
| 1 | P2.2 | Implement Typer CLI scaffold | 2 | P2.1 | All commands stubbed |
| 1 | P2.3 | Implement SQLite registry | 3 | P2.1 | CRUD operations work |
| 2 | P2.4 | Adapt HuggingFace download source | 4 | P2.3 | Download works |
| 2 | P2.5 | Implement HuggingFace cache scanner (NEW) | 3 | P2.3 | Scans HF cache |
| 3 | P2.6 | Implement Ollama symlink source | 4 | P2.3 | Symlinks created |
| 3 | P2.7 | Implement `add` and `remove` commands | 3 | P2.4, P2.6 | Add/remove work |
| 4 | P2.8 | Implement `status` with Rich tables | 2 | P2.7 | Pretty output |
| 4 | P2.9 | Implement `sync` for Ollama | 2 | P2.6 | Syncs all Ollama |
| 4 | P2.10 | Implement `scan` for HF cache (NEW) | 2 | P2.5 | Scans HF cache |
| 5 | P2.11 | Implement `link` and `unlink` | 3 | P2.3 | App registration |
| 5 | P2.12 | Implement deduplication engine | 4 | P2.5, P2.6 | Finds duplicates |
| 6 | P2.13 | Implement `clean` command | 2 | P2.11, P2.12 | Cleans orphaned |
| 6 | P2.14 | Implement `stats` command | 2 | P2.12 | Shows savings |
| 6 | P2.15 | Implement `config` command | 2 | P2.1 | Config CRUD |
| 7 | P2.16 | Write unit tests | 4 | All above | 90%+ coverage |
| 7 | P2.17 | Write integration tests | 3 | P2.16 | E2E tests pass |
| 8 | P2.18 | MLXDash integration (--json) | 2 | P2.8 | JSON output works |
| 8 | P2.19 | Documentation | 3 | All | Complete README |
| 9 | P2.20 | PyPI packaging with UV | 2 | P2.19 | Published |

**Total: ~55 hours across 9 days**

---

## 8. Phase 3: SwiftMLX - Complete Specification

### 8.1 Package.swift (UPDATED)

```swift
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SwiftMLX",
    platforms: [
        .macOS(.v14),
        .iOS(.v17),  // Future support
    ],
    products: [
        .library(
            name: "SwiftMLX",
            targets: ["SwiftMLX"]
        ),
        .library(
            name: "SwiftMLXUI",
            targets: ["SwiftMLXUI"]
        ),
    ],
    dependencies: [
        // Optional: GRDB for local caching (if needed)
        // .package(url: "https://github.com/groue/GRDB.swift", from: "7.0.0"),
    ],
    targets: [
        .target(
            name: "SwiftMLX",
            dependencies: []
        ),
        .target(
            name: "SwiftMLXUI",
            dependencies: ["SwiftMLX"]
        ),
        .testTarget(
            name: "SwiftMLXTests",
            dependencies: ["SwiftMLX"]
        ),
    ]
)
```

### 8.2 Actor-Isolated Ollama Client

```swift
// File: Sources/SwiftMLX/Client/OllamaClient.swift
import Foundation

/// Actor-isolated HTTP client for Ollama API
///
/// Using an actor ensures thread-safe access to the URLSession
/// and proper isolation for concurrent requests.
public actor OllamaClient {
    private let baseURL: URL
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    public init(baseURL: URL = URL(string: "http://localhost:11434")!) {
        self.baseURL = baseURL

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 300  // 5 min for long generations
        self.session = URLSession(configuration: config)

        self.decoder = JSONDecoder()
        self.encoder = JSONEncoder()
    }

    // MARK: - Generate (Non-Streaming)

    public func generate(
        model: String,
        prompt: String,
        system: String? = nil,
        images: [String]? = nil,  // Base64 encoded
        options: GenerationOptions = .default
    ) async throws -> GenerateResponse {
        let request = GenerateRequest(
            model: model,
            prompt: prompt,
            system: system,
            images: images,
            options: options.toDict(),
            stream: false
        )

        return try await post("api/generate", body: request)
    }

    // MARK: - Generate (Streaming)

    public func streamGenerate(
        model: String,
        prompt: String,
        system: String? = nil,
        options: GenerationOptions = .default
    ) -> AsyncThrowingStream<StreamChunk, Error> {
        AsyncThrowingStream { continuation in
            Task {
                do {
                    let request = GenerateRequest(
                        model: model,
                        prompt: prompt,
                        system: system,
                        images: nil,
                        options: options.toDict(),
                        stream: true
                    )

                    let url = baseURL.appendingPathComponent("api/generate")
                    var urlRequest = URLRequest(url: url)
                    urlRequest.httpMethod = "POST"
                    urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
                    urlRequest.httpBody = try encoder.encode(request)

                    let (bytes, response) = try await session.bytes(for: urlRequest)

                    guard let httpResponse = response as? HTTPURLResponse,
                          httpResponse.statusCode == 200 else {
                        throw OllamaError.serverError
                    }

                    for try await line in bytes.lines {
                        if let data = line.data(using: .utf8),
                           let chunk = try? decoder.decode(StreamChunk.self, from: data) {
                            continuation.yield(chunk)
                            if chunk.done {
                                break
                            }
                        }
                    }

                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }

    // MARK: - List Models

    public func listModels() async throws -> [OllamaModel] {
        let response: TagsResponse = try await get("api/tags")
        return response.models
    }

    // MARK: - Check Running Models

    public func runningModels() async throws -> [RunningModel] {
        let response: PSResponse = try await get("api/ps")
        return response.models
    }

    // MARK: - Private Helpers

    private func get<T: Decodable>(_ path: String) async throws -> T {
        let url = baseURL.appendingPathComponent(path)
        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw OllamaError.serverError
        }

        return try decoder.decode(T.self, from: data)
    }

    private func post<T: Encodable, R: Decodable>(_ path: String, body: T) async throws -> R {
        let url = baseURL.appendingPathComponent(path)
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw OllamaError.serverError
        }

        return try decoder.decode(R.self, from: data)
    }
}

// MARK: - Types

public struct GenerationOptions: Sendable {
    public var temperature: Double
    public var topP: Double
    public var topK: Int
    public var maxTokens: Int
    public var stop: [String]?

    public static let `default` = GenerationOptions(
        temperature: 0.7,
        topP: 0.9,
        topK: 40,
        maxTokens: 2048,
        stop: nil
    )

    func toDict() -> [String: Any] {
        var dict: [String: Any] = [
            "temperature": temperature,
            "top_p": topP,
            "top_k": topK,
            "num_predict": maxTokens,
        ]
        if let stop = stop {
            dict["stop"] = stop
        }
        return dict
    }
}

public enum OllamaError: Error, LocalizedError {
    case serverError
    case notConnected
    case modelNotFound

    public var errorDescription: String? {
        switch self {
        case .serverError: return "Ollama server returned an error"
        case .notConnected: return "Cannot connect to Ollama server"
        case .modelNotFound: return "Model not found"
        }
    }
}
```

### 8.3 Implementation Task List (Phase 3)

| Day | Task ID | Task | Hours | Dependencies | Deliverable |
|-----|---------|------|-------|--------------|-------------|
| 1 | P3.1 | Create Swift Package structure | 2 | None | `swift build` works |
| 1 | P3.2 | Implement OllamaClient actor | 4 | P3.1 | API calls work |
| 2 | P3.3 | Implement MLXModel wrapper | 3 | P3.2 | Model loading works |
| 2 | P3.4 | Implement generate() method | 3 | P3.3 | Text generation works |
| 3 | P3.5 | Implement stream() with AsyncSequence | 4 | P3.3 | Streaming works |
| 3 | P3.6 | Implement analyze() for vision | 3 | P3.3 | Image analysis works |
| 4 | P3.7 | Build ChatView component | 4 | P3.5 | Chat UI works |
| 4 | P3.8 | Build ModelPicker component | 2 | P3.2 | Model selection works |
| 5 | P3.9 | Build PerformanceView component | 2 | P3.3 | Metrics display |
| 5 | P3.10 | Build PromptField component | 2 | P3.1 | Input works |
| 5 | P3.11 | Implement MLXCacheClient | 3 | P2.18 | Cache integration |
| 6 | P3.12 | Create Chat App template | 4 | P3.7 | Template installs |
| 6 | P3.13 | Create Document Analyzer template | 3 | P3.4 | Template works |
| 7 | P3.14 | Create Image Captioner template | 3 | P3.6 | Template works |
| 7 | P3.15 | Build ChatDemo example | 3 | P3.7 | Demo compiles |
| 8 | P3.16 | Build VisionDemo example | 3 | P3.6 | Demo compiles |
| 8 | P3.17 | Write unit tests | 4 | All above | 70%+ coverage |
| 9 | P3.18 | Create template installer script | 2 | P3.12-14 | Installer works |
| 9 | P3.19 | Documentation and tutorials | 4 | All | Complete docs |

**Total: ~58 hours across 9 days**

---

## 9. Phase 4: Integration & Quality Assurance

### 9.1 Integration Testing Matrix

| Test Scenario | MLXDash | MLXCache | SwiftMLX | Status |
|---------------|---------|----------|----------|--------|
| Ollama not running | Shows disconnected | Handles gracefully | Returns error | Planned |
| mlx-cache not installed | Shows "Install mlx-cache" | N/A | Falls back to Ollama | Planned |
| No models cached | Empty state | Empty state | Empty picker | Planned |
| Large model (14B) | Memory warning | Accurate size | Loads normally | Planned |
| Vision model | Shows as vision | Correct metadata | analyze() works | Planned |
| Concurrent generation | Shows busy | N/A | Queues requests | Planned |
| Cache sync | Updates display | Creates symlinks | Sees new models | Planned |

### 9.2 Performance Targets

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| MLXDash memory | <50MB | Instruments profiling |
| MLXDash CPU idle | <1% | Activity Monitor |
| MLXCache startup | <200ms | `time mlx-cache status` |
| MLXCache sync | <5s | `time mlx-cache sync` |
| SwiftMLX load | <1s | Timer in ModelLoader |
| Tok/sec accuracy | ±5% | Compare to Ollama --verbose |

### 9.3 Test Coverage Targets

| Component | Unit | Integration | E2E | Target |
|-----------|------|-------------|-----|--------|
| MLXDash Services | 80% | Yes | Manual | 80% |
| MLXDash Database | 90% | Yes | - | 90% |
| MLXCache CLI | 90% | Yes | Yes | 90% |
| MLXCache Sources | 80% | Yes | - | 80% |
| SwiftMLX Core | 70% | Yes | - | 70% |
| SwiftMLX UI | Previews | - | Manual | N/A |

---

## 10. Phase 5: Release & Distribution

### 10.1 Release Checklist

```markdown
## Pre-Release Verification

### Code Signing (MLXDash)
- [ ] Developer ID Application certificate installed
- [ ] App signed with `codesign --verify`
- [ ] App notarized with Apple
- [ ] DMG stapled with `xcrun stapler staple`
- [ ] Gatekeeper test: `spctl --assess --type execute`

### Package Publishing (MLXCache)
- [ ] TestPyPI upload successful
- [ ] `pip install --index-url https://test.pypi.org/simple mlx-cache` works
- [ ] PyPI upload successful
- [ ] `pip install mlx-cache` works globally

### Swift Package (SwiftMLX)
- [ ] `swift package dump-package` succeeds
- [ ] Package can be added via Xcode
- [ ] Package can be added via `swift package add`
- [ ] Templates install correctly

### Integration
- [ ] All three tools work together
- [ ] Fresh install scenario tested
- [ ] Update scenario tested

### Documentation
- [ ] All READMEs complete
- [ ] Screenshots current
- [ ] Demo GIFs created
- [ ] Changelog updated
```

### 10.2 Distribution Channels

| Tool | Primary | Secondary | Tertiary |
|------|---------|-----------|----------|
| MLXDash | GitHub Releases (DMG) | Homebrew Cask | - |
| MLXCache | PyPI | GitHub Releases | uv/pip |
| SwiftMLX | GitHub (SPM) | Swift Package Index | - |

### 10.3 Marketing Plan

```yaml
Week 1 (MLXDash Launch):
  - Twitter/X thread with GIF demo
  - Reddit r/LocalLLaMA post
  - Hacker News submission

Week 3 (MLXCache Launch):
  - "Saved 20GB" screenshot posts
  - r/Python, r/MachineLearning
  - Dev.to article

Week 6 (SwiftMLX Launch):
  - Apple Developer Forums
  - Swift Forums post
  - Tutorial blog post

Ongoing:
  - GitHub README with badges
  - Star/download tracking
  - User feedback collection
```

---

## 11. Removed Items & Rationale

### 11.1 Technologies Removed

| Item | Was In | Removed Because |
|------|--------|-----------------|
| `ObservableObject` | MLXDash | @Observable is faster, modern Swift standard |
| Raw SQLite3 C API | MLXDash | GRDB provides type safety, better DX, auto-observation |
| `SettingsLink` | MLXDash | Broken in MenuBarExtra per 2025 research |
| pip-based workflow | MLXCache | UV is 10-100x faster, manages Python versions |
| Hatchling (direct) | MLXCache | UV uses it internally, no explicit mention needed |
| ollama-swift package | SwiftMLX | Custom actor gives full control, no external deps |

### 11.2 Features Deferred to v2

| Feature | Reason for Deferral |
|---------|---------------------|
| Cloud sync for MLXCache | Adds complexity, security concerns |
| Pro tier monetization | Focus on adoption first |
| iOS support for SwiftMLX | macOS MVP first |
| Direct mlx-lm integration | Ollama covers 90% of use cases |
| Custom benchmark prompts | Standard prompts sufficient for v1 |
| Model training in MLXDash | Out of scope for monitoring tool |

### 11.3 Approaches Rejected

| Approach | Why Rejected |
|----------|--------------|
| SwiftData for persistence | Too heavyweight for menu bar app |
| Combine for observation | @Observable is simpler, no publishers needed |
| Poetry for Python | UV is faster, simpler |
| Electron for cross-platform | Native Swift is lighter, Mac-focused |

---

## 12. Appendices

### Appendix A: Research Sources

**Swift/macOS:**
- [Apple @Observable Migration Guide](https://developer.apple.com/documentation/SwiftUI/Migrating-from-the-observable-object-protocol-to-the-observable-macro)
- [GRDB.swift GitHub](https://github.com/groue/GRDB.swift)
- [GRDBQuery GitHub](https://github.com/groue/GRDBQuery)
- [SharingGRDB Point-Free](https://www.pointfree.co/blog/posts/168-sharinggrdb-a-swiftdata-alternative)
- [MenuBarExtra Settings Workaround](https://steipete.me/posts/2025/showing-settings-from-macos-menu-bar-items)
- [Swift Actor Best Practices](https://alexdremov.me/swift-actors-common-problems-and-tips/)

**Python:**
- [UV Package Manager](https://www.datacamp.com/tutorial/python-uv)
- [Typer Documentation](https://typer.tiangolo.com/)

**MLX/Ollama:**
- [Ollama API Usage](https://docs.ollama.com/api/usage)
- [MLX GitHub](https://github.com/ml-explore/mlx)
- [WWDC 2025 MLX Session](https://developer.apple.com/videos/play/wwdc2025/315/)

### Appendix B: Quick Command Reference

```bash
# Development Setup
brew install create-dmg xcbeautify
uv sync --dev  # In mlx-cache directory

# MLXDash
cd mlxdash
swift build
swift test
xcodebuild -scheme MLXDash build

# MLXCache
cd mlx-cache
uv run mlx-cache --help
uv run pytest

# SwiftMLX
cd swiftmlx
swift build
swift test

# Full Test Suite
./scripts/test-all.sh

# Release Build
./scripts/build-release.sh
```

### Appendix C: Environment Variables

```bash
# HuggingFace (optional, for gated models)
export HF_TOKEN="hf_xxx"

# Ollama (if not default)
export OLLAMA_HOST="http://localhost:11434"

# Code Signing
export DEVELOPER_ID="Developer ID Application: Your Name (TEAM_ID)"
export APPLE_ID="your@email.com"
export TEAM_ID="XXXXXXXXXX"
```

---

**Document Version:** 2.0
**Total Estimated Hours:** ~175 hours across 6 weeks
**Critical Blockers:** Developer ID Certificate

*This document supersedes IMPLEMENTATION_PLAN.md and incorporates all research findings.*
