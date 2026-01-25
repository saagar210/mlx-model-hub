# MLX Infrastructure Suite - Complete Implementation Plan

> **A-to-Z Blueprint for Building the Definitive MLX Infrastructure Toolkit**

**Generated:** January 12, 2026
**Target Hardware:** MacBook Pro M4 Pro (48GB RAM), macOS 26.2
**Total Estimated Duration:** 6 weeks

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Environment Analysis](#2-environment-analysis)
3. [Technology Stack Decisions](#3-technology-stack-decisions)
4. [Phase 0: Foundation](#4-phase-0-foundation)
5. [Phase 1: MLXDash](#5-phase-1-mlxdash)
6. [Phase 2: MLXCache](#6-phase-2-mlxcache)
7. [Phase 3: SwiftMLX](#7-phase-3-swiftmlx)
8. [Phase 4: Integration & Release](#8-phase-4-integration--release)
9. [Quality Assurance Strategy](#9-quality-assurance-strategy)
10. [Risk Mitigation](#10-risk-mitigation)
11. [Resources & References](#11-resources--references)

---

## 1. Executive Summary

### 1.1 Project Vision

Build three interconnected tools that establish a complete MLX development ecosystem on Apple Silicon:

| Tool | Purpose | Distribution |
|------|---------|--------------|
| **MLXDash** | Real-time ML workload monitoring in menu bar | Signed DMG |
| **MLXCache** | Unified model weight cache with deduplication | PyPI + pip |
| **SwiftMLX** | Swift Package + Xcode templates for rapid AI apps | SPM + GitHub |

### 1.2 Key Success Metrics

- **MLXDash**: 1,000+ downloads in first month, <50MB memory footprint
- **MLXCache**: 50%+ disk savings (potential: 25GB → 12GB for current setup)
- **SwiftMLX**: 5-minute "Hello World" for AI-powered Mac app

### 1.3 Current Ollama Cache Analysis

```
Current Ollama Models: 25GB
├── deepseek-r1:14b      9.0 GB
├── llama3.2-vision:11b  7.8 GB
├── qwen2.5-coder:7b     4.7 GB
├── qwen2.5:7b           4.7 GB (DUPLICATE base weights!)
└── nomic-embed-text     0.3 GB

Potential Savings with MLXCache: ~4.7GB (18% immediately)
With HuggingFace dedup: Up to 50%
```

---

## 2. Environment Analysis

### 2.1 Hardware Capabilities

```yaml
Machine: MacBook Pro M4 Pro
Chip: Apple M4 Pro (14-core CPU, 20-core GPU)
Memory: 48GB Unified Memory
macOS: 26.2 (Tahoe) - Supports Neural Accelerators
Storage: SSD with ~25GB Ollama models
```

### 2.2 Installed Software Assets

#### Python Environment (3.12.12)
```
# Core ML Stack (EXCELLENT - can leverage directly)
mlx                 0.29.4    # Latest stable MLX
mlx-lm              0.29.1    # LLM support
mlx-vlm             0.3.9     # Vision models
mlx-audio           0.2.9     # Audio models
mlx-omni-server     0.5.1     # OpenAI-compatible server

# CLI Building (PERFECT - modern stack ready)
typer               0.21.1    # Modern CLI framework
click               8.2.1     # Typer's foundation
rich                14.1.0    # Beautiful terminal output

# Data & HTTP
httpx               0.28.1    # Modern HTTP client
huggingface-hub     0.36.0    # Model downloads
pydantic            2.11.7    # Data validation
numpy               2.4.1     # Array operations
```

#### Ollama Setup
```
Version: 0.13.5 (latest stable)
Models: 5 installed (25GB total)
API: http://localhost:11434
```

#### Development Tools
```
# Installed via Homebrew
git, gh              # Version control + GitHub CLI
node, pnpm           # For any web components
python@3.11          # Alternative Python
lazygit, git-delta   # Enhanced git workflow

# NOT Installed (Need to add)
create-dmg           # For DMG packaging
```

#### Code Signing Status
```
Developer ID Certificates: 0 found
Action Required: Generate Developer ID in Apple Developer Portal
```

### 2.3 Existing Related Projects

```
/Users/d/claude-code/ai-tools/
├── mlx-model-hub/        # Full MLX model management (FastAPI + Next.js)
│   └── Can reuse: Model download logic, HuggingFace integration
├── silicon-studio-audit/ # Fine-tuning UI
│   └── Can reuse: MLX training patterns
└── mlx-infrastructure-suite/ # THIS PROJECT
```

---

## 3. Technology Stack Decisions

### 3.1 MLXDash Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **UI Framework** | SwiftUI + MenuBarExtra | Native macOS 14+ API, no AppKit bridging needed |
| **Menu Bar Style** | `.window` style | Allows rich UI (sliders, charts) vs basic `.menu` |
| **Ollama Client** | Custom URLSession | Lightweight, no external dependencies |
| **System Metrics** | IOKit + ProcessInfo | Direct Apple APIs, no private API risk |
| **Database** | SQLite3 (raw C API) | Zero dependencies, ships with macOS |
| **Charts** | Swift Charts | Native, performant, no third-party libs |
| **Architecture** | MVVM + @Observable | Modern Swift observation, no Combine complexity |

**Key Insight from Research**: MenuBarExtra has quirks with SettingsLink - we'll implement a custom preferences window approach as recommended in [Peter Steinberger's 2025 analysis](https://steipete.me/posts/2025/showing-settings-from-macos-menu-bar-items).

### 3.2 MLXCache Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **CLI Framework** | Typer 0.21.1 | Already installed, type-hint based, includes Rich |
| **Output Formatting** | Rich 14.1.0 | Already installed, beautiful tables/progress |
| **HTTP Client** | httpx 0.28.1 | Already installed, async support |
| **Model Downloads** | huggingface_hub 0.36.0 | Already installed, handles auth/gated models |
| **Database** | SQLite3 | Consistent with MLXDash, zero deps |
| **Config Format** | YAML | Human-readable, pyyaml available |
| **Packaging** | Hatchling | Modern, PEP 517 compliant |

**Key Insight**: Typer is the 2025 recommendation over Click for new projects - it provides the same power with cleaner type-hint syntax.

### 3.3 SwiftMLX Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Package Type** | Swift Package (library) | Standard distribution, Xcode integration |
| **Ollama Client** | [ollama-swift](https://github.com/mattt/ollama-swift) | Matt's well-maintained client, tool calling support |
| **Async Model** | Swift Concurrency | Native async/await, AsyncSequence for streaming |
| **UI Components** | SwiftUI | Declarative, composable, modern |
| **Minimum macOS** | 14.0 (Sonoma) | MenuBarExtra, @Observable, Swift Charts |

**Alternative Considered**: [OllamaKit](https://github.com/kevinhermawan/OllamaKit) - tailored for Ollamac app, less general-purpose.

---

## 4. Phase 0: Foundation

### 4.1 Repository Structure

```
mlx-infrastructure-suite/
├── .github/
│   ├── workflows/
│   │   ├── mlxdash-build.yml      # Swift build + test
│   │   ├── mlxcache-test.yml      # Python test + lint
│   │   ├── swiftmlx-build.yml     # Package build + test
│   │   └── release.yml            # Coordinated release
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml
│   │   ├── feature_request.yml
│   │   └── config.yml
│   └── PULL_REQUEST_TEMPLATE.md
├── mlxdash/                        # Swift/Xcode project
│   ├── MLXDash.xcodeproj/
│   ├── MLXDash/
│   │   ├── App/
│   │   ├── Views/
│   │   ├── Services/
│   │   ├── Models/
│   │   └── Resources/
│   ├── MLXDashTests/
│   └── README.md
├── mlx-cache/                      # Python package
│   ├── src/
│   │   └── mlx_cache/
│   │       ├── __init__.py
│   │       ├── cli.py
│   │       ├── cache.py
│   │       ├── registry.py
│   │       ├── sources/
│   │       ├── dedup.py
│   │       └── config.py
│   ├── tests/
│   ├── pyproject.toml
│   └── README.md
├── swiftmlx/                       # Swift Package
│   ├── Package.swift
│   ├── Sources/
│   │   ├── SwiftMLX/
│   │   └── SwiftMLXUI/
│   ├── Templates/
│   ├── Examples/
│   ├── Tests/
│   └── README.md
├── shared/
│   ├── config-schema.yaml          # Shared config format
│   └── assets/                     # Shared icons, branding
├── docs/
│   ├── architecture.md
│   ├── api-reference.md
│   └── tutorials/
├── .taskmaster/
│   ├── tasks/
│   └── docs/
├── CLAUDE.md
├── STRATEGY.md
├── IMPLEMENTATION_PLAN.md          # This document
├── README.md
├── LICENSE
├── CONTRIBUTING.md
└── CODE_OF_CONDUCT.md
```

### 4.2 Prerequisites Checklist

```bash
# Required Installations
brew install create-dmg                    # DMG creation
brew install xcbeautify                    # Pretty xcodebuild output

# Code Signing Setup (MANUAL)
# 1. Login to developer.apple.com
# 2. Certificates, Identifiers & Profiles → Certificates
# 3. Create "Developer ID Application" certificate
# 4. Download and install in Keychain

# Verify Setup
security find-identity -v -p codesigning  # Should show Developer ID

# Python Development Setup
pip install build twine pytest-cov ruff   # Packaging + testing + linting
```

### 4.3 Initial Repository Setup Tasks

| Task | Command/Action | Verification |
|------|----------------|--------------|
| Initialize git | `git init` | `.git/` exists |
| Create .gitignore | Multi-language template | Swift, Python, Xcode artifacts ignored |
| Create README.md | Project overview | Renders on GitHub |
| Create LICENSE | MIT license | `LICENSE` file exists |
| Setup pre-commit | Python hooks | `pre-commit run --all-files` passes |
| Create GitHub repo | `gh repo create mlx-infrastructure-suite --public` | Visible on GitHub |
| Setup branch protection | GitHub Settings | `main` protected |

---

## 5. Phase 1: MLXDash

### 5.1 Architecture Deep Dive

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MLXDashApp (@main)                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    MenuBarExtra                              │   │
│  │  ┌─────────────┐  ┌──────────────────────────────────────┐  │   │
│  │  │ Status Icon │  │         .window Style                 │  │   │
│  │  │ "42 tok/s"  │  │  ┌────────────────────────────────┐  │  │   │
│  │  └─────────────┘  │  │        MenuBarView             │  │  │   │
│  │                   │  │  ├── ModelSection              │  │  │   │
│  │                   │  │  ├── MetricsSection            │  │  │   │
│  │                   │  │  ├── QuickActions              │  │  │   │
│  │                   │  │  └── Footer                    │  │  │   │
│  │                   │  └────────────────────────────────┘  │  │   │
│  │                   └──────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│                         Services Layer                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐   │
│  │  OllamaService   │  │ SystemMetrics    │  │  HistoryService │   │
│  │  @Observable     │  │ Service          │  │                 │   │
│  │                  │  │ @Observable      │  │                 │   │
│  │  - pollingTask   │  │                  │  │  - SQLite DB    │   │
│  │  - activeModel   │  │  - gpuUsage      │  │  - sessions     │   │
│  │  - tokensPerSec  │  │  - memoryUsage   │  │  - benchmarks   │   │
│  │  - isGenerating  │  │  - thermalState  │  │                 │   │
│  └──────────────────┘  └──────────────────┘  └─────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│                        Data Models                                  │
│  ┌──────────────┐  ┌────────────────┐  ┌────────────────────────┐  │
│  │  ModelInfo   │  │  SystemMetrics │  │  BenchmarkResult       │  │
│  │  - name      │  │  - gpuPercent  │  │  - modelName           │  │
│  │  - size      │  │  - memoryGB    │  │  - avgTokensPerSec     │  │
│  │  - family    │  │  - thermal     │  │  - p50LatencyMs        │  │
│  │  - params    │  │  - available   │  │  - p95LatencyMs        │  │
│  └──────────────┘  └────────────────┘  └────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 Detailed Implementation Tasks

#### 5.2.1 Project Setup (Day 1, ~4 hours)

```swift
// File: MLXDash/App/MLXDashApp.swift
import SwiftUI

@main
struct MLXDashApp: App {
    @State private var ollamaService = OllamaService()
    @State private var systemMetrics = SystemMetricsService()

    var body: some Scene {
        MenuBarExtra {
            MenuBarView()
                .environment(ollamaService)
                .environment(systemMetrics)
        } label: {
            MenuBarLabel()
                .environment(ollamaService)
        }
        .menuBarExtraStyle(.window)

        // Settings window (separate from menu bar)
        Settings {
            PreferencesView()
        }
    }
}
```

**Info.plist Configuration:**
```xml
<!-- Make app agent (no Dock icon) -->
<key>LSUIElement</key>
<true/>
<!-- Minimum macOS version -->
<key>LSMinimumSystemVersion</key>
<string>14.0</string>
```

**Tasks:**
1. Create Xcode project: macOS App, SwiftUI lifecycle
2. Configure MenuBarExtra with `.window` style
3. Set `LSUIElement = YES` in Info.plist
4. Create directory structure: App/, Views/, Services/, Models/, Resources/
5. Add placeholder views for all major components
6. Verify: App shows in menu bar, click opens window

#### 5.2.2 Ollama Service Implementation (Day 2, ~6 hours)

```swift
// File: MLXDash/Services/OllamaService.swift
import Foundation
import Observation

@Observable
final class OllamaService {
    private(set) var activeModel: ModelInfo?
    private(set) var availableModels: [ModelInfo] = []
    private(set) var isConnected = false
    private(set) var tokensPerSecond: Double = 0
    private(set) var isGenerating = false

    private var pollingTask: Task<Void, Never>?
    private let baseURL: URL
    private let session: URLSession

    init(baseURL: URL = URL(string: "http://localhost:11434")!) {
        self.baseURL = baseURL
        self.session = URLSession(configuration: .default)
    }

    func startPolling() {
        pollingTask = Task {
            while !Task.isCancelled {
                await fetchActiveModel()
                try? await Task.sleep(for: .seconds(1))
            }
        }
    }

    func stopPolling() {
        pollingTask?.cancel()
        pollingTask = nil
    }

    private func fetchActiveModel() async {
        let url = baseURL.appendingPathComponent("api/ps")
        do {
            let (data, _) = try await session.data(from: url)
            let response = try JSONDecoder().decode(PSResponse.self, from: data)
            await MainActor.run {
                self.isConnected = true
                self.activeModel = response.models.first.map(ModelInfo.init)
            }
        } catch {
            await MainActor.run {
                self.isConnected = false
                self.activeModel = nil
            }
        }
    }

    func fetchAvailableModels() async {
        let url = baseURL.appendingPathComponent("api/tags")
        do {
            let (data, _) = try await session.data(from: url)
            let response = try JSONDecoder().decode(TagsResponse.self, from: data)
            await MainActor.run {
                self.availableModels = response.models.map(ModelInfo.init)
            }
        } catch {
            // Handle error
        }
    }
}

// File: MLXDash/Models/OllamaModels.swift
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

struct ModelInfo: Identifiable {
    let id = UUID()
    let name: String
    let displayName: String
    let sizeBytes: Int64
    let vramBytes: Int64?
    let family: String?
    let parameterSize: String?

    var sizeGB: Double { Double(sizeBytes) / 1_073_741_824 }
    var vramGB: Double? { vramBytes.map { Double($0) / 1_073_741_824 } }

    init(from model: PSModel) {
        self.name = model.name
        self.displayName = model.name.components(separatedBy: ":").first ?? model.name
        self.sizeBytes = model.size
        self.vramBytes = model.sizeVram
        self.family = model.details?.family
        self.parameterSize = model.details?.parameterSize
    }
}
```

**Tasks:**
1. Implement `OllamaService` with `@Observable`
2. Add polling for `/api/ps` endpoint
3. Add `/api/tags` for available models list
4. Create `ModelInfo` data model
5. Handle connection errors gracefully
6. Add `isConnected` state for UI feedback
7. Unit tests with mocked URLProtocol

#### 5.2.3 System Metrics Service (Day 3, ~6 hours)

```swift
// File: MLXDash/Services/SystemMetricsService.swift
import Foundation
import Observation
import IOKit

@Observable
final class SystemMetricsService {
    private(set) var gpuUtilization: Double = 0
    private(set) var memoryUsedGB: Double = 0
    private(set) var memoryTotalGB: Double = 48.0 // From system_profiler
    private(set) var thermalState: ProcessInfo.ThermalState = .nominal

    private var pollingTask: Task<Void, Never>?

    func startPolling() {
        pollingTask = Task {
            while !Task.isCancelled {
                await updateMetrics()
                try? await Task.sleep(for: .seconds(2))
            }
        }
    }

    func stopPolling() {
        pollingTask?.cancel()
    }

    private func updateMetrics() async {
        // Memory: Use vm_statistics64
        var stats = vm_statistics64()
        var count = mach_msg_type_number_t(MemoryLayout<vm_statistics64>.size / MemoryLayout<integer_t>.size)
        let result = withUnsafeMutablePointer(to: &stats) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                host_statistics64(mach_host_self(), HOST_VM_INFO64, $0, &count)
            }
        }

        if result == KERN_SUCCESS {
            let pageSize = UInt64(vm_page_size)
            let activeBytes = UInt64(stats.active_count) * pageSize
            let wiredBytes = UInt64(stats.wire_count) * pageSize
            let compressedBytes = UInt64(stats.compressor_page_count) * pageSize
            let usedBytes = activeBytes + wiredBytes + compressedBytes

            await MainActor.run {
                self.memoryUsedGB = Double(usedBytes) / 1_073_741_824
            }
        }

        // Thermal state
        let thermal = ProcessInfo.processInfo.thermalState
        await MainActor.run {
            self.thermalState = thermal
        }

        // GPU utilization via IOKit (approximation)
        await updateGPUMetrics()
    }

    private func updateGPUMetrics() async {
        // Note: Full GPU utilization requires Metal Performance HUD or private APIs
        // Using IOKit to get accelerator statistics where available

        var iterator: io_iterator_t = 0
        let matching = IOServiceMatching("AppleM4Pro")  // Adjust for chip family

        if IOServiceGetMatchingServices(kIOMasterPortDefault, matching, &iterator) == KERN_SUCCESS {
            var service = IOIteratorNext(iterator)
            while service != 0 {
                var properties: Unmanaged<CFMutableDictionary>?
                if IORegistryEntryCreateCFProperties(service, &properties, kCFAllocatorDefault, 0) == KERN_SUCCESS {
                    if let props = properties?.takeRetainedValue() as? [String: Any] {
                        // Extract GPU stats if available
                        // This is chip-specific and may require experimentation
                    }
                }
                IOObjectRelease(service)
                service = IOIteratorNext(iterator)
            }
            IOObjectRelease(iterator)
        }

        // Fallback: Use a placeholder or Metal activity sampling
        await MainActor.run {
            self.gpuUtilization = 0 // Placeholder until Metal integration
        }
    }
}
```

**Tasks:**
1. Implement memory metrics using `vm_statistics64`
2. Implement thermal state using `ProcessInfo`
3. Research IOKit for M4 Pro GPU metrics
4. Add fallback for unavailable metrics
5. Verify accuracy against Activity Monitor
6. Add unit tests for metric calculations

#### 5.2.4 Menu Bar UI (Day 4, ~6 hours)

```swift
// File: MLXDash/Views/MenuBarLabel.swift
import SwiftUI

struct MenuBarLabel: View {
    @Environment(OllamaService.self) private var ollama

    var body: some View {
        Group {
            if ollama.isGenerating {
                Text("\(Int(ollama.tokensPerSecond)) tok/s")
                    .monospacedDigit()
            } else if ollama.activeModel != nil {
                Image(systemName: "brain")
            } else if ollama.isConnected {
                Image(systemName: "circle.fill")
                    .foregroundStyle(.green)
            } else {
                Image(systemName: "circle")
                    .foregroundStyle(.secondary)
            }
        }
    }
}

// File: MLXDash/Views/MenuBarView.swift
import SwiftUI

struct MenuBarView: View {
    @Environment(OllamaService.self) private var ollama
    @Environment(SystemMetricsService.self) private var system

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                Image(systemName: "brain.head.profile")
                    .font(.title2)
                Text("MLXDash")
                    .font(.headline)
                Spacer()
                ConnectionIndicator(isConnected: ollama.isConnected)
            }

            Divider()

            // Model Section
            ModelSection(model: ollama.activeModel)

            // Metrics Section
            MetricsSection(
                tokensPerSec: ollama.tokensPerSecond,
                memoryUsed: system.memoryUsedGB,
                memoryTotal: system.memoryTotalGB,
                gpuPercent: system.gpuUtilization,
                thermal: system.thermalState
            )

            Divider()

            // Quick Actions
            QuickActionsSection()

            Divider()

            // Footer
            HStack {
                Button("Preferences...") {
                    NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
                }
                .buttonStyle(.link)

                Spacer()

                Button("Quit") {
                    NSApplication.shared.terminate(nil)
                }
                .buttonStyle(.link)
                .foregroundStyle(.secondary)
            }
            .font(.caption)
        }
        .padding()
        .frame(width: 300)
    }
}

// File: MLXDash/Views/Components/ModelSection.swift
struct ModelSection: View {
    let model: ModelInfo?

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Label("Current Model", systemImage: "cube.box")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            if let model = model {
                HStack {
                    Text(model.displayName)
                        .font(.title3)
                        .fontWeight(.medium)
                    Spacer()
                    if let params = model.parameterSize {
                        Text(params)
                            .font(.caption)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(.tertiary)
                            .clipShape(Capsule())
                    }
                }

                if let vram = model.vramGB {
                    Text(String(format: "VRAM: %.1f GB", vram))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            } else {
                Text("No model loaded")
                    .foregroundStyle(.secondary)
            }
        }
    }
}

// File: MLXDash/Views/Components/MetricsSection.swift
struct MetricsSection: View {
    let tokensPerSec: Double
    let memoryUsed: Double
    let memoryTotal: Double
    let gpuPercent: Double
    let thermal: ProcessInfo.ThermalState

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Performance
            MetricRow(
                icon: "speedometer",
                label: "Performance",
                value: String(format: "%.1f tok/s", tokensPerSec)
            )

            // Memory
            VStack(alignment: .leading, spacing: 2) {
                MetricRow(
                    icon: "memorychip",
                    label: "Memory",
                    value: String(format: "%.1f / %.0f GB", memoryUsed, memoryTotal)
                )
                ProgressView(value: memoryUsed, total: memoryTotal)
                    .tint(memoryUsed / memoryTotal > 0.8 ? .orange : .blue)
            }

            // GPU
            MetricRow(
                icon: "gpu",
                label: "GPU",
                value: String(format: "%.0f%%", gpuPercent * 100)
            )

            // Thermal
            MetricRow(
                icon: thermalIcon,
                label: "Thermal",
                value: thermalLabel
            )
            .foregroundStyle(thermalColor)
        }
    }

    private var thermalIcon: String {
        switch thermal {
        case .nominal: return "thermometer.low"
        case .fair: return "thermometer.medium"
        case .serious: return "thermometer.high"
        case .critical: return "exclamationmark.triangle.fill"
        @unknown default: return "thermometer"
        }
    }

    private var thermalLabel: String {
        switch thermal {
        case .nominal: return "Normal"
        case .fair: return "Elevated"
        case .serious: return "High"
        case .critical: return "Critical"
        @unknown default: return "Unknown"
        }
    }

    private var thermalColor: Color {
        switch thermal {
        case .nominal: return .primary
        case .fair: return .yellow
        case .serious: return .orange
        case .critical: return .red
        @unknown default: return .primary
        }
    }
}

struct MetricRow: View {
    let icon: String
    let label: String
    let value: String

    var body: some View {
        HStack {
            Image(systemName: icon)
                .frame(width: 20)
            Text(label)
            Spacer()
            Text(value)
                .monospacedDigit()
                .foregroundStyle(.secondary)
        }
        .font(.callout)
    }
}
```

**Tasks:**
1. Create `MenuBarLabel` with dynamic content
2. Build `MenuBarView` main container
3. Implement `ModelSection` component
4. Implement `MetricsSection` with progress bars
5. Add `QuickActionsSection` with Benchmark, History buttons
6. Add Quit button (essential for agent apps)
7. Test light/dark mode rendering
8. Add SF Symbol icons throughout

#### 5.2.5 SQLite Database Layer (Day 5, ~4 hours)

```swift
// File: MLXDash/Services/HistoryService.swift
import Foundation
import SQLite3

final class HistoryService {
    private var db: OpaquePointer?
    private let dbPath: String

    init() {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let dbDir = appSupport.appendingPathComponent("MLXDash", isDirectory: true)
        try? FileManager.default.createDirectory(at: dbDir, withIntermediateDirectories: true)
        self.dbPath = dbDir.appendingPathComponent("mlxdash.db").path

        openDatabase()
        createTables()
    }

    deinit {
        sqlite3_close(db)
    }

    private func openDatabase() {
        if sqlite3_open(dbPath, &db) != SQLITE_OK {
            print("Error opening database")
        }
    }

    private func createTables() {
        let sessionsSQL = """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                started_at TEXT DEFAULT (datetime('now')),
                ended_at TEXT,
                avg_tokens_per_sec REAL,
                total_tokens INTEGER,
                peak_memory_gb REAL
            );
            """

        let benchmarksSQL = """
            CREATE TABLE IF NOT EXISTS benchmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                ran_at TEXT DEFAULT (datetime('now')),
                avg_tokens_per_sec REAL,
                p50_latency_ms REAL,
                p95_latency_ms REAL,
                peak_memory_gb REAL,
                prompt_count INTEGER
            );
            """

        executeSQL(sessionsSQL)
        executeSQL(benchmarksSQL)
    }

    private func executeSQL(_ sql: String) {
        var statement: OpaquePointer?
        if sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK {
            sqlite3_step(statement)
        }
        sqlite3_finalize(statement)
    }

    // MARK: - Benchmark Operations

    func saveBenchmark(_ result: BenchmarkResult) {
        let sql = """
            INSERT INTO benchmarks (model_name, avg_tokens_per_sec, p50_latency_ms, p95_latency_ms, peak_memory_gb, prompt_count)
            VALUES (?, ?, ?, ?, ?, ?);
            """
        var statement: OpaquePointer?
        if sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK {
            sqlite3_bind_text(statement, 1, result.modelName, -1, nil)
            sqlite3_bind_double(statement, 2, result.avgTokensPerSec)
            sqlite3_bind_double(statement, 3, result.p50LatencyMs)
            sqlite3_bind_double(statement, 4, result.p95LatencyMs)
            sqlite3_bind_double(statement, 5, result.peakMemoryGB)
            sqlite3_bind_int(statement, 6, Int32(result.promptCount))
            sqlite3_step(statement)
        }
        sqlite3_finalize(statement)
    }

    func fetchBenchmarks(forModel model: String? = nil, limit: Int = 30) -> [BenchmarkResult] {
        var results: [BenchmarkResult] = []
        var sql = "SELECT * FROM benchmarks"
        if let model = model {
            sql += " WHERE model_name = '\(model)'"
        }
        sql += " ORDER BY ran_at DESC LIMIT \(limit)"

        var statement: OpaquePointer?
        if sqlite3_prepare_v2(db, sql, -1, &statement, nil) == SQLITE_OK {
            while sqlite3_step(statement) == SQLITE_ROW {
                let result = BenchmarkResult(
                    id: Int(sqlite3_column_int(statement, 0)),
                    modelName: String(cString: sqlite3_column_text(statement, 1)),
                    ranAt: Date(), // Parse from column 2
                    avgTokensPerSec: sqlite3_column_double(statement, 3),
                    p50LatencyMs: sqlite3_column_double(statement, 4),
                    p95LatencyMs: sqlite3_column_double(statement, 5),
                    peakMemoryGB: sqlite3_column_double(statement, 6),
                    promptCount: Int(sqlite3_column_int(statement, 7))
                )
                results.append(result)
            }
        }
        sqlite3_finalize(statement)
        return results
    }
}

// File: MLXDash/Models/BenchmarkResult.swift
struct BenchmarkResult: Identifiable {
    let id: Int
    let modelName: String
    let ranAt: Date
    let avgTokensPerSec: Double
    let p50LatencyMs: Double
    let p95LatencyMs: Double
    let peakMemoryGB: Double
    let promptCount: Int
}
```

**Tasks:**
1. Create `HistoryService` with SQLite3 C API
2. Implement table creation with migrations
3. Add CRUD for benchmarks
4. Add CRUD for sessions
5. Add query methods with date filtering
6. Unit tests with in-memory database

#### 5.2.6 Benchmark Service (Day 6, ~6 hours)

```swift
// File: MLXDash/Services/BenchmarkService.swift
import Foundation
import Observation

@Observable
final class BenchmarkService {
    private(set) var isRunning = false
    private(set) var progress: Double = 0
    private(set) var currentPrompt: Int = 0
    private(set) var results: [PromptResult] = []

    private let ollama: OllamaService
    private let history: HistoryService
    private var benchmarkTask: Task<BenchmarkResult?, Never>?

    // Standard benchmark prompts
    private let prompts = [
        // Short (expect ~10 tokens)
        "What is 2+2?",
        "Name a color.",
        "Say hello.",
        // Medium (expect ~50 tokens)
        "Explain what an API is in simple terms.",
        "List 5 programming languages and their main uses.",
        "What are the benefits of exercise?",
        // Long (expect ~200 tokens)
        "Write a short story about a robot learning to paint.",
        "Explain how machine learning works to a beginner.",
        "Describe the process of photosynthesis in detail.",
        "Compare and contrast cats and dogs as pets."
    ]

    init(ollama: OllamaService, history: HistoryService) {
        self.ollama = ollama
        self.history = history
    }

    func runBenchmark() async -> BenchmarkResult? {
        guard !isRunning else { return nil }
        guard let model = ollama.activeModel else { return nil }

        await MainActor.run {
            isRunning = true
            progress = 0
            currentPrompt = 0
            results = []
        }

        var promptResults: [PromptResult] = []

        for (index, prompt) in prompts.enumerated() {
            await MainActor.run {
                currentPrompt = index + 1
                progress = Double(index) / Double(prompts.count)
            }

            let result = await runSinglePrompt(prompt, model: model.name)
            promptResults.append(result)

            await MainActor.run {
                results.append(result)
            }
        }

        // Calculate aggregate metrics
        let tokensPerSec = promptResults.map(\.tokensPerSec)
        let latencies = promptResults.map(\.latencyMs).sorted()

        let benchmark = BenchmarkResult(
            id: 0,
            modelName: model.name,
            ranAt: Date(),
            avgTokensPerSec: tokensPerSec.reduce(0, +) / Double(tokensPerSec.count),
            p50LatencyMs: latencies[latencies.count / 2],
            p95LatencyMs: latencies[Int(Double(latencies.count) * 0.95)],
            peakMemoryGB: promptResults.map(\.memoryGB).max() ?? 0,
            promptCount: prompts.count
        )

        history.saveBenchmark(benchmark)

        await MainActor.run {
            isRunning = false
            progress = 1.0
        }

        return benchmark
    }

    private func runSinglePrompt(_ prompt: String, model: String) async -> PromptResult {
        let startTime = Date()
        var tokenCount = 0
        var peakMemory: Double = 0

        let url = URL(string: "http://localhost:11434/api/generate")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "model": model,
            "prompt": prompt,
            "stream": true
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        do {
            let (bytes, _) = try await URLSession.shared.bytes(for: request)

            for try await line in bytes.lines {
                if let data = line.data(using: .utf8),
                   let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    if let response = json["response"] as? String {
                        tokenCount += 1  // Approximate: each chunk ~= 1 token
                    }
                    if json["done"] as? Bool == true {
                        break
                    }
                }
            }
        } catch {
            // Handle error
        }

        let duration = Date().timeIntervalSince(startTime)
        return PromptResult(
            prompt: prompt,
            tokenCount: tokenCount,
            latencyMs: duration * 1000,
            tokensPerSec: Double(tokenCount) / duration,
            memoryGB: peakMemory
        )
    }

    func cancel() {
        benchmarkTask?.cancel()
    }
}

struct PromptResult {
    let prompt: String
    let tokenCount: Int
    let latencyMs: Double
    let tokensPerSec: Double
    let memoryGB: Double
}
```

**Tasks:**
1. Define standard benchmark prompts (short/medium/long)
2. Implement streaming request parsing
3. Calculate per-prompt metrics
4. Aggregate into final benchmark result
5. Add progress reporting for UI
6. Implement cancellation
7. Save results to SQLite
8. Test with real Ollama

#### 5.2.7 Benchmark & History Views (Day 7, ~4 hours)

```swift
// File: MLXDash/Views/BenchmarkView.swift
import SwiftUI
import Charts

struct BenchmarkView: View {
    @Environment(OllamaService.self) private var ollama
    @State private var benchmarkService: BenchmarkService?
    @State private var latestResult: BenchmarkResult?
    @State private var historicalResults: [BenchmarkResult] = []

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack {
                Text("Benchmark")
                    .font(.title2)
                    .fontWeight(.bold)
                Spacer()
                if let service = benchmarkService, service.isRunning {
                    Button("Cancel") {
                        service.cancel()
                    }
                } else {
                    Button("Run Benchmark") {
                        Task { await runBenchmark() }
                    }
                    .disabled(ollama.activeModel == nil)
                }
            }

            // Progress
            if let service = benchmarkService, service.isRunning {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Running prompt \(service.currentPrompt) of 10...")
                        .font(.caption)
                    ProgressView(value: service.progress)
                }
            }

            // Latest Result
            if let result = latestResult {
                ResultCard(result: result)
            }

            // Historical Chart
            if !historicalResults.isEmpty {
                Text("History")
                    .font(.headline)

                Chart(historicalResults) { result in
                    BarMark(
                        x: .value("Date", result.ranAt),
                        y: .value("tok/s", result.avgTokensPerSec)
                    )
                    .foregroundStyle(by: .value("Model", result.modelName))
                }
                .frame(height: 150)
            }
        }
        .padding()
        .onAppear {
            loadHistory()
        }
    }

    private func runBenchmark() async {
        // Initialize service if needed
        // Run benchmark
        // Update latestResult
    }

    private func loadHistory() {
        // Load from HistoryService
    }
}

struct ResultCard: View {
    let result: BenchmarkResult

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(result.modelName)
                    .font(.headline)
                Spacer()
                Text(result.ranAt, style: .relative)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            HStack(spacing: 20) {
                MetricBadge(label: "Avg", value: String(format: "%.1f tok/s", result.avgTokensPerSec))
                MetricBadge(label: "P50", value: String(format: "%.0f ms", result.p50LatencyMs))
                MetricBadge(label: "P95", value: String(format: "%.0f ms", result.p95LatencyMs))
            }
        }
        .padding()
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

struct MetricBadge: View {
    let label: String
    let value: String

    var body: some View {
        VStack {
            Text(value)
                .font(.headline)
                .monospacedDigit()
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
    }
}
```

**Tasks:**
1. Build `BenchmarkView` with run button
2. Add progress indicator during benchmark
3. Display result card after completion
4. Add historical chart with Swift Charts
5. Build `HistoryView` with time filters
6. Add export to JSON functionality

#### 5.2.8 Preferences View (Day 8, ~3 hours)

```swift
// File: MLXDash/Views/PreferencesView.swift
import SwiftUI
import ServiceManagement

struct PreferencesView: View {
    @AppStorage("ollamaURL") private var ollamaURL = "http://localhost:11434"
    @AppStorage("pollingInterval") private var pollingInterval = 1.0
    @AppStorage("showTokensInMenuBar") private var showTokensInMenuBar = true
    @AppStorage("benchmarkPromptCount") private var benchmarkPromptCount = 10
    @AppStorage("dataRetentionDays") private var dataRetentionDays = 30

    @State private var launchAtLogin = false

    var body: some View {
        Form {
            Section("Connection") {
                TextField("Ollama URL", text: $ollamaURL)
                    .textFieldStyle(.roundedBorder)

                HStack {
                    Text("Polling Interval")
                    Slider(value: $pollingInterval, in: 0.5...5.0, step: 0.5) {
                        Text("Polling")
                    }
                    Text(String(format: "%.1fs", pollingInterval))
                        .monospacedDigit()
                        .frame(width: 40)
                }
            }

            Section("Display") {
                Toggle("Show tokens/sec in menu bar", isOn: $showTokensInMenuBar)
            }

            Section("Benchmark") {
                Picker("Prompt Count", selection: $benchmarkPromptCount) {
                    Text("5 prompts").tag(5)
                    Text("10 prompts").tag(10)
                    Text("20 prompts").tag(20)
                }
            }

            Section("Data") {
                Picker("Keep history for", selection: $dataRetentionDays) {
                    Text("7 days").tag(7)
                    Text("30 days").tag(30)
                    Text("90 days").tag(90)
                }

                Button("Clear All History") {
                    // Clear SQLite data
                }
                .foregroundStyle(.red)
            }

            Section("System") {
                Toggle("Launch at Login", isOn: $launchAtLogin)
                    .onChange(of: launchAtLogin) { _, newValue in
                        setLaunchAtLogin(newValue)
                    }
            }

            Section {
                HStack {
                    Spacer()
                    Button("Reset to Defaults") {
                        resetDefaults()
                    }
                    Spacer()
                }
            }
        }
        .formStyle(.grouped)
        .frame(width: 400)
        .padding()
        .onAppear {
            launchAtLogin = SMAppService.mainApp.status == .enabled
        }
    }

    private func setLaunchAtLogin(_ enabled: Bool) {
        do {
            if enabled {
                try SMAppService.mainApp.register()
            } else {
                try SMAppService.mainApp.unregister()
            }
        } catch {
            print("Failed to set launch at login: \(error)")
        }
    }

    private func resetDefaults() {
        ollamaURL = "http://localhost:11434"
        pollingInterval = 1.0
        showTokensInMenuBar = true
        benchmarkPromptCount = 10
        dataRetentionDays = 30
    }
}
```

**Tasks:**
1. Create preferences form with sections
2. Implement `@AppStorage` for persistence
3. Add launch at login using `SMAppService`
4. Add Ollama URL configuration
5. Add polling interval slider
6. Add data retention options
7. Add reset to defaults

#### 5.2.9 App Icon & Assets (Day 8, ~2 hours)

**Design Concept:**
- Menu bar icon: Stylized brain/speedometer hybrid
- App icon: Same concept with gradient background
- Colors: Blue-to-purple gradient (Apple Intelligence vibe)

**Tasks:**
1. Create 1024x1024 master icon (AI-generated or designed)
2. Export all required sizes via Xcode
3. Create template image for menu bar (PDF or SVG)
4. Test icon in light/dark menu bar

#### 5.2.10 Testing & Quality (Day 9, ~6 hours)

```swift
// File: MLXDashTests/OllamaServiceTests.swift
import XCTest
@testable import MLXDash

final class OllamaServiceTests: XCTestCase {
    var service: OllamaService!
    var mockSession: URLSession!

    override func setUp() {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        mockSession = URLSession(configuration: config)
        // Inject mock session
    }

    func testFetchActiveModel_Success() async {
        // Given
        let mockResponse = """
        {"models":[{"name":"deepseek-r1:14b","size":9012345678}]}
        """
        MockURLProtocol.mockData = mockResponse.data(using: .utf8)
        MockURLProtocol.mockResponse = HTTPURLResponse(
            url: URL(string: "http://localhost:11434/api/ps")!,
            statusCode: 200,
            httpVersion: nil,
            headerFields: nil
        )

        // When
        await service.fetchActiveModel()

        // Then
        XCTAssertNotNil(service.activeModel)
        XCTAssertEqual(service.activeModel?.name, "deepseek-r1:14b")
    }

    func testFetchActiveModel_OllamaNotRunning() async {
        // Given
        MockURLProtocol.mockError = URLError(.cannotConnectToHost)

        // When
        await service.fetchActiveModel()

        // Then
        XCTAssertFalse(service.isConnected)
        XCTAssertNil(service.activeModel)
    }
}

// Mock URL Protocol for testing
class MockURLProtocol: URLProtocol {
    static var mockData: Data?
    static var mockResponse: URLResponse?
    static var mockError: Error?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        if let error = MockURLProtocol.mockError {
            client?.urlProtocol(self, didFailWithError: error)
        } else {
            if let response = MockURLProtocol.mockResponse {
                client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            }
            if let data = MockURLProtocol.mockData {
                client?.urlProtocol(self, didLoad: data)
            }
        }
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}
```

**Testing Matrix:**

| Test Type | Coverage Target | Tools |
|-----------|-----------------|-------|
| Unit Tests | 80%+ | XCTest, MockURLProtocol |
| UI Tests | Critical paths | XCUITest |
| Integration | Ollama interactions | Live Ollama (CI flag) |
| Performance | Memory leaks | Instruments |

**Tasks:**
1. Write unit tests for OllamaService
2. Write unit tests for SystemMetricsService
3. Write unit tests for HistoryService
4. Add SwiftUI previews for all views
5. Run Instruments for memory profiling
6. Test graceful degradation (no Ollama)
7. Test on macOS 14.0 VM (if available)

#### 5.2.11 Packaging & Distribution (Day 10, ~4 hours)

```bash
# Install create-dmg
brew install create-dmg

# Build Release
xcodebuild -project MLXDash.xcodeproj \
    -scheme MLXDash \
    -configuration Release \
    -archivePath build/MLXDash.xcarchive \
    archive

# Export App
xcodebuild -exportArchive \
    -archivePath build/MLXDash.xcarchive \
    -exportPath build/export \
    -exportOptionsPlist ExportOptions.plist

# Sign (if not done by Xcode)
codesign --deep --force --verify --verbose \
    --sign "Developer ID Application: Your Name (TEAM_ID)" \
    --options runtime \
    build/export/MLXDash.app

# Create DMG
create-dmg \
    --volname "MLXDash" \
    --volicon "build/export/MLXDash.app/Contents/Resources/AppIcon.icns" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "MLXDash.app" 150 190 \
    --hide-extension "MLXDash.app" \
    --app-drop-link 450 185 \
    "build/MLXDash-1.0.0.dmg" \
    "build/export/MLXDash.app"

# Notarize
xcrun notarytool submit build/MLXDash-1.0.0.dmg \
    --apple-id "your@email.com" \
    --password "app-specific-password" \
    --team-id "TEAM_ID" \
    --wait

# Staple
xcrun stapler staple build/MLXDash-1.0.0.dmg
```

**ExportOptions.plist:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>developer-id</string>
    <key>signingStyle</key>
    <string>automatic</string>
    <key>teamID</key>
    <string>YOUR_TEAM_ID</string>
</dict>
</plist>
```

**Tasks:**
1. Configure code signing in Xcode
2. Create ExportOptions.plist
3. Build release archive
4. Create DMG with create-dmg
5. Notarize with Apple
6. Test installation on clean system
7. Create GitHub Release workflow

---

## 6. Phase 2: MLXCache

### 6.1 Architecture Deep Dive

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLI Entry (Typer)                         │
│  mlx-cache [status|add|remove|link|unlink|clean|stats|config|sync] │
└────────────────────────────────────┬────────────────────────────────┘
                                     │
                ┌────────────────────┼────────────────────┐
                │                    │                    │
                ▼                    ▼                    ▼
┌───────────────────────┐ ┌──────────────────┐ ┌────────────────────┐
│     CacheManager      │ │     Registry     │ │   ConfigManager    │
│                       │ │    (SQLite)      │ │     (YAML)         │
│  - add_model()        │ │                  │ │                    │
│  - remove_model()     │ │  - models table  │ │  - load()          │
│  - get_model_path()   │ │  - apps table    │ │  - save()          │
│  - calculate_savings()│ │  - usage table   │ │  - get/set()       │
└───────────┬───────────┘ └────────┬─────────┘ └────────────────────┘
            │                      │
            ▼                      │
┌───────────────────────────────────────────────────────────────────┐
│                          Sources                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│  │   HuggingFace   │  │     Ollama      │  │      Local      │   │
│  │                 │  │                 │  │                 │   │
│  │ hf://org/model  │  │ ollama://m:tag  │  │ file:///path    │   │
│  │                 │  │                 │  │                 │   │
│  │ - download()    │  │ - create_link() │  │ - import()      │   │
│  │ - verify()      │  │ - verify()      │  │ - verify()      │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘   │
└───────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌───────────────────────────────────────────────────────────────────┐
│                    File System (Cache Directory)                   │
│                                                                    │
│  ~/.mlx-cache/                                                     │
│  ├── models/                                                       │
│  │   ├── hf--deepseek-ai--deepseek-r1-14b/                        │
│  │   │   ├── model.safetensors                                    │
│  │   │   ├── config.json                                          │
│  │   │   └── .metadata.json                                       │
│  │   └── ollama--deepseek-r1--14b/ → ~/.ollama/models/... (symlink)│
│  ├── registry.db                                                   │
│  ├── config.yaml                                                   │
│  └── logs/                                                         │
└───────────────────────────────────────────────────────────────────┘
```

### 6.2 Detailed Implementation

#### 6.2.1 Project Structure

```
mlx-cache/
├── pyproject.toml
├── src/
│   └── mlx_cache/
│       ├── __init__.py           # Version, exports
│       ├── cli.py                # Typer CLI definition
│       ├── cache.py              # CacheManager class
│       ├── registry.py           # SQLite registry
│       ├── config.py             # YAML config handling
│       ├── sources/
│       │   ├── __init__.py
│       │   ├── base.py           # Abstract source
│       │   ├── huggingface.py    # HF Hub integration
│       │   ├── ollama.py         # Ollama symlinks
│       │   └── local.py          # Local file import
│       ├── dedup.py              # Deduplication scanner
│       └── utils.py              # Helpers
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Fixtures
│   ├── test_cli.py
│   ├── test_cache.py
│   ├── test_registry.py
│   ├── test_sources/
│   │   ├── test_huggingface.py
│   │   └── test_ollama.py
│   └── test_dedup.py
├── README.md
└── .pre-commit-config.yaml
```

#### 6.2.2 pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

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
keywords = ["mlx", "ollama", "llm", "cache", "apple-silicon"]
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
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-asyncio>=0.24",
    "ruff>=0.8",
    "mypy>=1.13",
]

[project.scripts]
mlx-cache = "mlx_cache.cli:app"

[project.urls]
Homepage = "https://github.com/yourusername/mlx-infrastructure-suite"
Documentation = "https://github.com/yourusername/mlx-infrastructure-suite#readme"
Repository = "https://github.com/yourusername/mlx-infrastructure-suite"

[tool.hatch.build.targets.wheel]
packages = ["src/mlx_cache"]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "C4"]

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

#### 6.2.3 CLI Implementation

```python
# File: src/mlx_cache/cli.py
"""MLX Cache CLI - Unified model cache for Apple Silicon."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .cache import CacheManager
from .config import Config
from .registry import Registry

app = typer.Typer(
    name="mlx-cache",
    help="Unified model cache for MLX and Ollama on Apple Silicon.",
    no_args_is_help=True,
)
console = Console()


def get_cache() -> CacheManager:
    """Get configured cache manager."""
    config = Config.load()
    registry = Registry(config.cache_dir / "registry.db")
    return CacheManager(config, registry)


@app.command()
def status(
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Filter by source"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show all cached models and their usage."""
    cache = get_cache()
    models = cache.list_models(source=source)

    if json_output:
        import json
        console.print(json.dumps([m.to_dict() for m in models], indent=2))
        return

    if not models:
        console.print("[dim]No models cached yet. Use 'mlx-cache add' to add models.[/dim]")
        return

    table = Table(title="MLX Cache Status", show_header=True)
    table.add_column("Model", style="cyan")
    table.add_column("Size", justify="right")
    table.add_column("Source", style="green")
    table.add_column("Used By", style="yellow")
    table.add_column("Symlink", justify="center")

    total_size = 0
    for model in models:
        apps = ", ".join(model.used_by) if model.used_by else "-"
        symlink = "→" if model.is_symlink else ""
        table.add_row(
            model.identifier,
            format_size(model.size_bytes),
            model.source,
            apps,
            symlink,
        )
        total_size += model.size_bytes

    console.print(table)
    console.print(f"\n[bold]Total:[/bold] {format_size(total_size)}")

    # Show savings
    savings = cache.calculate_savings()
    if savings > 0:
        console.print(f"[green]Disk saved by deduplication: {format_size(savings)}[/green]")


@app.command()
def add(
    model_url: str = typer.Argument(..., help="Model URL (hf://org/model, ollama://model:tag)"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite if exists"),
):
    """Download and cache a model."""
    cache = get_cache()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Adding {model_url}...", total=None)

        try:
            result = cache.add_model(model_url, force=force)
            progress.update(task, completed=True)
            console.print(f"[green]✓[/green] Added {result.identifier}")
            console.print(f"  Path: {result.local_path}")
            console.print(f"  Size: {format_size(result.size_bytes)}")
        except Exception as e:
            progress.update(task, completed=True)
            console.print(f"[red]✗[/red] Failed: {e}")
            raise typer.Exit(1)


@app.command()
def remove(
    model_id: str = typer.Argument(..., help="Model identifier to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Remove even if apps are using it"),
):
    """Remove a model from the cache."""
    cache = get_cache()

    # Check if apps are using it
    model = cache.get_model(model_id)
    if not model:
        console.print(f"[red]Model not found: {model_id}[/red]")
        raise typer.Exit(1)

    if model.used_by and not force:
        console.print(f"[yellow]Warning: Model is used by: {', '.join(model.used_by)}[/yellow]")
        console.print("Use --force to remove anyway.")
        raise typer.Exit(1)

    cache.remove_model(model_id)
    console.print(f"[green]✓[/green] Removed {model_id}")


@app.command()
def link(
    app_path: Path = typer.Argument(..., help="Path to the application"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Custom app name"),
):
    """Register an application to use the cache."""
    cache = get_cache()

    if not app_path.exists():
        console.print(f"[red]Path not found: {app_path}[/red]")
        raise typer.Exit(1)

    app_name = name or app_path.stem
    cache.register_app(app_name, app_path)
    console.print(f"[green]✓[/green] Registered {app_name}")


@app.command()
def unlink(
    app_name: str = typer.Argument(..., help="App name to unregister"),
):
    """Unregister an application from the cache."""
    cache = get_cache()
    cache.unregister_app(app_name)
    console.print(f"[green]✓[/green] Unregistered {app_name}")


@app.command()
def clean(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be removed"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Remove unused models from the cache."""
    cache = get_cache()
    orphaned = cache.find_orphaned_models()

    if not orphaned:
        console.print("[green]No unused models found.[/green]")
        return

    total_size = sum(m.size_bytes for m in orphaned)
    console.print(f"Found {len(orphaned)} unused models ({format_size(total_size)}):")

    for model in orphaned:
        console.print(f"  - {model.identifier} ({format_size(model.size_bytes)})")

    if dry_run:
        console.print("\n[dim]Dry run - no changes made.[/dim]")
        return

    if not yes:
        confirm = typer.confirm("Remove these models?")
        if not confirm:
            console.print("Cancelled.")
            return

    for model in orphaned:
        cache.remove_model(model.identifier)

    console.print(f"[green]✓[/green] Freed {format_size(total_size)}")


@app.command()
def stats():
    """Show disk usage and savings statistics."""
    cache = get_cache()
    stats = cache.get_stats()

    console.print("[bold]MLX Cache Statistics[/bold]\n")

    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    table.add_row("Total cache size", format_size(stats.total_size))
    table.add_row("Models cached", str(stats.model_count))
    table.add_row("Apps registered", str(stats.app_count))
    table.add_row("Symlinked models", str(stats.symlink_count))
    table.add_row("", "")
    table.add_row("Disk space saved", f"[green]{format_size(stats.savings)}[/green]")
    table.add_row("Duplicates avoided", str(stats.duplicates_avoided))

    console.print(table)

    if stats.largest_models:
        console.print("\n[bold]Largest Models:[/bold]")
        for model in stats.largest_models[:5]:
            console.print(f"  {model.identifier}: {format_size(model.size_bytes)}")


@app.command()
def sync():
    """Sync with existing Ollama models (create symlinks)."""
    cache = get_cache()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning Ollama models...", total=None)

        synced = cache.sync_ollama()
        progress.update(task, completed=True)

        if synced:
            console.print(f"[green]✓[/green] Synced {len(synced)} Ollama models:")
            for model in synced:
                console.print(f"  - {model}")
        else:
            console.print("[dim]No new Ollama models found.[/dim]")


@app.command()
def config(
    key: Optional[str] = typer.Argument(None, help="Config key to get/set"),
    value: Optional[str] = typer.Argument(None, help="Value to set"),
):
    """View or modify configuration."""
    cfg = Config.load()

    if key is None:
        # Show all config
        console.print("[bold]MLX Cache Configuration[/bold]\n")
        console.print(f"  cache_dir: {cfg.cache_dir}")
        console.print(f"  max_size_gb: {cfg.max_size_gb}")
        console.print(f"  auto_clean: {cfg.auto_clean}")
        console.print(f"  ollama_sync: {cfg.ollama_sync}")
        return

    if value is None:
        # Get single value
        val = getattr(cfg, key, None)
        if val is None:
            console.print(f"[red]Unknown config key: {key}[/red]")
            raise typer.Exit(1)
        console.print(f"{key}: {val}")
    else:
        # Set value
        cfg.set(key, value)
        cfg.save()
        console.print(f"[green]✓[/green] Set {key} = {value}")


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
):
    """MLX Cache - Unified model cache for Apple Silicon."""
    if version:
        from . import __version__
        console.print(f"mlx-cache {__version__}")
        raise typer.Exit()


def format_size(bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(bytes) < 1024:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024
    return f"{bytes:.1f} PB"


if __name__ == "__main__":
    app()
```

#### 6.2.4 Registry Implementation

```python
# File: src/mlx_cache/registry.py
"""SQLite registry for model and app tracking."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ModelRecord:
    id: int
    source: str
    identifier: str
    local_path: Path
    size_bytes: int
    downloaded_at: datetime
    checksum: Optional[str]
    is_symlink: bool
    used_by: list[str]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "identifier": self.identifier,
            "local_path": str(self.local_path),
            "size_bytes": self.size_bytes,
            "downloaded_at": self.downloaded_at.isoformat(),
            "checksum": self.checksum,
            "is_symlink": self.is_symlink,
            "used_by": self.used_by,
        }


@dataclass
class AppRecord:
    id: int
    name: str
    path: Path
    registered_at: datetime


class Registry:
    """SQLite-backed registry for models and apps."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS models (
                    id INTEGER PRIMARY KEY,
                    source TEXT NOT NULL,
                    identifier TEXT NOT NULL UNIQUE,
                    local_path TEXT NOT NULL,
                    size_bytes INTEGER,
                    downloaded_at TEXT DEFAULT (datetime('now')),
                    checksum TEXT,
                    is_symlink INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS apps (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    path TEXT NOT NULL,
                    registered_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS model_usage (
                    model_id INTEGER REFERENCES models(id) ON DELETE CASCADE,
                    app_id INTEGER REFERENCES apps(id) ON DELETE CASCADE,
                    last_used TEXT DEFAULT (datetime('now')),
                    PRIMARY KEY (model_id, app_id)
                );

                CREATE INDEX IF NOT EXISTS idx_models_identifier ON models(identifier);
                CREATE INDEX IF NOT EXISTS idx_apps_name ON apps(name);
            """)

    def add_model(
        self,
        source: str,
        identifier: str,
        local_path: Path,
        size_bytes: int,
        checksum: Optional[str] = None,
        is_symlink: bool = False,
    ) -> int:
        """Add a model to the registry."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO models (source, identifier, local_path, size_bytes, checksum, is_symlink)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(identifier) DO UPDATE SET
                    local_path = excluded.local_path,
                    size_bytes = excluded.size_bytes,
                    checksum = excluded.checksum,
                    is_symlink = excluded.is_symlink
                RETURNING id
                """,
                (source, identifier, str(local_path), size_bytes, checksum, int(is_symlink)),
            )
            return cursor.fetchone()[0]

    def get_model(self, identifier: str) -> Optional[ModelRecord]:
        """Get a model by identifier."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM models WHERE identifier = ?", (identifier,)
            ).fetchone()

            if not row:
                return None

            # Get apps using this model
            apps = conn.execute(
                """
                SELECT a.name FROM apps a
                JOIN model_usage u ON a.id = u.app_id
                WHERE u.model_id = ?
                """,
                (row["id"],),
            ).fetchall()

            return ModelRecord(
                id=row["id"],
                source=row["source"],
                identifier=row["identifier"],
                local_path=Path(row["local_path"]),
                size_bytes=row["size_bytes"],
                downloaded_at=datetime.fromisoformat(row["downloaded_at"]),
                checksum=row["checksum"],
                is_symlink=bool(row["is_symlink"]),
                used_by=[a["name"] for a in apps],
            )

    def list_models(self, source: Optional[str] = None) -> list[ModelRecord]:
        """List all models, optionally filtered by source."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if source:
                rows = conn.execute(
                    "SELECT * FROM models WHERE source = ? ORDER BY identifier",
                    (source,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM models ORDER BY identifier"
                ).fetchall()

            models = []
            for row in rows:
                apps = conn.execute(
                    """
                    SELECT a.name FROM apps a
                    JOIN model_usage u ON a.id = u.app_id
                    WHERE u.model_id = ?
                    """,
                    (row["id"],),
                ).fetchall()

                models.append(ModelRecord(
                    id=row["id"],
                    source=row["source"],
                    identifier=row["identifier"],
                    local_path=Path(row["local_path"]),
                    size_bytes=row["size_bytes"],
                    downloaded_at=datetime.fromisoformat(row["downloaded_at"]),
                    checksum=row["checksum"],
                    is_symlink=bool(row["is_symlink"]),
                    used_by=[a["name"] for a in apps],
                ))

            return models

    def remove_model(self, identifier: str) -> bool:
        """Remove a model from the registry."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM models WHERE identifier = ?", (identifier,)
            )
            return cursor.rowcount > 0

    def register_app(self, name: str, path: Path) -> int:
        """Register an application."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO apps (name, path)
                VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET path = excluded.path
                RETURNING id
                """,
                (name, str(path)),
            )
            return cursor.fetchone()[0]

    def unregister_app(self, name: str) -> bool:
        """Unregister an application."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM apps WHERE name = ?", (name,))
            return cursor.rowcount > 0

    def link_model_to_app(self, model_identifier: str, app_name: str):
        """Link a model to an app."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO model_usage (model_id, app_id)
                SELECT m.id, a.id FROM models m, apps a
                WHERE m.identifier = ? AND a.name = ?
                ON CONFLICT DO UPDATE SET last_used = datetime('now')
                """,
                (model_identifier, app_name),
            )

    def find_orphaned_models(self) -> list[ModelRecord]:
        """Find models not used by any app."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT m.* FROM models m
                LEFT JOIN model_usage u ON m.id = u.model_id
                WHERE u.model_id IS NULL
                """
            ).fetchall()

            return [
                ModelRecord(
                    id=row["id"],
                    source=row["source"],
                    identifier=row["identifier"],
                    local_path=Path(row["local_path"]),
                    size_bytes=row["size_bytes"],
                    downloaded_at=datetime.fromisoformat(row["downloaded_at"]),
                    checksum=row["checksum"],
                    is_symlink=bool(row["is_symlink"]),
                    used_by=[],
                )
                for row in rows
            ]
```

#### 6.2.5 Ollama Source (Symlinks)

```python
# File: src/mlx_cache/sources/ollama.py
"""Ollama integration - creates symlinks to existing Ollama models."""

import json
from pathlib import Path
from typing import Optional

from .base import Source, SourceResult


class OllamaSource(Source):
    """Handle ollama:// URLs by creating symlinks to Ollama's model cache."""

    OLLAMA_HOME = Path.home() / ".ollama" / "models"

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir

    def parse_url(self, url: str) -> tuple[str, Optional[str]]:
        """Parse ollama://model:tag URL."""
        # Remove prefix
        if url.startswith("ollama://"):
            url = url[9:]

        # Split model:tag
        if ":" in url:
            model, tag = url.rsplit(":", 1)
        else:
            model, tag = url, "latest"

        return model, tag

    def resolve(self, url: str) -> Optional[SourceResult]:
        """Resolve an Ollama model URL to a local path."""
        model, tag = self.parse_url(url)
        identifier = f"{model}:{tag}"

        # Find the model manifest
        manifest_path = self._find_manifest(model, tag)
        if not manifest_path:
            return None

        # Read manifest to get blob locations
        with open(manifest_path) as f:
            manifest = json.load(f)

        # Get size from layers
        total_size = sum(layer.get("size", 0) for layer in manifest.get("layers", []))

        # Create symlink in our cache
        link_name = f"ollama--{model.replace('/', '--')}--{tag}"
        link_path = self.cache_dir / "models" / link_name

        # Link to the model's blob directory
        blob_dir = self.OLLAMA_HOME / "blobs"

        return SourceResult(
            source="ollama",
            identifier=identifier,
            local_path=link_path,
            size_bytes=total_size,
            is_symlink=True,
            symlink_target=blob_dir,
        )

    def create_link(self, result: SourceResult) -> bool:
        """Create the actual symlink."""
        if not result.is_symlink or not result.symlink_target:
            return False

        result.local_path.parent.mkdir(parents=True, exist_ok=True)

        if result.local_path.exists() or result.local_path.is_symlink():
            result.local_path.unlink()

        result.local_path.symlink_to(result.symlink_target)
        return True

    def _find_manifest(self, model: str, tag: str) -> Optional[Path]:
        """Find the Ollama manifest file for a model."""
        # Ollama stores manifests in manifests/registry.ollama.ai/library/model/tag
        # or manifests/registry.ollama.ai/org/model/tag for custom registries

        possible_paths = [
            self.OLLAMA_HOME / "manifests" / "registry.ollama.ai" / "library" / model / tag,
            self.OLLAMA_HOME / "manifests" / "registry.ollama.ai" / model / tag,
        ]

        for path in possible_paths:
            if path.exists():
                return path

        return None

    def list_available(self) -> list[str]:
        """List all available Ollama models."""
        models = []
        manifests_dir = self.OLLAMA_HOME / "manifests"

        if not manifests_dir.exists():
            return models

        # Walk the manifests directory
        for registry_dir in manifests_dir.iterdir():
            if not registry_dir.is_dir():
                continue
            for org_dir in registry_dir.iterdir():
                if not org_dir.is_dir():
                    continue
                for model_dir in org_dir.iterdir():
                    if not model_dir.is_dir():
                        continue
                    for tag_file in model_dir.iterdir():
                        if tag_file.is_file():
                            model_name = model_dir.name
                            if org_dir.name != "library":
                                model_name = f"{org_dir.name}/{model_name}"
                            models.append(f"{model_name}:{tag_file.name}")

        return models
```

### 6.3 Testing Strategy

```python
# File: tests/conftest.py
import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_ollama_home(temp_cache_dir):
    """Create a mock Ollama home directory."""
    ollama_home = temp_cache_dir / ".ollama" / "models"
    ollama_home.mkdir(parents=True)

    # Create mock manifest
    manifests = ollama_home / "manifests" / "registry.ollama.ai" / "library" / "test-model" / "latest"
    manifests.parent.mkdir(parents=True)
    manifests.write_text('{"layers": [{"size": 1000000}]}')

    # Create mock blobs
    blobs = ollama_home / "blobs"
    blobs.mkdir()
    (blobs / "sha256-abc123").write_bytes(b"mock model data")

    return ollama_home


@pytest.fixture
def registry(temp_cache_dir):
    """Create a test registry."""
    from mlx_cache.registry import Registry
    return Registry(temp_cache_dir / "registry.db")
```

---

## 7. Phase 3: SwiftMLX

### 7.1 Package Structure

```
swiftmlx/
├── Package.swift
├── Sources/
│   ├── SwiftMLX/
│   │   ├── SwiftMLX.swift            # Public API facade
│   │   ├── Model/
│   │   │   ├── MLXModel.swift        # Model abstraction
│   │   │   ├── ModelLoader.swift     # Loading logic
│   │   │   └── ModelRegistry.swift   # Available models
│   │   ├── Inference/
│   │   │   ├── TextGeneration.swift  # Text completion
│   │   │   ├── Streaming.swift       # AsyncSequence
│   │   │   └── VisionAnalysis.swift  # Image analysis
│   │   ├── Cache/
│   │   │   └── MLXCacheClient.swift  # mlx-cache integration
│   │   └── Internal/
│   │       ├── OllamaClient.swift    # HTTP client
│   │       └── JSONModels.swift      # Codable types
│   └── SwiftMLXUI/
│       ├── ChatView.swift            # Chat interface
│       ├── ModelPicker.swift         # Model selector
│       ├── PerformanceView.swift     # Metrics display
│       ├── PromptField.swift         # Input field
│       └── Components/
│           ├── MessageBubble.swift
│           └── StreamingText.swift
├── Templates/
│   ├── MLX Chat App.xctemplate/
│   │   ├── TemplateInfo.plist
│   │   ├── ___PACKAGENAME___App.swift
│   │   └── ContentView.swift
│   ├── MLX Document Analyzer.xctemplate/
│   └── MLX Image Captioner.xctemplate/
├── Examples/
│   ├── ChatDemo/
│   │   ├── ChatDemo.xcodeproj
│   │   └── ChatDemo/
│   └── VisionDemo/
├── Tests/
│   └── SwiftMLXTests/
├── README.md
└── install-templates.sh
```

### 7.2 Package.swift

```swift
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SwiftMLX",
    platforms: [
        .macOS(.v14)
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
        // Optional: Use ollama-swift for more features
        // .package(url: "https://github.com/mattt/ollama-swift", from: "1.0.0"),
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

### 7.3 Core API Implementation

```swift
// File: Sources/SwiftMLX/SwiftMLX.swift
import Foundation

/// Main entry point for SwiftMLX
public enum SwiftMLX {
    /// Load a model by name
    public static func load(_ modelName: String) async throws -> MLXModel {
        let loader = ModelLoader()
        return try await loader.load(modelName)
    }

    /// List available models
    public static func availableModels() async throws -> [ModelInfo] {
        let loader = ModelLoader()
        return try await loader.listModels()
    }
}

// File: Sources/SwiftMLX/Model/MLXModel.swift
import Foundation

/// Represents a loaded MLX model
public final class MLXModel: Sendable {
    public let name: String
    public let family: String?
    public let parameterSize: String?

    private let client: OllamaClient

    init(name: String, family: String?, parameterSize: String?, client: OllamaClient) {
        self.name = name
        self.family = family
        self.parameterSize = parameterSize
        self.client = client
    }

    /// Generate text from a prompt
    public func generate(
        prompt: String,
        systemPrompt: String? = nil,
        maxTokens: Int = 2048,
        temperature: Double = 0.7
    ) async throws -> String {
        let request = GenerateRequest(
            model: name,
            prompt: prompt,
            system: systemPrompt,
            options: GenerateOptions(
                numPredict: maxTokens,
                temperature: temperature
            ),
            stream: false
        )

        let response = try await client.generate(request)
        return response.response
    }

    /// Stream text generation
    public func stream(
        prompt: String,
        systemPrompt: String? = nil,
        maxTokens: Int = 2048,
        temperature: Double = 0.7
    ) -> AsyncThrowingStream<String, Error> {
        AsyncThrowingStream { continuation in
            Task {
                do {
                    let request = GenerateRequest(
                        model: name,
                        prompt: prompt,
                        system: systemPrompt,
                        options: GenerateOptions(
                            numPredict: maxTokens,
                            temperature: temperature
                        ),
                        stream: true
                    )

                    for try await token in client.streamGenerate(request) {
                        continuation.yield(token)
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }

    /// Analyze an image
    public func analyze(
        image: Data,
        prompt: String = "Describe this image in detail."
    ) async throws -> String {
        let base64Image = image.base64EncodedString()

        let request = GenerateRequest(
            model: name,
            prompt: prompt,
            images: [base64Image],
            stream: false
        )

        let response = try await client.generate(request)
        return response.response
    }
}

// File: Sources/SwiftMLX/Internal/OllamaClient.swift
import Foundation

actor OllamaClient {
    private let baseURL: URL
    private let session: URLSession

    init(baseURL: URL = URL(string: "http://localhost:11434")!) {
        self.baseURL = baseURL
        self.session = URLSession.shared
    }

    func generate(_ request: GenerateRequest) async throws -> GenerateResponse {
        let url = baseURL.appendingPathComponent("api/generate")
        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try JSONEncoder().encode(request)

        let (data, _) = try await session.data(for: urlRequest)
        return try JSONDecoder().decode(GenerateResponse.self, from: data)
    }

    func streamGenerate(_ request: GenerateRequest) -> AsyncThrowingStream<String, Error> {
        AsyncThrowingStream { continuation in
            Task {
                let url = baseURL.appendingPathComponent("api/generate")
                var urlRequest = URLRequest(url: url)
                urlRequest.httpMethod = "POST"
                urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
                urlRequest.httpBody = try JSONEncoder().encode(request)

                do {
                    let (bytes, _) = try await session.bytes(for: urlRequest)

                    for try await line in bytes.lines {
                        if let data = line.data(using: .utf8),
                           let response = try? JSONDecoder().decode(StreamResponse.self, from: data) {
                            if !response.response.isEmpty {
                                continuation.yield(response.response)
                            }
                            if response.done {
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

    func listModels() async throws -> [TagModel] {
        let url = baseURL.appendingPathComponent("api/tags")
        let (data, _) = try await session.data(from: url)
        let response = try JSONDecoder().decode(TagsResponse.self, from: data)
        return response.models
    }
}
```

### 7.4 UI Components

```swift
// File: Sources/SwiftMLXUI/ChatView.swift
import SwiftUI
import SwiftMLX

/// A complete chat interface for MLX models
public struct MLXChatView: View {
    @Binding var messages: [ChatMessage]
    let model: MLXModel

    @State private var inputText = ""
    @State private var isGenerating = false
    @State private var streamingResponse = ""

    public init(messages: Binding<[ChatMessage]>, model: MLXModel) {
        self._messages = messages
        self.model = model
    }

    public var body: some View {
        VStack(spacing: 0) {
            // Messages
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 12) {
                        ForEach(messages) { message in
                            MessageBubble(message: message)
                        }

                        if isGenerating {
                            MessageBubble(message: ChatMessage(
                                role: .assistant,
                                content: streamingResponse
                            ))
                            .id("streaming")
                        }
                    }
                    .padding()
                }
                .onChange(of: messages.count) { _, _ in
                    withAnimation {
                        proxy.scrollTo(messages.last?.id, anchor: .bottom)
                    }
                }
                .onChange(of: streamingResponse) { _, _ in
                    withAnimation {
                        proxy.scrollTo("streaming", anchor: .bottom)
                    }
                }
            }

            Divider()

            // Input
            HStack(spacing: 12) {
                TextField("Message", text: $inputText, axis: .vertical)
                    .textFieldStyle(.plain)
                    .lineLimit(1...5)
                    .onSubmit {
                        Task { await sendMessage() }
                    }
                    .disabled(isGenerating)

                Button {
                    Task { await sendMessage() }
                } label: {
                    Image(systemName: isGenerating ? "stop.fill" : "arrow.up.circle.fill")
                        .font(.title2)
                }
                .buttonStyle(.plain)
                .disabled(inputText.isEmpty && !isGenerating)
            }
            .padding()
        }
    }

    private func sendMessage() async {
        guard !inputText.isEmpty else { return }

        let userMessage = ChatMessage(role: .user, content: inputText)
        messages.append(userMessage)

        let prompt = inputText
        inputText = ""
        isGenerating = true
        streamingResponse = ""

        do {
            for try await token in model.stream(prompt: prompt) {
                streamingResponse += token
            }

            messages.append(ChatMessage(role: .assistant, content: streamingResponse))
        } catch {
            messages.append(ChatMessage(role: .assistant, content: "Error: \(error.localizedDescription)"))
        }

        isGenerating = false
        streamingResponse = ""
    }
}

public struct ChatMessage: Identifiable {
    public let id = UUID()
    public let role: Role
    public let content: String
    public let timestamp = Date()

    public enum Role {
        case user
        case assistant
        case system
    }

    public init(role: Role, content: String) {
        self.role = role
        self.content = content
    }
}

struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack {
            if message.role == .user { Spacer() }

            Text(message.content)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(backgroundColor)
                .foregroundStyle(foregroundColor)
                .clipShape(RoundedRectangle(cornerRadius: 16))

            if message.role == .assistant { Spacer() }
        }
    }

    private var backgroundColor: Color {
        switch message.role {
        case .user: return .blue
        case .assistant: return Color(.systemGray5)
        case .system: return .orange.opacity(0.2)
        }
    }

    private var foregroundColor: Color {
        message.role == .user ? .white : .primary
    }
}
```

### 7.5 Template Installation

```bash
#!/bin/bash
# File: swiftmlx/install-templates.sh

TEMPLATE_DIR=~/Library/Developer/Xcode/Templates/File\ Templates/SwiftMLX
SOURCE_DIR="$(dirname "$0")/Templates"

echo "Installing SwiftMLX Xcode Templates..."

# Create directory
mkdir -p "$TEMPLATE_DIR"

# Copy templates
cp -R "$SOURCE_DIR"/*.xctemplate "$TEMPLATE_DIR/"

echo "Templates installed to: $TEMPLATE_DIR"
echo "Restart Xcode to see templates in New Project wizard."
```

---

## 8. Phase 4: Integration & Release

### 8.1 Cross-Tool Integration Points

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Workflow                               │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       │                       │                       │
       ▼                       ▼                       ▼
┌─────────────┐        ┌─────────────┐        ┌─────────────┐
│  MLXCache   │◄──────►│   MLXDash   │        │  SwiftMLX   │
│             │        │             │        │             │
│ mlx-cache   │        │ Menu Bar    │        │ Swift Apps  │
│ status      │◄───────│ Cache Info  │        │             │
│ --json      │        │             │        │             │
└─────────────┘        └─────────────┘        └─────────────┘
       │                                              │
       │              ┌───────────────┐               │
       └─────────────►│    Ollama     │◄──────────────┘
                      │ localhost:    │
                      │ 11434         │
                      └───────────────┘
```

### 8.2 GitHub Actions CI/CD

```yaml
# File: .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  mlxdash:
    runs-on: macos-14
    steps:
      - uses: actions/checkout@v4

      - name: Setup Xcode
        uses: maxim-lobanov/setup-xcode@v1
        with:
          xcode-version: latest-stable

      - name: Build MLXDash
        run: |
          cd mlxdash
          xcodebuild -project MLXDash.xcodeproj \
            -scheme MLXDash \
            -configuration Release \
            -archivePath build/MLXDash.xcarchive \
            archive

      - name: Create DMG
        run: |
          brew install create-dmg
          # ... DMG creation steps

      - name: Upload Release
        uses: actions/upload-artifact@v4
        with:
          name: MLXDash.dmg
          path: mlxdash/build/MLXDash-*.dmg

  mlxcache:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install Dependencies
        run: |
          cd mlx-cache
          pip install build twine
          pip install -e ".[dev]"

      - name: Run Tests
        run: |
          cd mlx-cache
          pytest --cov=mlx_cache

      - name: Build Package
        run: |
          cd mlx-cache
          python -m build

      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
        run: |
          cd mlx-cache
          twine upload dist/*

  swiftmlx:
    runs-on: macos-14
    steps:
      - uses: actions/checkout@v4

      - name: Build SwiftMLX
        run: |
          cd swiftmlx
          swift build
          swift test
```

### 8.3 Release Checklist

```markdown
## Pre-Release Checklist

### Code Quality
- [ ] All tests passing (MLXDash, MLXCache, SwiftMLX)
- [ ] No compiler warnings
- [ ] Linting passes (ruff for Python, SwiftLint if enabled)
- [ ] Documentation complete

### MLXDash
- [ ] App signed with Developer ID
- [ ] App notarized with Apple
- [ ] DMG stapled
- [ ] Tested on clean macOS 14.0 install
- [ ] Tested with Ollama running
- [ ] Tested with Ollama NOT running (graceful degradation)

### MLXCache
- [ ] pip install mlx-cache works from TestPyPI
- [ ] All CLI commands work
- [ ] Symlinks to Ollama work
- [ ] Stats show accurate savings

### SwiftMLX
- [ ] swift package add works
- [ ] Templates install correctly
- [ ] Example apps build and run

### Documentation
- [ ] README updated with installation instructions
- [ ] Changelog updated
- [ ] Screenshots current
- [ ] Video/GIF demos created

### Distribution
- [ ] GitHub Release created with all assets
- [ ] PyPI package published
- [ ] Blog post drafted
- [ ] Social media posts prepared
```

---

## 9. Quality Assurance Strategy

### 9.1 Testing Matrix

| Component | Unit Tests | Integration | E2E | Performance |
|-----------|------------|-------------|-----|-------------|
| MLXDash Services | XCTest | Live Ollama | Manual | Instruments |
| MLXDash UI | SwiftUI Previews | - | XCUITest | - |
| MLXCache CLI | pytest | temp dirs | subprocess | - |
| MLXCache Sources | pytest + mocks | Live Ollama | - | - |
| SwiftMLX Core | XCTest | Live Ollama | - | - |
| SwiftMLX UI | Previews | - | - | - |

### 9.2 Coverage Targets

- **MLXDash**: 80%+ on Services, 50%+ on Views
- **MLXCache**: 90%+ overall (CLI-focused)
- **SwiftMLX**: 70%+ on Core, UI coverage via previews

### 9.3 Manual Test Scenarios

1. **Fresh Install**: New Mac, no Ollama, no models
2. **Existing Ollama User**: 5+ models already downloaded
3. **Heavy Usage**: Run benchmark while generating
4. **Network Issues**: Ollama stops mid-generation
5. **Memory Pressure**: Large model + low memory

---

## 10. Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Apple changes MenuBarExtra API | Low | High | Abstract UI layer, follow WWDC |
| Ollama changes API | Medium | Medium | Version check, fallback behavior |
| Code signing issues | Medium | High | Test early, document process |
| GPU metrics unavailable | High | Low | Graceful fallback to "N/A" |
| PyPI name taken | Low | Medium | Check early, have backup name |
| Low initial adoption | Medium | Medium | Focus on genuine utility first |

---

## 11. Resources & References

### Official Documentation
- [Apple MenuBarExtra](https://developer.apple.com/documentation/swiftui/menubarextra)
- [Apple Code Signing](https://developer.apple.com/developer-id/)
- [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [MLX Documentation](https://ml-explore.github.io/mlx/)

### Swift/macOS Resources
- [Building Menu Bar Apps](https://sarunw.com/posts/swiftui-menu-bar-app/) - Sarunw
- [MenuBarExtra Settings Workaround](https://steipete.me/posts/2025/showing-settings-from-macos-menu-bar-items) - Peter Steinberger
- [ollama-swift Package](https://github.com/mattt/ollama-swift) - Matt

### Python/CLI Resources
- [Typer Documentation](https://typer.tiangolo.com/)
- [Rich Documentation](https://rich.readthedocs.io/)
- [Modern Python Packaging](https://packaging.python.org/en/latest/)

### MLX Resources
- [MLX WWDC25 Session](https://developer.apple.com/videos/play/wwdc2025/315/)
- [MLX GitHub](https://github.com/ml-explore/mlx)
- [Local LLM Hosting Guide 2025](https://medium.com/@rosgluk/local-llm-hosting-complete-2025-guide-ollama-vllm-localai-jan-lm-studio-more-f98136ce7e4a)

---

## Appendix A: Quick Reference Commands

```bash
# MLXDash Development
cd mlxdash
xcodebuild -scheme MLXDash build
xcodebuild -scheme MLXDash test

# MLXCache Development
cd mlx-cache
pip install -e ".[dev]"
mlx-cache --help
pytest --cov

# SwiftMLX Development
cd swiftmlx
swift build
swift test

# Full Test Suite
./scripts/test-all.sh
```

---

*This document is the authoritative implementation reference for the MLX Infrastructure Suite project.*
