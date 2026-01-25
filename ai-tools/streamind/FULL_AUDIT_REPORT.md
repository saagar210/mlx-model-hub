# StreamMind Full Project Audit Report

**Date:** January 12, 2026
**Audited By:** Claude Opus 4.5
**Project Path:** `/Users/d/claude-code/ai-tools/streamind`

---

## Executive Summary

StreamMind is a **planning-complete but unimplemented** macOS application for real-time screen analysis using local AI vision models. The project has exceptional documentation (115KB+ implementation plan) but zero production code - only empty module stubs exist.

| Metric | Status |
|--------|--------|
| **Implementation Progress** | 5% (scaffolding only) |
| **Documentation Quality** | Excellent |
| **Security Posture** | Medium-Low Risk (no code yet) |
| **Synergy Potential** | Very High (8+ related projects) |
| **Market Timing** | Excellent (FastVLM, local AI trend) |

---

## 1. Current Project State

### File Inventory

```
streamind/
├── README.md              # Quick start guide
├── CLAUDE.md              # AI context
├── pyproject.toml         # Complete package config ✅
├── STRATEGY.md            # High-level vision (13KB)
├── IMPLEMENTATION_PLAN.md # Detailed plan (115KB) ⭐
├── PLAN_REVIEW.md         # Improvement recommendations
├── .taskmaster/           # Task management
│   ├── config.json
│   ├── docs/prd.txt      # Product Requirements (19KB)
│   └── tasks/tasks.json  # 20 tasks defined
├── src/streamind/         # Empty module stubs
│   ├── __init__.py       # Empty
│   ├── capture/          # Screen capture (empty)
│   ├── vision/           # AI analysis (empty)
│   ├── reasoning/        # DeepSeek integration (empty)
│   ├── context/          # History/storage (empty)
│   ├── api/              # HTTP API (empty)
│   └── ui/               # Menu bar app (empty)
└── tests/                 # Empty test directory
```

### What's Built vs Planned

| Component | Planned | Implemented |
|-----------|---------|-------------|
| Project setup | ✅ | ✅ |
| Screen capture | ✅ Detailed | ❌ Empty |
| Vision engine | ✅ Detailed | ❌ Empty |
| Context manager | ✅ Detailed | ❌ Empty |
| Reasoning engine | ✅ Detailed | ❌ Empty |
| CLI | ✅ Detailed | ❌ Empty |
| Menu bar UI | ✅ Detailed | ❌ Empty |
| Privacy controls | ✅ Detailed | ❌ Empty |
| Tests | ✅ Planned | ❌ Empty |

---

## 2. Security Audit Findings

### Summary: 3 High, 5 Medium, 4 Low Priority Issues

All findings are **pre-implementation** - addressing these before coding prevents security debt.

### HIGH Priority

| Issue | Description | Fix |
|-------|-------------|-----|
| **Privacy Blocklist** | No enforcement mechanism for sensitive apps | Implement defense-in-depth with fuzzy matching, HMAC-protected blocklist |
| **SQL Injection Risk** | LIKE queries with user wildcards | Use FTS5 full-text search, sanitize input, add length limits |
| **Ollama Endpoint** | No TLS, accepts arbitrary URLs | Validate localhost-only, warn on remote, require HTTPS for network |

### MEDIUM Priority

| Issue | Description | Fix |
|-------|-------------|-----|
| Image validation | No decompression bomb protection | Add PIL size limits, MAX_PIXELS check |
| Database permissions | No file permission restrictions | Set 0o600 on history.db |
| No rate limiting | Local API exploitable | Add slowapi rate limiter |
| Env var injection | Unvalidated config overrides | Use pydantic validators |
| Timing attacks | Blocklist check not constant-time | Use hmac.compare_digest |

### LOW Priority

| Issue | Description | Fix |
|-------|-------------|-----|
| Pillow version | 10.0 vs 11.1.0 available | Update dependency |
| No audit logging | Can't trace privacy decisions | Add loguru audit trail |
| No secure deletion | Deleted data recoverable | Implement 3-pass overwrite |
| No CSP for captures | XSS if viewed in web context | Strip image metadata |

### Security Recommendations for pyproject.toml

```toml
dependencies = [
    # ... existing ...
    "slowapi>=0.1.9",        # Rate limiting
    "cryptography>=42.0",    # Encryption at rest
    "sqlcipher3>=0.5",       # Optional encrypted SQLite
]
```

---

## 3. Local System Synergies

### Related Projects in claude-code/

| Project | Path | Synergy Type |
|---------|------|--------------|
| **MLX Inference Server** | `ai-tools/mlx-model-hub/inference-server` | Vision service, Ollama integration, prompt caching |
| **Knowledge Activation System** | `personal/knowledge-activation-system` | Screenshot indexing, semantic search, RAG |
| **CrewAI Automation** | `personal/crewai-automation-platform` | Multi-agent orchestration for complex queries |
| **MLX Infrastructure** | `ai-tools/mlx-infrastructure-suite` | MLXDash monitoring, metrics |
| **Dev Memory Suite** | `ai-tools/dev-memory-suite` | Code understanding from screenshots |
| **Silicon Studio Audit** | `ai-tools/silicon-studio-audit` | Fine-tuning vision models |
| **CCFlare** | `ai-tools/ccflare` | Claude API proxy if using fallback |
| **Vibe Templates** | `templates/vibe-templates` | Self-hosted AI patterns |

### Integration Opportunities

#### 1. StreamMind → KAS Integration
```
Screen Capture → OCR/Vision → KAS Ingest → Searchable History
```
- Index every analyzed screenshot in KAS
- Enable "what did I see last week about X?" queries
- Leverage existing Nomic embeddings + pgvector

#### 2. StreamMind → MLX Inference Server
```
StreamMind → MLX Server API → Vision Analysis
```
- Use existing OpenAI-compatible endpoint
- Benefit from prompt caching
- MCP integration for Claude desktop

#### 3. StreamMind → CrewAI
```
Complex Query → CrewAI Crew → Multi-step Research → Answer
```
- "Research this error and find solutions" triggers crew
- Agents can browse documentation, search code
- Returns comprehensive analysis

### Installed Applications

| Application | Use Case |
|-------------|----------|
| **AnythingLLM** | Alternative local LLM frontend |
| **Jan.ai** | Another local model interface |
| **LocalAI** | OpenAI-compatible local server |
| **Ollama** | Vision model runtime |
| **ffmpeg** | Video processing (future: video analysis) |

### Installed Brew Packages for AI

```
aichat, cairo, ffmpeg, ffmpegthumbnailer, localai, ollama, anythingllm
```

---

## 4. Competitive Landscape & Similar Projects

### Commercial Competition

| Product | Approach | StreamMind Advantage |
|---------|----------|----------------------|
| **Rewind.ai** | Cloud + subscription | 100% local, free, private |
| **Limitless Pendant** | Hardware wearable | Software-only, no hardware |
| **Microsoft Recall** | Windows only | macOS native |
| **Notion AI** | Document context | Screen-level context |

### Open Source Alternatives

| Project | Platform | Notes |
|---------|----------|-------|
| **[Windrecorder](https://github.com/yuka-friends/Windrecorder)** | Windows | Most similar - OCR-based history search |
| **screenpipe** | Cross-platform | Screen + audio recording with AI |
| **OpenRecall** | Windows | Windows Recall alternative |

### Cutting Edge Research (2025)

| Model | Source | Relevance |
|-------|--------|-----------|
| **[FastVLM](https://github.com/apple/ml-fastvlm)** | Apple ML | 85x faster TTFT, MLX demo app, optimized for Apple Silicon |
| **Molmo 2** | AI2 | Fully open, video analysis |
| **LLaVA-OneVision** | Academic | Strong OCR, document VQA |
| **Qwen 2.5 VL** | Alibaba | Video input, object localization |

**Key Opportunity:** Apple's FastVLM has an MLX demo app. Consider integrating FastVLM when it stabilizes for significant speed improvements.

---

## 5. Vulnerabilities to Address Before Implementation

### Critical: macOS Tahoe Permissions

**Problem:** Non-bundled Python scripts cannot request Screen Recording permission on macOS 15+.

**Solution:**
1. Build as `.app` bundle with py2app
2. Create Swift helper for capture if needed
3. Add first-run permission guide

### Critical: Privacy by Design

Must implement before first capture:
- Hardcoded sensitive app blocklist
- Emergency pause hotkey (⌘+Shift+P)
- Visual capture indicator
- Encrypted local storage

### Configuration Fixes for pyproject.toml

```diff
dependencies = [
-   "click>=8.1",                      # CLI framework
+   "typer>=0.21",                     # CLI framework (better DX)
+   "loguru>=0.7",                     # Structured logging
+   "tenacity>=9.0",                   # Retry logic
+   "aiosqlite>=0.22",                 # Async SQLite
]
```

---

## 6. What to Cut

### Remove from Plan

| Item | Reason |
|------|--------|
| Click references | Typer is superior, already installed |
| pip instructions | Use uv (10-100x faster) |
| Time estimates | Per user preferences |
| Cloud fallback | Keep 100% local for privacy |

### Simplify Architecture

| Current | Simplified |
|---------|------------|
| 7 separate modules | 4 core modules (capture, vision, storage, ui) |
| Complex context engine | Simple SQLite history with FTS |
| Multi-model routing | Single llama3.2-vision:11b to start |

---

## 7. What to Add

### Essential Additions

| Feature | Priority | Rationale |
|---------|----------|-----------|
| **FastVLM integration** | High | Apple's optimized VLM, MLX native |
| **KAS integration** | High | Searchable screenshot history |
| **Response streaming** | High | Better UX, faster perceived response |
| **OCR fallback** | Medium | rapidocr-onnxruntime for text-heavy screens |
| **Hotkey capture** | Medium | ⌘+Shift+S for instant analysis |
| **Export to Obsidian** | Low | Save analyses as notes |

### Integration APIs

```python
# Planned integration points
class StreamMindIntegrations:
    kas: KASClient           # Knowledge Activation System
    mlx_server: MLXClient    # MLX inference server
    crewai: CrewAIClient     # Complex query orchestration
```

---

## 8. Implementation Roadmap

### Phase 0: Pre-Implementation (Now)

- [ ] Update pyproject.toml (Typer, loguru, tenacity)
- [ ] Apply PLAN_REVIEW.md improvements
- [ ] Set up uv environment
- [ ] Create security configuration template

### Phase 1: Foundation (Week 1)

| Task | Description | Dependencies |
|------|-------------|--------------|
| **Screen Capture** | mss-based capture with hash change detection | None |
| **Vision Engine** | Ollama llama3.2-vision integration | Capture |
| **Basic CLI** | `streamind ask "what's this?"` | Capture, Vision |
| **Tests** | End-to-end pipeline test | All above |

### Phase 2: Intelligence (Week 2)

| Task | Description | Dependencies |
|------|-------------|--------------|
| **Window Detection** | PyObjC active window tracking | Capture |
| **SQLite Storage** | FTS5-enabled history | None |
| **Context Manager** | Recent frame buffer, history search | Storage |
| **Content Type Detection** | Code/terminal/browser prompts | Vision |

### Phase 3: User Experience (Week 3)

| Task | Description | Dependencies |
|------|-------------|--------------|
| **Menu Bar App** | rumps-based status menu | All Phase 1-2 |
| **Settings System** | pydantic-settings config | None |
| **Privacy Controls** | Blocklist, pause, indicators | Capture |
| **Hotkeys** | Global capture/pause shortcuts | Menu Bar |

### Phase 4: Integration (Week 4)

| Task | Description | Dependencies |
|------|-------------|--------------|
| **KAS Integration** | Screenshot indexing | Storage, KAS API |
| **MLX Server** | OpenAI-compatible endpoint | Vision |
| **Response Caching** | Query deduplication | Vision, Storage |
| **FastVLM Evaluation** | Test Apple's optimized VLM | Vision |

### Phase 5: Polish (Week 5)

| Task | Description | Dependencies |
|------|-------------|--------------|
| **Test Coverage** | 80%+ coverage | All |
| **py2app Bundle** | macOS app bundle | Menu Bar |
| **Performance Tuning** | <3s response, <500MB RAM | All |
| **Documentation** | README, user guide | All |

---

## 9. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Response time | <3 seconds | Benchmark suite |
| Memory usage | <500MB | Activity Monitor |
| Error identification | 90% accuracy | Test dataset |
| Privacy compliance | 100% blocklist enforcement | Unit tests |
| Offline capability | 100% | Network disconnected test |

---

## 10. Recommended Next Steps

### Immediate Actions (Today)

1. **Update pyproject.toml** with corrected dependencies
2. **Run `uv venv && uv pip install -e ".[dev]"`** to set up environment
3. **Start Task 2** - Screen Capture module

### This Week

1. Complete Phase 1 (capture → vision → CLI → tests)
2. Get "streamind ask 'what's this?'" working end-to-end
3. Benchmark response time

### This Month

1. Complete Phases 1-4
2. Have working menu bar app
3. Integrate with KAS for searchable history
4. Evaluate FastVLM for speed improvements

---

## Appendix A: Reusable Code from Local Projects

### From inference-server

- `ollama_vision_service.py` - Vision API client
- `response_cache.py` - Query caching pattern
- `config.py` - pydantic-settings pattern

### From KAS

- `cli.py` - Typer + Rich pattern
- `embeddings.py` - Nomic embedding client
- `ingestion/` - Content processing pipeline

### From CrewAI Platform

- `crew_flows.py` - Multi-agent orchestration
- `mlx_integration.py` - MLX-native inference

---

## Appendix B: Web Research Sources

- [Apple FastVLM](https://github.com/apple/ml-fastvlm) - MLX-optimized VLM
- [Windrecorder](https://github.com/yuka-friends/Windrecorder) - Windows alternative
- [Best Open Source VLMs 2025](https://www.koyeb.com/blog/best-multimodal-vision-models-in-2025)
- [Rewind Alternatives](https://alternativeto.net/software/rewind-ai/)

---

**Report Complete**

This audit provides a complete snapshot of StreamMind's current state, security posture, integration opportunities, and a concrete roadmap for implementation. The project is well-planned and ready for development to begin.
