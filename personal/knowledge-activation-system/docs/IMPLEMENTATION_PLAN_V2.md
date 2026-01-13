# KAS Implementation Plan v2.0

**Created:** 2026-01-13
**Author:** Senior Engineer / Product Manager
**Version:** 2.0
**Status:** APPROVED FOR EXECUTION

---

## Executive Summary

This document contains the complete implementation plan for KAS Priorities 1-8. Each priority is broken down into:
- Objective and success criteria
- Technical specifications
- Step-by-step implementation
- Testing and validation
- Acceptance criteria

**Total Scope:** 8 Priorities, ~35-45 hours of work
**Timeline:** 3-4 weeks

---

## Current State

```
┌─────────────────────────────────────────────────────────────┐
│                    KAS - OPERATIONAL                         │
├─────────────────────────────────────────────────────────────┤
│ API:        http://localhost:8000 (running)                 │
│ Database:   PostgreSQL on port 5433 (healthy)               │
│ Embeddings: Ollama nomic-embed-text (available)             │
│ Content:    176 documents, 815 chunks                       │
│ Search:     Hybrid BM25 + Vector (working)                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│               KNOWLEDGE SEEDER - OPERATIONAL                 │
├─────────────────────────────────────────────────────────────┤
│ Location:   /Users/d/claude-code/projects-2026/knowledge-seeder │
│ Sources:    295 configured, 245 ingested, 50 skipped        │
│ Client:     kas_client.py (working)                         │
└─────────────────────────────────────────────────────────────┘
```

---

# PRIORITY 1: Claude Code MCP Server

## 1.1 Objective

Create an MCP (Model Context Protocol) server that allows Claude Code to query the KAS knowledge base directly during coding sessions.

## 1.2 Success Criteria

- [ ] MCP server starts without errors
- [ ] `search` tool returns relevant results from KAS
- [ ] `ask` tool returns synthesized answers
- [ ] Server registered in Claude Code MCP config
- [ ] End-to-end test: query from Claude Code → KAS response

## 1.3 Technical Specification

### Architecture
```
┌──────────────┐     stdio      ┌──────────────┐     HTTP      ┌──────────────┐
│ Claude Code  │◄──────────────►│  MCP Server  │◄─────────────►│   KAS API    │
│              │                │  (Node.js)   │               │ :8000        │
└──────────────┘                └──────────────┘               └──────────────┘
```

### MCP Tools to Implement

| Tool | Description | Parameters |
|------|-------------|------------|
| `kas_search` | Search knowledge base | `query: string`, `limit?: number` |
| `kas_ask` | Ask question, get synthesized answer | `question: string` |
| `kas_stats` | Get knowledge base statistics | none |

### Directory Structure
```
/Users/d/claude-code/personal/knowledge-activation-system/mcp-server/
├── package.json
├── tsconfig.json
├── src/
│   ├── index.ts              # MCP server entry point
│   ├── kas-client.ts         # KAS API client
│   └── tools/
│       ├── search.ts         # kas_search tool
│       ├── ask.ts            # kas_ask tool
│       └── stats.ts          # kas_stats tool
└── README.md
```

## 1.4 Step-by-Step Implementation

### Step 1.4.1: Initialize Project (10 min)
```bash
cd /Users/d/claude-code/personal/knowledge-activation-system
mkdir -p mcp-server/src/tools
cd mcp-server

# Create package.json
cat > package.json << 'EOF'
{
  "name": "kas-mcp-server",
  "version": "1.0.0",
  "description": "MCP server for Knowledge Activation System",
  "type": "module",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js",
    "dev": "tsx src/index.ts"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^0.5.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "tsx": "^4.0.0",
    "typescript": "^5.0.0"
  }
}
EOF

# Create tsconfig.json
cat > tsconfig.json << 'EOF'
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "declaration": true
  },
  "include": ["src/**/*"]
}
EOF

npm install
```

### Step 1.4.2: Create KAS Client (20 min)
```typescript
// src/kas-client.ts
const KAS_BASE_URL = process.env.KAS_URL || 'http://localhost:8000';

export interface SearchResult {
  content_id: string;
  title: string;
  content_type: string;
  score: number;
  chunk_text: string | null;
}

export interface SearchResponse {
  results: SearchResult[];
  query: string;
  total: number;
}

export interface AskResponse {
  answer: string;
  confidence: string;
  citations: Array<{
    content_id: string;
    title: string;
    chunk_text: string;
  }>;
}

export interface StatsResponse {
  total_content: number;
  total_chunks: number;
  content_by_type: Record<string, number>;
}

export async function kasSearch(query: string, limit: number = 10): Promise<SearchResponse> {
  const url = `${KAS_BASE_URL}/api/v1/search?q=${encodeURIComponent(query)}&limit=${limit}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`KAS search failed: ${response.statusText}`);
  }
  return response.json();
}

export async function kasAsk(question: string): Promise<AskResponse> {
  const url = `${KAS_BASE_URL}/api/v1/ask`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: question }),
  });
  if (!response.ok) {
    throw new Error(`KAS ask failed: ${response.statusText}`);
  }
  return response.json();
}

export async function kasStats(): Promise<StatsResponse> {
  const url = `${KAS_BASE_URL}/api/v1/stats`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`KAS stats failed: ${response.statusText}`);
  }
  return response.json();
}

export async function kasHealth(): Promise<boolean> {
  try {
    const url = `${KAS_BASE_URL}/api/v1/health`;
    const response = await fetch(url);
    const data = await response.json();
    return data.status === 'healthy';
  } catch {
    return false;
  }
}
```

### Step 1.4.3: Create MCP Server (30 min)
```typescript
// src/index.ts
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { kasSearch, kasAsk, kasStats, kasHealth } from './kas-client.js';

const server = new Server(
  {
    name: 'kas-mcp-server',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'kas_search',
        description: 'Search your personal knowledge base for relevant information. Returns chunks of text from your curated documentation, research papers, and notes.',
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: 'Search query (e.g., "FastAPI dependency injection", "RAG evaluation metrics")',
            },
            limit: {
              type: 'number',
              description: 'Maximum results to return (default: 10)',
              default: 10,
            },
          },
          required: ['query'],
        },
      },
      {
        name: 'kas_ask',
        description: 'Ask a question and get a synthesized answer from your knowledge base. Uses AI to combine relevant information into a coherent response with citations.',
        inputSchema: {
          type: 'object',
          properties: {
            question: {
              type: 'string',
              description: 'Question to answer (e.g., "How do I implement streaming in FastAPI?")',
            },
          },
          required: ['question'],
        },
      },
      {
        name: 'kas_stats',
        description: 'Get statistics about your knowledge base: total documents, chunks, and content breakdown by type.',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
    ],
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'kas_search': {
        const query = args?.query as string;
        const limit = (args?.limit as number) || 10;

        if (!query) {
          return { content: [{ type: 'text', text: 'Error: query is required' }] };
        }

        const results = await kasSearch(query, limit);

        if (results.total === 0) {
          return {
            content: [{
              type: 'text',
              text: `No results found for "${query}" in knowledge base.`,
            }],
          };
        }

        const formatted = results.results.map((r, i) =>
          `${i + 1}. **${r.title}** (score: ${r.score.toFixed(3)})\n   ${r.chunk_text?.substring(0, 200)}...`
        ).join('\n\n');

        return {
          content: [{
            type: 'text',
            text: `Found ${results.total} results for "${query}":\n\n${formatted}`,
          }],
        };
      }

      case 'kas_ask': {
        const question = args?.question as string;

        if (!question) {
          return { content: [{ type: 'text', text: 'Error: question is required' }] };
        }

        const response = await kasAsk(question);

        let text = `**Answer** (confidence: ${response.confidence}):\n\n${response.answer}`;

        if (response.citations && response.citations.length > 0) {
          text += '\n\n**Sources:**\n';
          response.citations.forEach((c, i) => {
            text += `${i + 1}. ${c.title}\n`;
          });
        }

        return { content: [{ type: 'text', text }] };
      }

      case 'kas_stats': {
        const stats = await kasStats();

        const typeBreakdown = Object.entries(stats.content_by_type)
          .map(([type, count]) => `  - ${type}: ${count}`)
          .join('\n');

        return {
          content: [{
            type: 'text',
            text: `**Knowledge Base Statistics:**\n\n- Total Documents: ${stats.total_content}\n- Total Chunks: ${stats.total_chunks}\n- Content by Type:\n${typeBreakdown}`,
          }],
        };
      }

      default:
        return { content: [{ type: 'text', text: `Unknown tool: ${name}` }] };
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return { content: [{ type: 'text', text: `Error: ${message}` }] };
  }
});

// Start server
async function main() {
  const healthy = await kasHealth();
  if (!healthy) {
    console.error('Warning: KAS API is not healthy. Some tools may not work.');
  }

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('KAS MCP Server running on stdio');
}

main().catch(console.error);
```

### Step 1.4.4: Build and Test Locally (15 min)
```bash
cd /Users/d/claude-code/personal/knowledge-activation-system/mcp-server

# Build
npm run build

# Test manually (should output tool list)
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | node dist/index.js
```

### Step 1.4.5: Register in Claude Code (10 min)

Add to Claude Code MCP configuration (`~/.claude/claude_desktop_config.json` or similar):

```json
{
  "mcpServers": {
    "kas": {
      "command": "node",
      "args": ["/Users/d/claude-code/personal/knowledge-activation-system/mcp-server/dist/index.js"],
      "env": {
        "KAS_URL": "http://localhost:8000"
      }
    }
  }
}
```

### Step 1.4.6: End-to-End Test (10 min)

1. Restart Claude Code
2. Verify MCP server connects (check logs)
3. Test queries:
   - "Use kas_search to find information about FastAPI"
   - "Use kas_stats to show knowledge base statistics"

## 1.5 Testing Checklist

- [ ] `npm run build` succeeds without errors
- [ ] Server starts with `npm start`
- [ ] `kas_search` returns results for "FastAPI"
- [ ] `kas_stats` returns correct counts (176 docs, 815 chunks)
- [ ] Server handles KAS being down gracefully
- [ ] Claude Code recognizes the MCP server
- [ ] Tools appear in Claude Code tool list

## 1.6 Acceptance Criteria

**Priority 1 is COMPLETE when:**
1. MCP server is built and running
2. All three tools work (`kas_search`, `kas_ask`, `kas_stats`)
3. Server is registered in Claude Code config
4. You can query your knowledge base from any Claude Code session

## 1.7 Estimated Time: 2-3 hours

---

# PRIORITY 2: Q&A Endpoint Validation

## 2.1 Objective

Validate that the `/api/v1/ask` endpoint works correctly with AI synthesis, returning coherent answers with citations from the knowledge base.

## 2.2 Success Criteria

- [ ] AI provider configured (OpenRouter or DeepSeek)
- [ ] `/api/v1/ask` returns synthesized answers
- [ ] Confidence scoring works
- [ ] Citations are included in response
- [ ] Low-confidence warning appears when appropriate

## 2.3 Technical Specification

### Expected API Behavior
```
POST /api/v1/ask
{
  "query": "How do I implement streaming in FastAPI?"
}

Response:
{
  "answer": "To implement streaming in FastAPI, you can use...",
  "confidence": "high",
  "citations": [
    {
      "content_id": "uuid",
      "title": "FastAPI Documentation",
      "chunk_text": "..."
    }
  ],
  "warning": null  // or "Low confidence - results may not be accurate"
}
```

### AI Provider Options
| Provider | Model | Cost | Speed |
|----------|-------|------|-------|
| OpenRouter (free tier) | mistral-7b-instruct | Free | Medium |
| DeepSeek | deepseek-chat | $0.14/1M tokens | Fast |
| Claude | claude-3-haiku | $0.25/1M tokens | Fast |

## 2.4 Step-by-Step Implementation

### Step 2.4.1: Check Current Q&A Implementation (10 min)
```bash
# Test current endpoint
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "How does RAG work?"}' | python3 -m json.tool
```

### Step 2.4.2: Configure AI Provider (15 min)

Option A: OpenRouter (Recommended - Free Tier)
```bash
# Add to .env
echo 'OPENROUTER_API_KEY=your-key-here' >> /Users/d/claude-code/personal/knowledge-activation-system/.env
```

Option B: DeepSeek
```bash
echo 'DEEPSEEK_API_KEY=your-key-here' >> /Users/d/claude-code/personal/knowledge-activation-system/.env
```

### Step 2.4.3: Verify AI Configuration in Code (15 min)

Check `src/knowledge/ai.py` for provider configuration:
```python
# Expected configuration
AI_PROVIDERS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "models": ["mistralai/mistral-7b-instruct:free"]
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat"]
    }
}
```

### Step 2.4.4: Test Q&A Endpoint (20 min)

```bash
# Test 1: Basic question
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is FastAPI?"}' | python3 -m json.tool

# Test 2: Question requiring synthesis
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "Compare FastAPI and Flask for building APIs"}' | python3 -m json.tool

# Test 3: Question with no good answer (should show low confidence)
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "How do I cook pasta?"}' | python3 -m json.tool
```

### Step 2.4.5: Validate Response Quality (15 min)

Create test script:
```python
# /Users/d/claude-code/personal/knowledge-activation-system/scripts/test_qa.py
import httpx
import asyncio

TEST_QUESTIONS = [
    ("What is FastAPI?", "high"),
    ("How do I implement RAG?", "high"),
    ("What are transformer attention mechanisms?", "medium"),
    ("How do I cook pasta?", "low"),  # Should be low - not in KB
]

async def test_qa():
    async with httpx.AsyncClient() as client:
        for question, expected_confidence in TEST_QUESTIONS:
            response = await client.post(
                "http://localhost:8000/api/v1/ask",
                json={"query": question},
                timeout=60.0
            )
            data = response.json()

            print(f"\nQ: {question}")
            print(f"Confidence: {data.get('confidence', 'N/A')} (expected: {expected_confidence})")
            print(f"Answer: {data.get('answer', 'N/A')[:200]}...")
            print(f"Citations: {len(data.get('citations', []))}")

if __name__ == "__main__":
    asyncio.run(test_qa())
```

### Step 2.4.6: Fix Issues If Needed (30 min buffer)

Common issues:
- Missing API key → Add to .env
- Timeout → Increase timeout in settings
- No answer → Check AI provider connection
- Wrong confidence → Adjust threshold in qa.py

## 2.5 Testing Checklist

- [ ] AI provider API key is set
- [ ] Basic questions return answers
- [ ] Answers include citations
- [ ] Confidence scoring is accurate
- [ ] Low-confidence warning appears for irrelevant questions
- [ ] Response time is acceptable (<30s)

## 2.6 Acceptance Criteria

**Priority 2 is COMPLETE when:**
1. `/api/v1/ask` returns synthesized answers
2. Confidence scoring accurately reflects answer quality
3. Citations link back to source documents
4. MCP `kas_ask` tool works end-to-end

## 2.7 Estimated Time: 1-2 hours

---

# PRIORITY 3: Automated Knowledge Sync

## 3.1 Objective

Set up automated synchronization so the knowledge base stays fresh without manual intervention.

## 3.2 Success Criteria

- [ ] Sync script runs successfully
- [ ] Cron job scheduled for weekly sync
- [ ] Logs capture sync results
- [ ] Failed sources are retried
- [ ] Notification on sync completion

## 3.3 Technical Specification

### Sync Architecture
```
┌────────────┐     cron      ┌────────────┐     HTTP      ┌────────────┐
│  crontab   │──────────────►│  sync.sh   │──────────────►│    KAS     │
│  (weekly)  │               │            │               │            │
└────────────┘               └────────────┘               └────────────┘
                                   │
                                   ▼
                             ┌────────────┐
                             │  Log File  │
                             │  + Alert   │
                             └────────────┘
```

### Sync Modes
| Mode | Description | Use Case |
|------|-------------|----------|
| `--full` | Sync all sources | First run, monthly refresh |
| `--update-only` | Skip unchanged | Weekly updates |
| `--failed-only` | Retry failed | After fixing URLs |

## 3.4 Step-by-Step Implementation

### Step 3.4.1: Create Sync Script (15 min)
```bash
cat > /Users/d/claude-code/projects-2026/knowledge-seeder/sync.sh << 'EOF'
#!/bin/bash
# Knowledge Seeder Automated Sync Script
# Run via cron: 0 4 * * 0 /path/to/sync.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/var/log/knowledge-seeder"
LOG_FILE="$LOG_DIR/sync-$(date +%Y%m%d-%H%M%S).log"
VENV_PATH="$SCRIPT_DIR/.venv"

# Create log directory if needed
mkdir -p "$LOG_DIR"

# Redirect all output to log
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=========================================="
echo "Knowledge Seeder Sync - $(date)"
echo "=========================================="

# Check KAS health first
echo "Checking KAS health..."
KAS_HEALTH=$(curl -sf http://localhost:8000/api/v1/health || echo '{"status":"error"}')
KAS_STATUS=$(echo "$KAS_HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','error'))")

if [ "$KAS_STATUS" != "healthy" ]; then
    echo "ERROR: KAS is not healthy. Aborting sync."
    echo "KAS response: $KAS_HEALTH"
    exit 1
fi

echo "KAS is healthy. Starting sync..."

# Activate virtual environment
cd "$SCRIPT_DIR"
source "$VENV_PATH/bin/activate"

# Get pre-sync stats
PRE_STATS=$(curl -sf http://localhost:8000/api/v1/stats)
PRE_DOCS=$(echo "$PRE_STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_content',0))")

echo "Pre-sync document count: $PRE_DOCS"

# Run sync (update-only mode for weekly)
echo "Running knowledge-seeder sync..."
python -m knowledge_seeder sync sources/*.yaml --update-only 2>&1

# Get post-sync stats
POST_STATS=$(curl -sf http://localhost:8000/api/v1/stats)
POST_DOCS=$(echo "$POST_STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_content',0))")
POST_CHUNKS=$(echo "$POST_STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_chunks',0))")

NEW_DOCS=$((POST_DOCS - PRE_DOCS))

echo ""
echo "=========================================="
echo "Sync Complete - $(date)"
echo "=========================================="
echo "Documents before: $PRE_DOCS"
echo "Documents after:  $POST_DOCS"
echo "New documents:    $NEW_DOCS"
echo "Total chunks:     $POST_CHUNKS"
echo ""

# Send notification (macOS)
if [ "$NEW_DOCS" -gt 0 ]; then
    osascript -e "display notification \"Added $NEW_DOCS new documents\" with title \"Knowledge Sync Complete\""
else
    osascript -e "display notification \"No new documents\" with title \"Knowledge Sync Complete\""
fi

echo "Log saved to: $LOG_FILE"
EOF

chmod +x /Users/d/claude-code/projects-2026/knowledge-seeder/sync.sh
```

### Step 3.4.2: Create Log Directory (5 min)
```bash
sudo mkdir -p /var/log/knowledge-seeder
sudo chown $(whoami) /var/log/knowledge-seeder
```

### Step 3.4.3: Test Sync Script (10 min)
```bash
# Run manually first
/Users/d/claude-code/projects-2026/knowledge-seeder/sync.sh

# Check log
ls -la /var/log/knowledge-seeder/
cat /var/log/knowledge-seeder/sync-*.log | tail -50
```

### Step 3.4.4: Schedule Cron Job (10 min)
```bash
# Open crontab editor
crontab -e

# Add this line (Sunday 4am):
# 0 4 * * 0 /Users/d/claude-code/projects-2026/knowledge-seeder/sync.sh

# Verify cron is set
crontab -l
```

### Step 3.4.5: Create Manual Sync Commands (10 min)
```bash
# Add aliases to ~/.zshrc or ~/.bashrc
cat >> ~/.zshrc << 'EOF'

# Knowledge Seeder aliases
alias ks-sync='/Users/d/claude-code/projects-2026/knowledge-seeder/sync.sh'
alias ks-status='curl -s http://localhost:8000/api/v1/stats | python3 -m json.tool'
alias ks-health='curl -s http://localhost:8000/api/v1/health | python3 -m json.tool'
alias ks-logs='tail -f /var/log/knowledge-seeder/sync-*.log | tail -1'
EOF

source ~/.zshrc
```

## 3.5 Testing Checklist

- [ ] sync.sh runs without errors
- [ ] KAS health check works
- [ ] Logs are created in /var/log/knowledge-seeder/
- [ ] macOS notification appears
- [ ] Cron job is scheduled
- [ ] Manual aliases work

## 3.6 Acceptance Criteria

**Priority 3 is COMPLETE when:**
1. `ks-sync` runs the sync manually
2. Cron job is scheduled for weekly sync
3. Logs capture all sync activity
4. Notifications alert on completion

## 3.7 Estimated Time: 1 hour

---

# PRIORITY 4: Fix Broken Sources

## 4.1 Objective

Fix the 50 broken/skipped sources to maximize knowledge coverage.

## 4.2 Success Criteria

- [ ] Identify all broken URLs
- [ ] Find alternatives for blocked sources
- [ ] Update YAML files with correct URLs
- [ ] Re-run sync for fixed sources
- [ ] Coverage increases from 83% to 95%+

## 4.3 Technical Specification

### Broken Sources Summary
| Category | Count | Root Cause | Solution |
|----------|-------|------------|----------|
| OpenAI Platform | 8 | Bot blocking (403) | Use API docs instead / manual |
| LangGraph | 5 | Docs moved | Update to docs.langchain.com |
| LlamaIndex | 3 | URL restructure | Find new paths |
| GitHub links | 15 | Tree/blob paths | Fix path format |
| Content too short | 5 | Extraction failure | Try different extractor |
| Other 404s | 14 | Various | Find alternatives |

## 4.4 Step-by-Step Implementation

### Step 4.4.1: Export Broken Sources List (15 min)
```bash
cd /Users/d/claude-code/projects-2026/knowledge-seeder

# Create report of skipped sources
python3 << 'EOF'
import sqlite3
import json

conn = sqlite3.connect('state.db')
cursor = conn.cursor()

# Get failed/skipped sources
cursor.execute("""
    SELECT source_id, url, status, error_message, namespace
    FROM sources
    WHERE status IN ('failed', 'skipped', 'error')
    ORDER BY namespace, source_id
""")

results = cursor.fetchall()

print(f"Total broken sources: {len(results)}\n")
print("=" * 80)

for source_id, url, status, error, namespace in results:
    print(f"Namespace: {namespace}")
    print(f"Source ID: {source_id}")
    print(f"URL: {url}")
    print(f"Status: {status}")
    print(f"Error: {error}")
    print("-" * 80)

conn.close()
EOF > /tmp/broken_sources.txt

# Review the list
cat /tmp/broken_sources.txt
```

### Step 4.4.2: Fix LangGraph URLs (20 min)

LangGraph docs moved to `docs.langchain.com/langgraph/`.

```bash
# Find LangGraph entries in YAML files
grep -r "langchain-ai.github.io/langgraph" sources/

# Update URLs in YAML files
# Example fix:
# OLD: https://langchain-ai.github.io/langgraph/concepts/
# NEW: https://docs.langchain.com/langgraph/concepts/
```

### Step 4.4.3: Fix LlamaIndex URLs (20 min)
```bash
# Find LlamaIndex entries
grep -r "llamaindex" sources/

# Check current documentation structure
curl -s https://docs.llamaindex.ai/ | head -50

# Update URLs accordingly
```

### Step 4.4.4: Fix GitHub Links (30 min)
```bash
# Common issues:
# - tree/main/docs → raw URLs or different paths
# - Repository structure changes

# Find GitHub entries
grep -r "github.com" sources/ | grep -E "tree|blob"

# For each broken link, verify:
curl -sI "URL" | head -5
```

### Step 4.4.5: Handle OpenAI Blocked Docs (20 min)

OpenAI blocks automated requests. Options:
1. Use official API documentation (usually accessible)
2. Manual snapshot ingestion
3. Skip and document as "manual required"

```yaml
# In sources/ai-ml.yaml, mark as manual:
- id: openai-function-calling
  url: https://platform.openai.com/docs/guides/function-calling
  status: manual_required
  notes: "Blocked by bot protection. Requires manual extraction."
```

### Step 4.4.6: Re-run Sync for Fixed Sources (15 min)
```bash
# Retry failed sources only
cd /Users/d/claude-code/projects-2026/knowledge-seeder
source .venv/bin/activate

# Clear failed status to retry
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('state.db')
cursor = conn.cursor()
cursor.execute("UPDATE sources SET status = 'pending' WHERE status IN ('failed', 'skipped')")
conn.commit()
print(f"Reset {cursor.rowcount} sources to pending")
conn.close()
EOF

# Run sync
python -m knowledge_seeder sync sources/*.yaml
```

### Step 4.4.7: Verify Coverage Improvement (10 min)
```bash
# Check new stats
curl -s http://localhost:8000/api/v1/stats | python3 -m json.tool

# Expected: documents should increase from 176 to ~200+
```

## 4.5 Testing Checklist

- [ ] Broken sources list exported
- [ ] LangGraph URLs fixed and working
- [ ] LlamaIndex URLs fixed and working
- [ ] GitHub links fixed and working
- [ ] OpenAI docs marked appropriately
- [ ] Re-sync completed
- [ ] Document count increased

## 4.6 Acceptance Criteria

**Priority 4 is COMPLETE when:**
1. All fixable URLs have been updated
2. Re-sync adds at least 20 new documents
3. Coverage is 90%+ of accessible sources
4. Unfixable sources are documented

## 4.7 Estimated Time: 2-3 hours

---

# PRIORITY 5: Service Management & Monitoring

## 5.1 Objective

Ensure KAS runs reliably as a background service with health monitoring and alerting.

## 5.2 Success Criteria

- [ ] KAS starts automatically on boot
- [ ] KAS restarts on failure
- [ ] Health checks run every 5 minutes
- [ ] Alerts on service failure
- [ ] Logs are rotated

## 5.3 Technical Specification

### Service Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                        macOS System                              │
├─────────────────────────────────────────────────────────────────┤
│  launchd                                                        │
│  ├── com.kas.api.plist        → KAS API Server                  │
│  └── com.kas.healthcheck.plist → Health Check (every 5 min)     │
├─────────────────────────────────────────────────────────────────┤
│  Logs                                                           │
│  ├── /var/log/kas/api.log     → API server logs                 │
│  ├── /var/log/kas/health.log  → Health check logs               │
│  └── /var/log/knowledge-seeder/ → Sync logs                     │
└─────────────────────────────────────────────────────────────────┘
```

## 5.4 Step-by-Step Implementation

### Step 5.4.1: Create Log Directory (5 min)
```bash
sudo mkdir -p /var/log/kas
sudo chown $(whoami) /var/log/kas
```

### Step 5.4.2: Create KAS Start Script (15 min)
```bash
cat > /Users/d/claude-code/personal/knowledge-activation-system/scripts/start-kas.sh << 'EOF'
#!/bin/bash
# KAS API Server Start Script

set -e

KAS_DIR="/Users/d/claude-code/personal/knowledge-activation-system"
LOG_FILE="/var/log/kas/api.log"
PID_FILE="/tmp/kas-api.pid"

cd "$KAS_DIR"

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "KAS already running (PID: $OLD_PID)"
        exit 0
    fi
fi

# Ensure dependencies
echo "$(date): Starting KAS API server..." >> "$LOG_FILE"

# Check PostgreSQL
if ! docker ps | grep -q "knowledge-db"; then
    echo "$(date): Starting PostgreSQL..." >> "$LOG_FILE"
    docker compose up -d postgres
    sleep 5
fi

# Start API server
source .venv/bin/activate 2>/dev/null || uv sync
exec uvicorn knowledge.api.main:app --host 0.0.0.0 --port 8000 >> "$LOG_FILE" 2>&1 &

echo $! > "$PID_FILE"
echo "$(date): KAS started (PID: $!)" >> "$LOG_FILE"
EOF

chmod +x /Users/d/claude-code/personal/knowledge-activation-system/scripts/start-kas.sh
```

### Step 5.4.3: Create launchd Service (20 min)
```bash
cat > ~/Library/LaunchAgents/com.kas.api.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.kas.api</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>cd /Users/d/claude-code/personal/knowledge-activation-system && source .venv/bin/activate && exec uvicorn knowledge.api.main:app --host 0.0.0.0 --port 8000</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/d/claude-code/personal/knowledge-activation-system</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
        <key>KNOWLEDGE_DATABASE_URL</key>
        <string>postgresql://knowledge:localdev@localhost:5433/knowledge</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>StandardOutPath</key>
    <string>/var/log/kas/api.stdout.log</string>

    <key>StandardErrorPath</key>
    <string>/var/log/kas/api.stderr.log</string>

    <key>ThrottleInterval</key>
    <integer>30</integer>
</dict>
</plist>
EOF
```

### Step 5.4.4: Create Health Check Script (15 min)
```bash
cat > /Users/d/claude-code/personal/knowledge-activation-system/scripts/health-check.sh << 'EOF'
#!/bin/bash
# KAS Health Check Script

LOG_FILE="/var/log/kas/health.log"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# Check KAS API
KAS_RESPONSE=$(curl -sf http://localhost:8000/api/v1/health 2>/dev/null)
KAS_STATUS=$?

if [ $KAS_STATUS -eq 0 ]; then
    STATUS=$(echo "$KAS_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null)
    if [ "$STATUS" = "healthy" ]; then
        echo "$TIMESTAMP: KAS healthy" >> "$LOG_FILE"
    else
        echo "$TIMESTAMP: KAS degraded - $KAS_RESPONSE" >> "$LOG_FILE"
        osascript -e "display notification \"KAS is degraded\" with title \"KAS Alert\" sound name \"Basso\""
    fi
else
    echo "$TIMESTAMP: KAS DOWN - curl exit code $KAS_STATUS" >> "$LOG_FILE"
    osascript -e "display notification \"KAS is DOWN!\" with title \"KAS Alert\" sound name \"Basso\""

    # Try to restart
    launchctl kickstart -k gui/$(id -u)/com.kas.api 2>/dev/null
fi

# Check PostgreSQL
if docker ps | grep -q "knowledge-db"; then
    echo "$TIMESTAMP: PostgreSQL healthy" >> "$LOG_FILE"
else
    echo "$TIMESTAMP: PostgreSQL DOWN" >> "$LOG_FILE"
    osascript -e "display notification \"PostgreSQL is DOWN!\" with title \"KAS Alert\" sound name \"Basso\""

    # Try to restart
    cd /Users/d/claude-code/personal/knowledge-activation-system
    docker compose up -d postgres
fi

# Check Ollama
OLLAMA_RESPONSE=$(curl -sf http://localhost:11434/api/tags 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$TIMESTAMP: Ollama healthy" >> "$LOG_FILE"
else
    echo "$TIMESTAMP: Ollama DOWN" >> "$LOG_FILE"
fi

# Trim log file (keep last 1000 lines)
tail -1000 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
EOF

chmod +x /Users/d/claude-code/personal/knowledge-activation-system/scripts/health-check.sh
```

### Step 5.4.5: Create Health Check launchd Service (10 min)
```bash
cat > ~/Library/LaunchAgents/com.kas.healthcheck.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.kas.healthcheck</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/d/claude-code/personal/knowledge-activation-system/scripts/health-check.sh</string>
    </array>

    <key>StartInterval</key>
    <integer>300</integer>

    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
EOF
```

### Step 5.4.6: Load Services (10 min)
```bash
# Load services
launchctl load ~/Library/LaunchAgents/com.kas.api.plist
launchctl load ~/Library/LaunchAgents/com.kas.healthcheck.plist

# Verify running
launchctl list | grep kas

# Check status
curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
```

### Step 5.4.7: Create Management Commands (10 min)
```bash
cat >> ~/.zshrc << 'EOF'

# KAS Service Management
alias kas-start='launchctl load ~/Library/LaunchAgents/com.kas.api.plist'
alias kas-stop='launchctl unload ~/Library/LaunchAgents/com.kas.api.plist'
alias kas-restart='kas-stop && sleep 2 && kas-start'
alias kas-logs='tail -f /var/log/kas/api.stderr.log'
alias kas-health-logs='tail -f /var/log/kas/health.log'
EOF

source ~/.zshrc
```

## 5.5 Testing Checklist

- [ ] launchd services created
- [ ] KAS starts automatically
- [ ] Health check runs every 5 minutes
- [ ] Alert appears when KAS is down
- [ ] KAS restarts after failure
- [ ] Logs are being written
- [ ] Management aliases work

## 5.6 Acceptance Criteria

**Priority 5 is COMPLETE when:**
1. `kas-start`, `kas-stop`, `kas-restart` commands work
2. KAS auto-starts on login
3. Health checks run every 5 minutes
4. macOS notifications alert on failures
5. Logs are in /var/log/kas/

## 5.7 Estimated Time: 2-3 hours

---

# PRIORITY 6: RAG Evaluation Framework

## 6.1 Objective

Create an objective measurement system for search and answer quality using RAGAS metrics.

## 6.2 Success Criteria

- [ ] Test query set created (50+ queries)
- [ ] RAGAS evaluation script working
- [ ] Baseline metrics established
- [ ] Metrics tracked over time
- [ ] Report generation automated

## 6.3 Technical Specification

### RAGAS Metrics
| Metric | Description | Target |
|--------|-------------|--------|
| Context Precision | Are retrieved chunks relevant? | > 0.8 |
| Context Recall | Are all relevant chunks retrieved? | > 0.7 |
| Answer Relevancy | Does answer address the question? | > 0.8 |
| Faithfulness | Is answer grounded in context? | > 0.9 |

### Directory Structure
```
/Users/d/claude-code/personal/knowledge-activation-system/evaluation/
├── test_queries.yaml       # Test dataset
├── evaluate.py             # Evaluation script
├── metrics/                # Historical metrics (JSON)
│   └── 2026-01-13.json
├── reports/                # Generated reports
│   └── 2026-01-13.md
└── README.md
```

## 6.4 Step-by-Step Implementation

### Step 6.4.1: Create Evaluation Directory (5 min)
```bash
mkdir -p /Users/d/claude-code/personal/knowledge-activation-system/evaluation/{metrics,reports}
```

### Step 6.4.2: Create Test Query Dataset (30 min)
```yaml
# /Users/d/claude-code/personal/knowledge-activation-system/evaluation/test_queries.yaml
# Test queries with expected relevant content

queries:
  # Frameworks
  - id: frameworks-001
    question: "How do I create a FastAPI endpoint?"
    expected_topics: ["FastAPI", "endpoint", "decorator", "@app.get"]
    namespace: frameworks
    difficulty: easy

  - id: frameworks-002
    question: "What is dependency injection in FastAPI?"
    expected_topics: ["Depends", "dependency", "injection"]
    namespace: frameworks
    difficulty: medium

  - id: frameworks-003
    question: "How do I implement WebSocket in FastAPI?"
    expected_topics: ["WebSocket", "async", "connection"]
    namespace: frameworks
    difficulty: hard

  # AI/ML
  - id: ai-ml-001
    question: "What is RAG and how does it work?"
    expected_topics: ["retrieval", "augmented", "generation", "vector"]
    namespace: ai-ml
    difficulty: easy

  - id: ai-ml-002
    question: "How do transformer attention mechanisms work?"
    expected_topics: ["attention", "query", "key", "value", "softmax"]
    namespace: ai-ml
    difficulty: hard

  - id: ai-ml-003
    question: "What are the best practices for RAG evaluation?"
    expected_topics: ["RAGAS", "evaluation", "metrics", "precision"]
    namespace: ai-ml
    difficulty: medium

  # Infrastructure
  - id: infra-001
    question: "How do I set up a Docker container?"
    expected_topics: ["Docker", "container", "Dockerfile"]
    namespace: infrastructure
    difficulty: easy

  - id: infra-002
    question: "What is Kubernetes and when should I use it?"
    expected_topics: ["Kubernetes", "orchestration", "pods", "scaling"]
    namespace: infrastructure
    difficulty: medium

  # Negative tests (should have low confidence)
  - id: negative-001
    question: "How do I cook Italian pasta?"
    expected_topics: []
    namespace: null
    difficulty: negative
    expected_confidence: low

  - id: negative-002
    question: "What is the capital of France?"
    expected_topics: []
    namespace: null
    difficulty: negative
    expected_confidence: low

# Add 40 more queries covering all namespaces...
```

### Step 6.4.3: Create Evaluation Script (45 min)
```python
# /Users/d/claude-code/personal/knowledge-activation-system/evaluation/evaluate.py
"""
KAS RAG Evaluation Script using RAGAS metrics.
"""

import asyncio
import json
import yaml
import httpx
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

# Try to import RAGAS (optional)
try:
    from ragas import evaluate
    from ragas.metrics import (
        context_precision,
        context_recall,
        answer_relevancy,
        faithfulness,
    )
    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False
    print("Warning: RAGAS not installed. Using simplified metrics.")


@dataclass
class QueryResult:
    query_id: str
    question: str
    search_results: int
    answer_length: int
    confidence: str
    has_citations: bool
    response_time_ms: float
    context_relevance: float  # Simplified metric
    error: Optional[str] = None


@dataclass
class EvaluationReport:
    timestamp: str
    total_queries: int
    successful_queries: int
    failed_queries: int
    avg_response_time_ms: float
    avg_search_results: float
    avg_context_relevance: float
    high_confidence_pct: float
    medium_confidence_pct: float
    low_confidence_pct: float
    results: list


KAS_URL = "http://localhost:8000"


async def evaluate_query(client: httpx.AsyncClient, query: dict) -> QueryResult:
    """Evaluate a single query."""
    query_id = query["id"]
    question = query["question"]
    expected_topics = query.get("expected_topics", [])

    start_time = datetime.now()

    try:
        # Search
        search_response = await client.get(
            f"{KAS_URL}/api/v1/search",
            params={"q": question, "limit": 10},
            timeout=30.0
        )
        search_data = search_response.json()
        search_results = search_data.get("total", 0)

        # Ask
        ask_response = await client.post(
            f"{KAS_URL}/api/v1/ask",
            json={"query": question},
            timeout=60.0
        )
        ask_data = ask_response.json()

        response_time = (datetime.now() - start_time).total_seconds() * 1000

        # Calculate context relevance (simplified)
        context_relevance = 0.0
        if search_results > 0 and expected_topics:
            chunks_text = " ".join([
                r.get("chunk_text", "") or ""
                for r in search_data.get("results", [])
            ]).lower()

            matches = sum(1 for topic in expected_topics if topic.lower() in chunks_text)
            context_relevance = matches / len(expected_topics) if expected_topics else 0.0
        elif not expected_topics:
            # Negative test - should have low results
            context_relevance = 1.0 if search_results == 0 else 0.5

        return QueryResult(
            query_id=query_id,
            question=question,
            search_results=search_results,
            answer_length=len(ask_data.get("answer", "")),
            confidence=ask_data.get("confidence", "unknown"),
            has_citations=len(ask_data.get("citations", [])) > 0,
            response_time_ms=response_time,
            context_relevance=context_relevance,
        )

    except Exception as e:
        return QueryResult(
            query_id=query_id,
            question=question,
            search_results=0,
            answer_length=0,
            confidence="error",
            has_citations=False,
            response_time_ms=0,
            context_relevance=0,
            error=str(e),
        )


async def run_evaluation():
    """Run full evaluation suite."""
    # Load test queries
    queries_path = Path(__file__).parent / "test_queries.yaml"
    with open(queries_path) as f:
        data = yaml.safe_load(f)

    queries = data.get("queries", [])
    print(f"Loaded {len(queries)} test queries")

    # Run evaluations
    results = []
    async with httpx.AsyncClient() as client:
        for i, query in enumerate(queries):
            print(f"Evaluating {i+1}/{len(queries)}: {query['id']}")
            result = await evaluate_query(client, query)
            results.append(result)
            await asyncio.sleep(0.5)  # Rate limiting

    # Calculate aggregate metrics
    successful = [r for r in results if r.error is None]
    failed = [r for r in results if r.error is not None]

    confidence_counts = {"high": 0, "medium": 0, "low": 0}
    for r in successful:
        if r.confidence in confidence_counts:
            confidence_counts[r.confidence] += 1

    total_successful = len(successful) or 1

    report = EvaluationReport(
        timestamp=datetime.now().isoformat(),
        total_queries=len(queries),
        successful_queries=len(successful),
        failed_queries=len(failed),
        avg_response_time_ms=sum(r.response_time_ms for r in successful) / total_successful,
        avg_search_results=sum(r.search_results for r in successful) / total_successful,
        avg_context_relevance=sum(r.context_relevance for r in successful) / total_successful,
        high_confidence_pct=confidence_counts["high"] / total_successful * 100,
        medium_confidence_pct=confidence_counts["medium"] / total_successful * 100,
        low_confidence_pct=confidence_counts["low"] / total_successful * 100,
        results=[asdict(r) for r in results],
    )

    # Save metrics
    metrics_dir = Path(__file__).parent / "metrics"
    metrics_file = metrics_dir / f"{datetime.now().strftime('%Y-%m-%d')}.json"
    with open(metrics_file, "w") as f:
        json.dump(asdict(report), f, indent=2)

    print(f"\nMetrics saved to: {metrics_file}")

    # Generate report
    generate_report(report)

    return report


def generate_report(report: EvaluationReport):
    """Generate markdown report."""
    reports_dir = Path(__file__).parent / "reports"
    report_file = reports_dir / f"{datetime.now().strftime('%Y-%m-%d')}.md"

    content = f"""# KAS Evaluation Report

**Date:** {report.timestamp}
**Status:** {'PASS' if report.avg_context_relevance > 0.7 else 'NEEDS IMPROVEMENT'}

## Summary

| Metric | Value | Target |
|--------|-------|--------|
| Total Queries | {report.total_queries} | - |
| Successful | {report.successful_queries} | 100% |
| Failed | {report.failed_queries} | 0 |
| Avg Response Time | {report.avg_response_time_ms:.0f}ms | <5000ms |
| Avg Search Results | {report.avg_search_results:.1f} | >3 |
| Context Relevance | {report.avg_context_relevance:.2%} | >70% |

## Confidence Distribution

| Confidence | Percentage |
|------------|------------|
| High | {report.high_confidence_pct:.1f}% |
| Medium | {report.medium_confidence_pct:.1f}% |
| Low | {report.low_confidence_pct:.1f}% |

## Detailed Results

| Query ID | Results | Confidence | Relevance | Time (ms) |
|----------|---------|------------|-----------|-----------|
"""

    for r in report.results[:20]:  # Show top 20
        status = "✅" if r.get("error") is None else "❌"
        content += f"| {r['query_id']} | {r['search_results']} | {r['confidence']} | {r['context_relevance']:.2f} | {r['response_time_ms']:.0f} |\n"

    content += f"\n\n*Report generated at {report.timestamp}*\n"

    with open(report_file, "w") as f:
        f.write(content)

    print(f"Report saved to: {report_file}")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
```

### Step 6.4.4: Install Dependencies (5 min)
```bash
cd /Users/d/claude-code/personal/knowledge-activation-system
uv add pyyaml ragas
```

### Step 6.4.5: Run Initial Evaluation (15 min)
```bash
cd /Users/d/claude-code/personal/knowledge-activation-system
uv run python evaluation/evaluate.py
```

### Step 6.4.6: Create Evaluation Alias (5 min)
```bash
cat >> ~/.zshrc << 'EOF'

# KAS Evaluation
alias kas-eval='cd /Users/d/claude-code/personal/knowledge-activation-system && uv run python evaluation/evaluate.py'
alias kas-report='cat /Users/d/claude-code/personal/knowledge-activation-system/evaluation/reports/$(ls -t /Users/d/claude-code/personal/knowledge-activation-system/evaluation/reports/ | head -1)'
EOF

source ~/.zshrc
```

## 6.5 Testing Checklist

- [ ] Test queries created (10+ queries minimum)
- [ ] Evaluation script runs without errors
- [ ] Metrics JSON file generated
- [ ] Report markdown file generated
- [ ] Baseline metrics recorded
- [ ] Aliases work

## 6.6 Acceptance Criteria

**Priority 6 is COMPLETE when:**
1. `kas-eval` runs the evaluation suite
2. Metrics are saved to evaluation/metrics/
3. Reports are generated in evaluation/reports/
4. Baseline context relevance is >50%

## 6.7 Estimated Time: 3-4 hours

---

# PRIORITY 7: Web Dashboard

## 7.1 Objective

Create a visual interface for KAS with search, browsing, and monitoring capabilities.

## 7.2 Success Criteria

- [ ] Dashboard runs on localhost:3000
- [ ] Search interface works
- [ ] Content browser shows all documents
- [ ] Stats page shows system health
- [ ] Responsive design

## 7.3 Technical Specification

### Architecture
```
┌──────────────────────────────────────────────────────────────┐
│                   Next.js 15 Frontend                         │
│                   localhost:3000                              │
├──────────────────────────────────────────────────────────────┤
│  Pages:                                                       │
│  ├── /              → Dashboard home (stats overview)         │
│  ├── /search        → Search interface                        │
│  ├── /browse        → Content browser                         │
│  ├── /document/[id] → Document detail view                    │
│  └── /health        → System health                           │
├──────────────────────────────────────────────────────────────┤
│  Components:                                                  │
│  ├── SearchBar      → Query input                             │
│  ├── ResultCard     → Search result display                   │
│  ├── StatsCard      → Metric display                          │
│  └── ContentTable   → Document list                           │
└──────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP
                              ▼
                    ┌──────────────────┐
                    │     KAS API      │
                    │   localhost:8000 │
                    └──────────────────┘
```

### Tech Stack
- Next.js 15 (App Router)
- TypeScript
- Tailwind CSS
- shadcn/ui components

## 7.4 Step-by-Step Implementation

### Step 7.4.1: Check Existing Web Directory (10 min)
```bash
# Check what exists
ls -la /Users/d/claude-code/personal/knowledge-activation-system/web/

# If exists, check structure
tree /Users/d/claude-code/personal/knowledge-activation-system/web/ -L 2
```

### Step 7.4.2: Initialize or Update Project (20 min)

If starting fresh:
```bash
cd /Users/d/claude-code/personal/knowledge-activation-system
npx create-next-app@latest web --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"
cd web
npx shadcn@latest init
npx shadcn@latest add button card input table badge
```

### Step 7.4.3: Create KAS Client (15 min)
```typescript
// web/src/lib/kas-client.ts
const KAS_URL = process.env.NEXT_PUBLIC_KAS_URL || 'http://localhost:8000';

export interface SearchResult {
  content_id: string;
  title: string;
  content_type: string;
  score: number;
  chunk_text: string | null;
}

export interface SearchResponse {
  results: SearchResult[];
  query: string;
  total: number;
}

export interface StatsResponse {
  total_content: number;
  total_chunks: number;
  content_by_type: Record<string, number>;
  review_active: number;
  review_due: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  services: Record<string, string>;
  stats: {
    total_content: number;
    total_chunks: number;
  };
}

export async function search(query: string, limit = 10): Promise<SearchResponse> {
  const res = await fetch(`${KAS_URL}/api/v1/search?q=${encodeURIComponent(query)}&limit=${limit}`);
  if (!res.ok) throw new Error('Search failed');
  return res.json();
}

export async function getStats(): Promise<StatsResponse> {
  const res = await fetch(`${KAS_URL}/api/v1/stats`);
  if (!res.ok) throw new Error('Failed to get stats');
  return res.json();
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${KAS_URL}/api/v1/health`);
  if (!res.ok) throw new Error('Failed to get health');
  return res.json();
}
```

### Step 7.4.4: Create Dashboard Page (30 min)
```typescript
// web/src/app/page.tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getStats, getHealth } from "@/lib/kas-client";

export default async function Dashboard() {
  const [stats, health] = await Promise.all([
    getStats().catch(() => null),
    getHealth().catch(() => null),
  ]);

  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Knowledge Activation System</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <Card>
          <CardHeader>
            <CardTitle>Documents</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-4xl font-bold">{stats?.total_content || 0}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Chunks</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-4xl font-bold">{stats?.total_chunks || 0}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Status</CardTitle>
          </CardHeader>
          <CardContent>
            <p className={`text-4xl font-bold ${health?.status === 'healthy' ? 'text-green-500' : 'text-red-500'}`}>
              {health?.status || 'Unknown'}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Content by Type</CardTitle>
          </CardHeader>
          <CardContent>
            <ul>
              {stats?.content_by_type && Object.entries(stats.content_by_type).map(([type, count]) => (
                <li key={type} className="flex justify-between py-1">
                  <span className="capitalize">{type}</span>
                  <span className="font-mono">{count}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Services</CardTitle>
          </CardHeader>
          <CardContent>
            <ul>
              {health?.services && Object.entries(health.services).map(([service, status]) => (
                <li key={service} className="flex justify-between py-1">
                  <span className="capitalize">{service}</span>
                  <span className={status === 'connected' || status === 'available' ? 'text-green-500' : 'text-red-500'}>
                    {status}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
```

### Step 7.4.5: Create Search Page (30 min)
```typescript
// web/src/app/search/page.tsx
'use client';

import { useState } from 'react';
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { search, SearchResult } from "@/lib/kas-client";

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;

    setLoading(true);
    try {
      const data = await search(query);
      setResults(data.results);
      setSearched(true);
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Search Knowledge Base</h1>

      <div className="flex gap-2 mb-6">
        <Input
          placeholder="Search for anything..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="flex-1"
        />
        <Button onClick={handleSearch} disabled={loading}>
          {loading ? 'Searching...' : 'Search'}
        </Button>
      </div>

      {searched && results.length === 0 && (
        <p className="text-gray-500">No results found for "{query}"</p>
      )}

      <div className="space-y-4">
        {results.map((result) => (
          <Card key={result.content_id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">{result.title}</CardTitle>
                <div className="flex gap-2">
                  <Badge variant="outline">{result.content_type}</Badge>
                  <Badge variant="secondary">{(result.score * 100).toFixed(1)}%</Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-600 line-clamp-3">
                {result.chunk_text || 'No preview available'}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
```

### Step 7.4.6: Create Navigation (15 min)
```typescript
// web/src/components/nav.tsx
import Link from 'next/link';

export function Nav() {
  return (
    <nav className="border-b bg-white">
      <div className="container mx-auto px-6 py-3">
        <div className="flex items-center justify-between">
          <Link href="/" className="text-xl font-bold">KAS</Link>
          <div className="flex gap-6">
            <Link href="/" className="hover:text-blue-600">Dashboard</Link>
            <Link href="/search" className="hover:text-blue-600">Search</Link>
            <Link href="/browse" className="hover:text-blue-600">Browse</Link>
            <Link href="/health" className="hover:text-blue-600">Health</Link>
          </div>
        </div>
      </div>
    </nav>
  );
}
```

### Step 7.4.7: Update Layout (10 min)
```typescript
// web/src/app/layout.tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/nav";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Knowledge Activation System",
  description: "AI-powered personal knowledge management",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <Nav />
        <main>{children}</main>
      </body>
    </html>
  );
}
```

### Step 7.4.8: Add Environment Config (5 min)
```bash
# web/.env.local
echo 'NEXT_PUBLIC_KAS_URL=http://localhost:8000' > /Users/d/claude-code/personal/knowledge-activation-system/web/.env.local
```

### Step 7.4.9: Run and Test (15 min)
```bash
cd /Users/d/claude-code/personal/knowledge-activation-system/web
npm run dev

# Open http://localhost:3000
```

## 7.5 Testing Checklist

- [ ] Dashboard shows correct stats
- [ ] Search returns results
- [ ] Navigation works
- [ ] Responsive on mobile
- [ ] Handles KAS being down gracefully

## 7.6 Acceptance Criteria

**Priority 7 is COMPLETE when:**
1. Dashboard shows document/chunk counts
2. Search interface returns relevant results
3. All pages load without errors
4. Design is clean and usable

## 7.7 Estimated Time: 6-8 hours

---

# PRIORITY 8: Spaced Repetition Activation

## 8.1 Objective

Activate the FSRS spaced repetition system to enable active learning from the knowledge base.

## 8.2 Success Criteria

- [ ] High-value content added to review queue
- [ ] Daily review command works
- [ ] Review submission updates scheduling
- [ ] Retention metrics tracked
- [ ] Review reminders configured

## 8.3 Technical Specification

### FSRS Flow
```
                    ┌─────────────────┐
                    │  Review Queue   │
                    │  (PostgreSQL)   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
         ┌────────┐    ┌────────┐    ┌────────┐
         │  New   │    │Learning│    │ Review │
         │        │───▶│        │───▶│        │
         └────────┘    └────────┘    └────────┘
              │              │              │
              └──────────────┴──────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   FSRS Engine   │
                    │   (py-fsrs)     │
                    └─────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Next Review Date│
                    └─────────────────┘
```

### Review Ratings
| Rating | Description | Effect |
|--------|-------------|--------|
| Again (1) | Didn't remember | Reset to learning |
| Hard (2) | Barely remembered | Shorter interval |
| Good (3) | Remembered | Normal interval |
| Easy (4) | Easy recall | Longer interval |

## 8.4 Step-by-Step Implementation

### Step 8.4.1: Check Current Review State (10 min)
```bash
# Check review queue
curl -s http://localhost:8000/review/due | python3 -m json.tool

# Check review stats
curl -s http://localhost:8000/review/stats | python3 -m json.tool
```

### Step 8.4.2: Create Content Selection Script (20 min)
```python
# /Users/d/claude-code/personal/knowledge-activation-system/scripts/populate_review.py
"""
Select high-value content for spaced repetition review.
"""

import asyncio
import httpx

KAS_URL = "http://localhost:8000"

# Selection criteria
HIGH_VALUE_NAMESPACES = ["frameworks", "ai-ml", "infrastructure"]
MIN_CHUNKS = 3  # Content with at least 3 chunks (substantial)


async def get_content_for_review():
    """Get content candidates for review queue."""
    async with httpx.AsyncClient() as client:
        # Get all content
        response = await client.get(f"{KAS_URL}/content", params={"limit": 500})
        content = response.json()

        candidates = []
        for item in content.get("items", []):
            # Filter by criteria
            # (In reality, filter by namespace, quality score, etc.)
            if item.get("chunk_count", 0) >= MIN_CHUNKS:
                candidates.append(item)

        return candidates


async def add_to_review_queue(content_ids: list[str]):
    """Add content to review queue."""
    async with httpx.AsyncClient() as client:
        for content_id in content_ids:
            try:
                response = await client.post(
                    f"{KAS_URL}/review/add",
                    json={"content_id": content_id}
                )
                if response.status_code == 200:
                    print(f"Added: {content_id}")
                elif response.status_code == 409:
                    print(f"Already in queue: {content_id}")
                else:
                    print(f"Failed: {content_id} - {response.text}")
            except Exception as e:
                print(f"Error: {content_id} - {e}")


async def main():
    print("Fetching content for review selection...")
    candidates = await get_content_for_review()
    print(f"Found {len(candidates)} candidates")

    # Select top 50 for initial review queue
    selected = candidates[:50]
    content_ids = [c["id"] for c in selected]

    print(f"\nAdding {len(content_ids)} items to review queue...")
    await add_to_review_queue(content_ids)

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
```

### Step 8.4.3: Create Review CLI (30 min)
```python
# /Users/d/claude-code/personal/knowledge-activation-system/scripts/review_cli.py
"""
CLI for daily spaced repetition review.
"""

import asyncio
import httpx
from datetime import datetime

KAS_URL = "http://localhost:8000"


async def get_due_reviews():
    """Get items due for review."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{KAS_URL}/review/due", params={"limit": 10})
        return response.json()


async def get_content_detail(content_id: str):
    """Get content details."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{KAS_URL}/content/{content_id}")
        return response.json()


async def submit_review(content_id: str, rating: int):
    """Submit review rating."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{KAS_URL}/review/submit",
            json={"content_id": content_id, "rating": rating}
        )
        return response.json()


def print_review_item(item: dict, detail: dict):
    """Display review item."""
    print("\n" + "=" * 60)
    print(f"📚 {detail.get('title', 'Unknown')}")
    print(f"   Type: {detail.get('type', 'unknown')}")
    print(f"   State: {item.get('state', 'new')}")
    print(f"   Reviews: {item.get('review_count', 0)}")
    print("=" * 60)

    # Show summary or first chunk
    summary = detail.get("summary", "")
    if summary:
        print(f"\n{summary[:500]}...")

    print("\n" + "-" * 60)
    print("Rate your recall:")
    print("  1 = Again (didn't remember)")
    print("  2 = Hard (barely remembered)")
    print("  3 = Good (remembered)")
    print("  4 = Easy (effortless)")
    print("  q = Quit review session")


async def review_session():
    """Run interactive review session."""
    print("\n🧠 KAS Daily Review")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    due = await get_due_reviews()
    items = due.get("items", [])

    if not items:
        print("\n✅ No items due for review!")
        return

    print(f"\n📋 {len(items)} items due for review\n")

    reviewed = 0
    for item in items:
        content_id = item.get("content_id")

        try:
            detail = await get_content_detail(content_id)
        except:
            detail = {"title": "Unknown", "summary": ""}

        print_review_item(item, detail)

        while True:
            choice = input("\nYour rating (1-4, q to quit): ").strip().lower()

            if choice == 'q':
                print(f"\n📊 Session complete: {reviewed} items reviewed")
                return

            if choice in ['1', '2', '3', '4']:
                rating = int(choice)
                result = await submit_review(content_id, rating)
                next_review = result.get("next_review", "unknown")
                print(f"✓ Scheduled for: {next_review}")
                reviewed += 1
                break
            else:
                print("Invalid input. Enter 1-4 or q.")

    print(f"\n🎉 All done! Reviewed {reviewed} items.")


async def show_stats():
    """Show review statistics."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{KAS_URL}/review/stats")
        stats = response.json()

    print("\n📊 Review Statistics")
    print("=" * 40)
    print(f"Total in queue:  {stats.get('total', 0)}")
    print(f"Due today:       {stats.get('due', 0)}")
    print(f"New:             {stats.get('new', 0)}")
    print(f"Learning:        {stats.get('learning', 0)}")
    print(f"Review:          {stats.get('review', 0)}")
    print(f"Avg retention:   {stats.get('retention', 0):.1%}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        asyncio.run(show_stats())
    else:
        asyncio.run(review_session())
```

### Step 8.4.4: Create Shell Aliases (10 min)
```bash
cat >> ~/.zshrc << 'EOF'

# KAS Review
alias kas-review='cd /Users/d/claude-code/personal/knowledge-activation-system && uv run python scripts/review_cli.py'
alias kas-review-stats='cd /Users/d/claude-code/personal/knowledge-activation-system && uv run python scripts/review_cli.py stats'
alias kas-review-populate='cd /Users/d/claude-code/personal/knowledge-activation-system && uv run python scripts/populate_review.py'
EOF

source ~/.zshrc
```

### Step 8.4.5: Populate Initial Review Queue (10 min)
```bash
# Add content to review queue
kas-review-populate

# Check stats
kas-review-stats
```

### Step 8.4.6: Test Review Flow (15 min)
```bash
# Start a review session
kas-review
```

### Step 8.4.7: Create Morning Reminder (Optional) (10 min)
```bash
# Add to crontab - morning reminder at 9am
# 0 9 * * * osascript -e 'display notification "Time for knowledge review!" with title "KAS Review"'
```

## 8.5 Testing Checklist

- [ ] Content added to review queue
- [ ] `kas-review` starts interactive session
- [ ] Rating submission updates schedule
- [ ] `kas-review-stats` shows statistics
- [ ] Next review dates are calculated correctly

## 8.6 Acceptance Criteria

**Priority 8 is COMPLETE when:**
1. 20+ items in review queue
2. Daily review workflow works
3. FSRS scheduling calculates correctly
4. Statistics are tracked

## 8.7 Estimated Time: 2-3 hours

---

# Implementation Timeline

## Week 1: Core Integration
| Day | Priority | Task | Hours |
|-----|----------|------|-------|
| 1 | P1 | MCP Server | 3 |
| 1 | P2 | Q&A Validation | 2 |
| 2 | P3 | Automated Sync | 1 |
| 2 | P4 | Fix Sources (start) | 2 |
| 3 | P4 | Fix Sources (complete) | 2 |

**Week 1 Total: ~10 hours**

## Week 2: Stability & Measurement
| Day | Priority | Task | Hours |
|-----|----------|------|-------|
| 1 | P5 | Service Management | 3 |
| 2 | P6 | RAG Evaluation (start) | 3 |
| 3 | P6 | RAG Evaluation (complete) | 2 |

**Week 2 Total: ~8 hours**

## Week 3-4: Experience
| Day | Priority | Task | Hours |
|-----|----------|------|-------|
| 1-3 | P7 | Web Dashboard | 8 |
| 4 | P8 | Spaced Repetition | 3 |

**Week 3-4 Total: ~11 hours**

---

# Success Metrics

| Priority | Metric | Target |
|----------|--------|--------|
| P1 | MCP tools working in Claude Code | 100% |
| P2 | Q&A confidence accuracy | >80% |
| P3 | Automated sync running weekly | Yes |
| P4 | Knowledge coverage | >90% |
| P5 | Uptime | >99% |
| P6 | Context relevance | >70% |
| P7 | Dashboard functional | All pages |
| P8 | Active review items | >20 |

---

# Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| MCP SDK changes | Medium | High | Pin version, test before update |
| AI provider outage | Low | Medium | Fallback to search-only mode |
| Broken URLs increase | High | Low | Regular validation, alternatives |
| PostgreSQL failure | Low | High | Daily backups, health checks |
| Ollama memory issues | Medium | Medium | Monitor, restart on OOM |

---

*Implementation Plan v2.0 - Ready for Execution*
*Total Estimated Effort: 35-45 hours*
*Timeline: 3-4 weeks*
