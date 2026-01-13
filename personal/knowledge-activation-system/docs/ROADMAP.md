# Knowledge Ecosystem Roadmap

**Created:** 2026-01-13
**Author:** KAS (Senior Engineer Lead)
**Status:** ACTIVE

---

## Executive Summary

We have successfully built and integrated two core systems:

| System | Status | Key Metrics |
|--------|--------|-------------|
| **Knowledge Activation System (KAS)** | ✅ Operational | 176 docs, 815 chunks, hybrid search |
| **Knowledge Seeder** | ✅ Operational | 295 sources, 83% ingestion rate |

**The foundation is solid. Now we make it useful.**

---

## Current State Assessment

### What We Have
```
┌─────────────────────────────────────────────────────────────────┐
│                      KNOWLEDGE ECOSYSTEM                         │
│                                                                  │
│  ┌──────────────────┐         ┌──────────────────┐              │
│  │ Knowledge Seeder │ ──────▶ │       KAS        │              │
│  │   (Ingestion)    │   API   │  (Storage/Search)│              │
│  │                  │         │                  │              │
│  │ • 295 sources    │         │ • 176 documents  │              │
│  │ • 5 extractors   │         │ • 815 chunks     │              │
│  │ • Quality scoring│         │ • Hybrid search  │              │
│  └──────────────────┘         │ • FSRS review    │              │
│                               │ • Security layer │              │
│                               └────────┬─────────┘              │
│                                        │                        │
│                                        ▼                        │
│                               ┌──────────────────┐              │
│                               │   CONSUMERS      │              │
│                               │   (NOT CONNECTED)│              │
│                               │                  │              │
│                               │ • Web Frontend ? │              │
│                               │ • LocalCrew ?    │              │
│                               │ • Claude Code ?  │              │
│                               │ • Other apps ?   │              │
│                               └──────────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

### What's Missing
1. **No active consumers** - The knowledge exists but nothing is using it
2. **No automation** - Manual sync required for Knowledge Seeder
3. **No monitoring** - We can't see if things break
4. **50 broken sources** - URLs need updating
5. **Review system unused** - 0 items in spaced repetition queue

---

## Roadmap Phases

### Phase 1: ACTIVATE (This Week)
**Goal:** Make the knowledge base immediately useful

#### 1.1 Connect Claude Code to KAS
**Priority:** CRITICAL
**Effort:** 2-4 hours

Create an MCP server that allows Claude Code to query the knowledge base directly during coding sessions.

```
User: "How do I implement RAG with LlamaIndex?"
Claude Code: [Queries KAS] → Returns relevant chunks from knowledge base
Claude Code: "Based on your knowledge base, here's how..."
```

**Implementation:**
- Create `/Users/d/claude-code/personal/knowledge-activation-system/mcp-server/`
- Implement `search` and `ask` tools
- Register in Claude Code MCP config

#### 1.2 Enable Q&A Functionality
**Priority:** HIGH
**Effort:** 1-2 hours

The `/search` endpoint returns chunks, but we need `/ask` to provide synthesized answers.

```bash
# Current (search)
curl "http://localhost:8000/api/v1/search?q=RAG"
# Returns: list of chunks

# Needed (ask)
curl -X POST "http://localhost:8000/api/v1/ask" -d '{"query": "How does RAG work?"}'
# Returns: synthesized answer with citations
```

**Status:** Route exists but may need AI provider configuration (OpenRouter/DeepSeek).

#### 1.3 Automate Knowledge Seeder Sync
**Priority:** HIGH
**Effort:** 1 hour

Set up cron job to sync knowledge weekly:

```bash
# Add to crontab
0 4 * * 0 cd /Users/d/claude-code/projects-2026/knowledge-seeder && ./sync.sh >> /var/log/knowledge-sync.log 2>&1
```

---

### Phase 2: STABILIZE (Next 2 Weeks)
**Goal:** Operational reliability and monitoring

#### 2.1 Fix Broken Sources
**Priority:** MEDIUM
**Effort:** 2-3 hours

Update the 50 skipped sources in Knowledge Seeder YAML files:
- LangGraph → `docs.langchain.com/langgraph/...`
- LlamaIndex → verify current paths
- GitHub links → fix tree/blob paths

#### 2.2 Health Monitoring
**Priority:** MEDIUM
**Effort:** 2 hours

Create simple monitoring script:
```bash
#!/bin/bash
# /usr/local/bin/kas-health-check.sh
HEALTH=$(curl -s http://localhost:8000/api/v1/health)
STATUS=$(echo $HEALTH | jq -r '.status')
if [ "$STATUS" != "healthy" ]; then
    echo "KAS unhealthy: $HEALTH" | mail -s "KAS Alert" you@email.com
fi
```

#### 2.3 Backup Strategy
**Priority:** MEDIUM
**Effort:** 1 hour

- PostgreSQL: `pg_dump` daily to cloud storage
- Obsidian vault: Already git-tracked (hourly commits)
- Knowledge Seeder state.db: Include in backup

#### 2.4 Service Management
**Priority:** MEDIUM
**Effort:** 1 hour

Create systemd services (or launchd on macOS) for:
- KAS API server (auto-restart on failure)
- PostgreSQL container health checks

---

### Phase 3: ENHANCE (Month 1)
**Goal:** Improve search quality and intelligence

#### 3.1 Reranking Pipeline
**Priority:** HIGH
**Effort:** 4-6 hours

Current search returns results but doesn't rerank them optimally. Enable:
- Cross-encoder reranking (mxbai-rerank or similar)
- Score normalization
- Confidence thresholds

#### 3.2 Activate Spaced Repetition
**Priority:** MEDIUM
**Effort:** 2-3 hours

The FSRS review system is built but unused:
- Select high-value content for review queue
- Create daily review workflow
- Integrate with notification system

#### 3.3 Auto-Tagging
**Priority:** LOW
**Effort:** 4-6 hours

Use LLM to automatically generate tags for ingested content:
- Extract key concepts
- Suggest related topics
- Build tag hierarchy

---

### Phase 4: INTEGRATE (Month 2)
**Goal:** Connect to broader ecosystem

#### 4.1 LocalCrew Integration
**Priority:** HIGH
**Effort:** 4-6 hours

Enable LocalCrew agents to use KAS for research:
```python
# In LocalCrew agent
knowledge = await kas_client.search("topic relevant to task")
# Agent uses knowledge for better responses
```

#### 4.2 Web Frontend
**Priority:** MEDIUM
**Effort:** 8-16 hours

The Next.js frontend exists at `/web`. Connect it to:
- Search interface
- Content browser
- Review dashboard
- Ingestion status

#### 4.3 Unified Dashboard
**Priority:** LOW
**Effort:** 8-16 hours

Single dashboard showing:
- KAS status and stats
- Knowledge Seeder sync status
- Recent ingestions
- Search analytics

---

### Phase 5: SCALE (Month 3+)
**Goal:** Handle growth and advanced use cases

#### 5.1 Multi-User Support
- API key per application
- Usage tracking
- Rate limiting per client

#### 5.2 Knowledge Graph
- Entity extraction
- Relationship mapping
- Graph visualization

#### 5.3 Advanced RAG
- Query routing
- Multi-hop reasoning
- Source synthesis

---

## Immediate Action Items

Based on the above analysis, here's what I recommend we do **right now**:

### Priority 1: Claude Code MCP Server (TODAY)
```
Why: Immediate value - use knowledge base while coding
Effort: 2-4 hours
Impact: HIGH - every coding session benefits
```

### Priority 2: Verify Q&A Endpoint (TODAY)
```
Why: Core functionality for knowledge retrieval
Effort: 30 minutes to test, 1-2 hours if fixes needed
Impact: HIGH - enables synthesized answers
```

### Priority 3: Automate Seeder Sync (THIS WEEK)
```
Why: Knowledge gets stale without updates
Effort: 1 hour
Impact: MEDIUM - keeps knowledge current
```

---

## Decision Point

**As the Senior Engineer, I recommend we start with Phase 1.1: Claude Code MCP Server.**

Rationale:
1. **Immediate ROI** - You'll use this in every coding session
2. **Validates the system** - Real usage reveals real issues
3. **Low risk** - If it doesn't work, nothing breaks
4. **Foundation for more** - Once Claude Code can query KAS, we can expand to other consumers

---

## Resource Requirements

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Phase 1 | 4-8 hours | None |
| Phase 2 | 6-10 hours | Phase 1 |
| Phase 3 | 10-16 hours | Phase 2 |
| Phase 4 | 20-40 hours | Phase 3 |
| Phase 5 | 40+ hours | Phase 4 |

---

## Next Steps

Awaiting your direction:

1. **Option A:** Proceed with Phase 1.1 (Claude Code MCP Server) immediately
2. **Option B:** Test Q&A endpoint first to validate AI integration
3. **Option C:** Fix broken sources first to maximize knowledge base
4. **Option D:** Something else you have in mind

What's your call?

---

*Roadmap created by Knowledge Activation System*
*Senior Engineer Lead*
*2026-01-13*
