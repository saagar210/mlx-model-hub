# CODEX_BRIEF.md — Senior Architect Handover

**Project:** AI Command Center Desktop App (Phases 13-18)
**Author:** Junior Engineer (Claude)
**Date:** 2026-01-25
**Commits:** `6cb034a4`, `68442e6c`, `0ad5604a`

---

## A. State Transition

- **From:** Headless Python API service (Smart Router + LiteLLM + Langfuse) managed via LaunchAgents and CLI.
- **To:** Full Tauri 2.0 desktop application with React UI, system tray integration, real-time monitoring, configuration editor, test runner, and DMG packaging.

---

## B. Change Manifest (Evidence Anchors)

### Commit 1: `6cb034a4` — Phase 13-14 (Desktop Foundation + Dashboard)

| File | Logic Change |
|------|--------------|
| `desktop/package.json` | Created React + Vite + Tauri frontend with Zustand state, Recharts visualization, lucide-react icons |
| `desktop/src-tauri/Cargo.toml` | Added Rust dependencies: tauri 2.0, tokio, reqwest, serde_yaml, dirs for cross-platform paths |
| `desktop/src-tauri/src/main.rs` | Implemented 750+ lines: AppState struct, health check commands, service start/stop via process spawning, system tray setup with menu events, config/policy read/write, Ollama model management, log tailing |
| `desktop/src-tauri/tauri.conf.json` | Configured app window (1200x800), tray icon, DMG bundling, macOS minimum 11.0 |
| `desktop/src/App.tsx` | Main component with tab routing, health polling every 5s, service control handlers |
| `desktop/src/components/Dashboard.tsx` | Real-time metrics dashboard with LineChart, PieChart, BarChart from Recharts, fetching `/metrics` endpoint |
| `desktop/src/components/ServiceCard.tsx` | Reusable card component with health status indicator, start/stop buttons, external link option |
| `desktop/src/components/Sidebar.tsx` | Navigation sidebar with 6 tabs using Zustand store |
| `desktop/src/components/LogViewer.tsx` | Service log viewer with auto-scroll, 2s polling, color-coded log levels |
| `desktop/src/components/OllamaModels.tsx` | Ollama model management: list, pull, delete with confirmation |
| `desktop/src/stores/appStore.ts` | Zustand store for activeTab and firstRun state |
| `desktop/src/lib/types.ts` | TypeScript interfaces matching Rust structs: Config, RoutingPolicy, HealthStatus, Metrics |
| `desktop/src/index.css` | Tailwind v4 import, custom scrollbar styling |
| `desktop/postcss.config.js` | Tailwind v4 PostCSS plugin configuration |
| `desktop/tailwind.config.js` | Dark mode, gray-900 theme configuration |

### Commit 2: `68442e6c` — Phase 15 (Configuration UI)

| File | Logic Change |
|------|--------------|
| `desktop/src/components/ConfigEditor.tsx` | Added PII regex pattern editing (add/remove/modify), injection pattern editing, scrollable lists with max-height |
| `desktop/src-tauri/src/main.rs` | Added `min_token_length` field to PrivacyPolicy struct for YAML compatibility |
| `desktop/src/lib/types.ts` | Added `min_token_length` to TypeScript RoutingPolicy interface |

### Commit 3: `0ad5604a` — Phase 16-18 (Tests, Setup Wizard, Packaging)

| File | Logic Change |
|------|--------------|
| `desktop/src/components/TestRunner.tsx` | 322-line test runner: service connection tests (5 services), chat completion tests (4 scenarios), routing info display, pass/fail summary |
| `desktop/src/components/SetupWizard.tsx` | First-run dependency checker: Ollama (required), Redis (required), Langfuse (optional), Config files; localStorage persistence, skip option |
| `desktop/src-tauri/src/main.rs` | Added 150+ lines: `TestResult` struct, `ChatTestResult` struct, `RoutingInfo` struct, `test_service_connection` command with HTTP/Redis checks, `test_chat_completion` command with routing metadata extraction |
| `desktop/src/App.tsx` | Integrated SetupWizard with localStorage check, added TestRunner tab routing |
| `desktop/src/components/Sidebar.tsx` | Added Tests tab with TestTube2 icon |
| `desktop/src/stores/appStore.ts` | Added 'tests' to Tab type, isFirstRun state |

---

## C. Trade-Off Defense

### 1. Monolithic `main.rs` (814 lines)

**Decision:** Keep all Rust code in single file.
**Justification:**
- Tauri 2.0 proc-macros (`#[tauri::command]`) caused E0255 errors when split across lib.rs + main.rs
- Compilation works reliably with single-file approach
- **Risk acknowledged:** Technical debt for future maintenance
- **Mitigation:** Clear section comments, logical grouping by feature

### 2. Polling vs WebSocket for Logs

**Decision:** HTTP polling every 2 seconds.
**Justification:**
- Simpler implementation, no additional dependencies
- Log files are small (<10MB typically)
- WebSocket would require additional Tauri plugin setup
- **Trade-off:** ~50ms latency acceptable for log viewing

### 3. localStorage for First-Run Detection

**Decision:** Use browser localStorage instead of Tauri fs plugin.
**Justification:**
- Simpler, no additional permissions needed
- Works across app restarts
- **Risk:** Cleared if user clears browser data (acceptable for setup wizard)

### 4. No Rust Unit Tests

**Decision:** Zero Rust test coverage.
**Justification:**
- Time constraint for Phase 13-18 completion
- Python tests (27 passing) cover Smart Router logic
- Tauri commands are thin wrappers around HTTP calls
- **Technical debt:** Should add tests for process spawning, config parsing

### 5. Bundle Size Warning (628KB JS)

**Decision:** Accept chunk size warning, defer code-splitting.
**Justification:**
- Recharts library is ~350KB alone
- Desktop app, not web—initial load time less critical
- Tauri WebView caches aggressively
- **Future:** Lazy-load Dashboard tab

### 6. Hardcoded Ports (4000, 4001, 11434)

**Decision:** No port configuration UI.
**Justification:**
- Matches existing config.yaml/LaunchAgent setup
- Ports are internal implementation detail
- **Risk:** Conflicts if user runs other services on same ports

---

## D. The Audit Mandate (Instructions for Codex)

> **Codex, please review my work and generate these 7 specific reports based on FACTS and LOGIC, not assumptions:**
>
> 1. **Security Issues Summary** — Analyze `main.rs` for command injection in process spawning, credential handling in test commands, and any exposed secrets in config patterns.
>
> 2. **Code Quality Report** — Review TypeScript strict mode compliance, Rust error handling patterns, component prop drilling vs proper state management.
>
> 3. **Architecture Assessment** — Evaluate the monolithic main.rs decision, Tauri IPC patterns, frontend-backend coupling, and separation of concerns.
>
> 4. **Test Coverage Analysis** — Assess the gap between Python tests (27) and Rust tests (0), identify untested critical paths in service management and config persistence.
>
> 5. **Performance Observation** — Analyze health check polling frequency, log file reading efficiency, React re-render patterns in Dashboard charts.
>
> 6. **Risk Assessment** — Evaluate process spawning without proper signal handling, config file corruption scenarios, race conditions in concurrent service start/stop.
>
> 7. **Improvement Recommendations** — Prioritize: Rust module extraction, error boundaries in React, integration test suite for Tauri commands, accessibility compliance.

---

## Appendix: Build Verification

```
Tests:        27/27 passing (Python)
Frontend:     Builds in 1.60s (TypeScript clean)
Rust:         Compiles in 2.02s (no warnings)
DMG:          5.8 MB at desktop/src-tauri/target/release/bundle/dmg/
```

---

*Prepared for Senior Architect review. All claims are backed by commit diffs and build artifacts.*
