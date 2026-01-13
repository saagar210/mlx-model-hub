# Master Roadmap: KAS-Centric Ecosystem

**Created:** 2026-01-13
**Author:** Senior Engineer Lead
**Status:** ACTIVE - Primary Development Plan

---

## Strategic Vision

**KAS (Knowledge Activation System) is the foundation.** Every other project we build will either:
1. **Feed knowledge INTO KAS** (ingestion)
2. **Pull knowledge FROM KAS** (consumption)
3. **Enhance KAS capabilities** (extensions)

```
                         ┌─────────────────────┐
                         │                     │
       INGESTION         │   KNOWLEDGE         │         CONSUMPTION
                         │   ACTIVATION        │
  ┌──────────────┐       │   SYSTEM            │       ┌──────────────┐
  │ Knowledge    │──────▶│                     │◀──────│ Claude Code  │
  │ Seeder       │       │   176 docs          │       │ MCP Server   │
  └──────────────┘       │   815 chunks        │       └──────────────┘
                         │   Hybrid Search     │
  ┌──────────────┐       │   Q&A               │       ┌──────────────┐
  │ Screen       │──────▶│   Spaced Rep        │◀──────│ Voice        │
  │ Capture      │       │                     │       │ Interface    │
  └──────────────┘       └─────────────────────┘       └──────────────┘
                                   │
  ┌──────────────┐                 │                   ┌──────────────┐
  │ Browser      │─────────────────┼───────────────────│ Agent        │
  │ Research     │                 │                   │ Platform     │
  └──────────────┘                 │                   └──────────────┘
                                   ▼
                         ┌─────────────────────┐
                         │   EVALUATION        │
                         │   RAG Quality       │
                         │   Search Relevance  │
                         └─────────────────────┘
```

---

## Existing Projects Assessment

### To Be Scrapped (Ideas May Be Reused)
| Project | Location | Valuable Ideas |
|---------|----------|----------------|
| knowledge-engine (old) | `/personal/knowledge-engine/` | Replaced by KAS |
| knowledge-engine (2026) | `/projects-2026/knowledge-engine/` | Merged into KAS |
| agent-platform | `/projects-2026/agent-platform/` | Multi-agent orchestration |
| browser-automation | `/projects-2026/browser-automation/` | Playwright automation |
| rag-evaluation | `/projects-2026/rag-evaluation/` | RAGAS/DeepEval metrics |
| screen-analysis | `/projects-2026/screen-analysis/` | Real-time vision |
| voice-assistant | `/projects-2026/voice-assistant/` | Voice UI for AI |
| mcp-servers | `/projects-2026/mcp-servers/` | MCP patterns |
| dev-memory-suite | `/ai-tools/dev-memory-suite/` | Knowledge graph ideas |
| streamind | `/ai-tools/streamind/` | Screen capture + AI |
| mlx-infrastructure-suite | `/ai-tools/mlx-infrastructure-suite/` | MLX tooling |
| mlx-model-hub | `/ai-tools/mlx-model-hub/` | Model management UI |
| silicon-studio-audit | `/ai-tools/silicon-studio-audit/` | Fine-tuning UI |
| ccflare | `/ai-tools/ccflare/` | API load balancing |

### To Be Kept
| Project | Location | Role |
|---------|----------|------|
| **Knowledge Activation System** | `/personal/knowledge-activation-system/` | **CENTRAL HUB** |
| **Knowledge Seeder** | `/projects-2026/knowledge-seeder/` | Ingestion pipeline |

---

## The 10 Priorities

### Priority 1: Claude Code MCP Server
**Goal:** Query KAS directly from any Claude Code session

**Why First:**
- Immediate daily value
- Validates the entire KAS architecture
- Low risk, high reward

**Deliverable:**
```
/Users/d/claude-code/personal/knowledge-activation-system/mcp-server/
├── src/
│   ├── index.ts
│   ├── tools/
│   │   ├── search.ts      # Search knowledge base
│   │   ├── ask.ts         # Q&A with synthesis
│   │   └── ingest.ts      # Quick capture
│   └── kas-client.ts      # KAS API client
├── package.json
└── README.md
```

**Usage After Completion:**
```
You: "How do I implement streaming in FastAPI?"
Claude: [Queries your KAS] → Returns curated knowledge
```

**Effort:** 2-4 hours
**Dependencies:** KAS running

---

### Priority 2: Q&A Endpoint Validation
**Goal:** Ensure synthesized answers work with AI providers

**Why Second:**
- Core functionality for MCP server
- Validates AI integration layer
- Required for Priority 1 to be useful

**Tasks:**
1. Test `/api/v1/ask` endpoint
2. Configure OpenRouter or DeepSeek API key
3. Verify answer synthesis quality
4. Add confidence scoring to responses

**Effort:** 1-2 hours
**Dependencies:** API key for AI provider

---

### Priority 3: Automated Knowledge Sync
**Goal:** Knowledge stays fresh without manual intervention

**Why Third:**
- Prevents knowledge rot
- "Set and forget" operation
- Knowledge Seeder already built

**Deliverable:**
```bash
# Weekly sync cron (Sunday 4am)
0 4 * * 0 /Users/d/claude-code/projects-2026/knowledge-seeder/sync.sh

# sync.sh contents:
#!/bin/bash
cd /Users/d/claude-code/projects-2026/knowledge-seeder
source .venv/bin/activate
knowledge-seeder sync sources/*.yaml --update-only >> /var/log/knowledge-sync.log 2>&1
```

**Effort:** 1 hour
**Dependencies:** Knowledge Seeder working

---

### Priority 4: Fix Broken Sources
**Goal:** Maximize knowledge coverage (50 sources currently broken)

**Why Fourth:**
- Low effort, tangible improvement
- Increases knowledge base by ~17%
- Can be done incrementally

**Tasks:**
1. Update LangGraph URLs → `docs.langchain.com`
2. Update LlamaIndex URLs → current paths
3. Find alternatives for OpenAI blocked docs
4. Fix GitHub tree/blob paths

**Effort:** 2-3 hours
**Dependencies:** None

---

### Priority 5: Service Management & Monitoring
**Goal:** KAS runs reliably without babysitting

**Why Fifth:**
- Foundation for everything else
- Catches problems before they cascade
- Professional-grade infrastructure

**Deliverables:**
1. **launchd service** (macOS) for KAS API
2. **Health check script** with alerting
3. **Log rotation** for API logs
4. **Backup script** for PostgreSQL

```bash
# /usr/local/bin/kas-health-check.sh
#!/bin/bash
HEALTH=$(curl -sf http://localhost:8000/api/v1/health)
if [ $? -ne 0 ]; then
    osascript -e 'display notification "KAS is down!" with title "KAS Alert"'
fi
```

**Effort:** 2-3 hours
**Dependencies:** KAS running

---

### Priority 6: RAG Evaluation Framework
**Goal:** Measure and improve search quality objectively

**Why Sixth:**
- Can't improve what you can't measure
- Validates knowledge base quality
- Identifies weak areas

**Approach:**
- Use RAGAS metrics (context precision, answer relevancy)
- Create test query set (~50 queries with expected results)
- Run weekly evaluation
- Track metrics over time

**Deliverable:**
```
/Users/d/claude-code/personal/knowledge-activation-system/evaluation/
├── test_queries.yaml      # 50 test queries with ground truth
├── evaluate.py            # RAGAS evaluation script
├── metrics/               # Historical metrics
└── reports/               # Generated reports
```

**Effort:** 4-6 hours
**Dependencies:** KAS with data

---

### Priority 7: Web Dashboard
**Goal:** Visual interface for KAS

**Why Seventh:**
- Better UX than CLI for browsing
- Shows system health at a glance
- Foundation for non-technical users

**Approach:**
- Leverage existing `/web` Next.js app
- Connect to KAS API
- Pages: Search, Browse, Stats, Health

**Deliverable:**
```
/Users/d/claude-code/personal/knowledge-activation-system/web/
├── app/
│   ├── page.tsx           # Dashboard home
│   ├── search/            # Search interface
│   ├── browse/            # Content browser
│   ├── stats/             # Statistics
│   └── health/            # System health
└── lib/
    └── kas-client.ts      # API client
```

**Effort:** 8-12 hours
**Dependencies:** Priorities 1-5 complete

---

### Priority 8: Spaced Repetition Activation
**Goal:** Active engagement with knowledge (not just storage)

**Why Eighth:**
- Transforms passive storage into active learning
- FSRS system already built, just unused
- Daily review habit = knowledge retention

**Tasks:**
1. Select high-value content for review queue
2. Create daily review CLI command
3. Integrate with notification system
4. Track retention metrics

**Deliverable:**
```bash
# Morning routine
kas review        # Get today's review items
kas review done   # Mark items reviewed
kas review stats  # See retention metrics
```

**Effort:** 3-4 hours
**Dependencies:** Content in KAS

---

### Priority 9: Screen Capture Integration
**Goal:** Capture knowledge from screen activity

**Why Ninth:**
- Captures implicit knowledge (what you're reading)
- Bridges StreamMind ideas into KAS
- Passive knowledge accumulation

**Approach:**
- Periodic screenshot → OCR → Extract key info
- Smart filtering (skip Netflix, capture docs)
- Queue interesting content for review

**Deliverable:**
```
/Users/d/claude-code/personal/knowledge-activation-system/capture/
├── screenshot.py          # Periodic capture
├── ocr.py                 # Text extraction
├── classifier.py          # Is this worth capturing?
├── queue.py               # Add to review queue
└── daemon.py              # Background service
```

**Effort:** 8-12 hours
**Dependencies:** Vision model (llama3.2-vision)

---

### Priority 10: Voice Interface
**Goal:** Hands-free interaction with KAS

**Why Tenth:**
- Natural interaction mode
- Accessibility
- Builds on voice-assistant ideas

**Approach:**
- Whisper for speech-to-text
- KAS Q&A for answers
- TTS for response

**Deliverable:**
```bash
# Voice command
kas listen        # Start listening
"What did I learn about FastAPI?"
# KAS searches, synthesizes, speaks answer
```

**Effort:** 12-20 hours
**Dependencies:** Priorities 1-8 complete

---

## Summary Table

| Priority | Name | Effort | Dependencies | Impact |
|----------|------|--------|--------------|--------|
| **1** | Claude Code MCP Server | 2-4 hrs | KAS running | Every coding session |
| **2** | Q&A Endpoint Validation | 1-2 hrs | AI API key | Enables synthesis |
| **3** | Automated Sync | 1 hr | Knowledge Seeder | Fresh knowledge |
| **4** | Fix Broken Sources | 2-3 hrs | None | +17% coverage |
| **5** | Service Management | 2-3 hrs | KAS running | Reliability |
| **6** | RAG Evaluation | 4-6 hrs | KAS with data | Quality metrics |
| **7** | Web Dashboard | 8-12 hrs | P1-5 | Visual interface |
| **8** | Spaced Repetition | 3-4 hrs | Content in KAS | Active learning |
| **9** | Screen Capture | 8-12 hrs | Vision model | Passive capture |
| **10** | Voice Interface | 12-20 hrs | P1-8 | Hands-free |

**Total Estimated Effort:** 45-70 hours

---

## Execution Plan

### Week 1: Foundation (Priorities 1-4)
- Day 1: MCP Server + Q&A validation
- Day 2: Automated sync + Fix broken sources

### Week 2: Stability (Priority 5-6)
- Day 1: Service management + monitoring
- Day 2-3: RAG evaluation framework

### Week 3-4: Experience (Priorities 7-8)
- Web dashboard
- Spaced repetition activation

### Month 2: Advanced (Priorities 9-10)
- Screen capture integration
- Voice interface

---

## Decision Point

**Ready to execute Priority 1 (Claude Code MCP Server)?**

This will give you immediate value and validate the entire system. We can iterate from there.

---

*Master Roadmap created by KAS Senior Engineer Lead*
*2026-01-13*
