# Local AI Automation for Knowledge Base Growth

**Goal:** Reach 1,000 items without using Claude Code tokens

**Current:** 572/1,000 (need 428 more items)

---

## Available Local AI Tools

### 1. Unified MLX App (BEST OPTION)
**Location:** `/Users/d/claude-code/ai-tools/unified-mlx-app/`
**Model:** Qwen2.5-7B-Instruct (4-bit quantized)
**API:** OpenAI-compatible at `http://localhost:8080/v1`
**Advantages:**
- Already installed and configured
- Fast on Apple Silicon (M4 Pro)
- Free unlimited usage
- OpenAI-compatible API (easy integration)

**Start server:**
```bash
cd /Users/d/claude-code/ai-tools/unified-mlx-app
source .venv/bin/activate
unified-mlx
```

### 2. Ollama
**Location:** `/opt/homebrew/bin/ollama`
**Advantages:**
- Easy model management
- Multiple model options
- CLI-friendly

**Start and use:**
```bash
ollama serve  # Start server
ollama pull qwen2.5:7b  # Download model
ollama run qwen2.5:7b "Your prompt"
```

---

## Recommended Automation Strategies

### Strategy 1: Batch Content Generator Script (RECOMMENDED)

Create a Python script that uses your local MLX API to generate content in batches.

**File:** `scripts/batch_generate_content.py`

```python
#!/usr/bin/env python3
"""
Batch content generator using local MLX API.
Generates reference guides and automatically ingests them.
"""

import asyncio
from pathlib import Path
from openai import AsyncOpenAI
import json

# Configure to use local MLX server
client = AsyncOpenAI(
    base_url="http://localhost:8080/v1",
    api_key="not-needed"  # Local server doesn't need auth
)

OBSIDIAN_DIR = Path("/Users/d/Obsidian/Knowledge/Notes")

TOPICS = [
    # Programming Languages
    {"name": "Rust Programming Guide 2026", "tags": ["rust", "programming", "systems"],
     "prompt": "Create a comprehensive guide to Rust programming covering ownership, borrowing, lifetimes, async/await, error handling, and common patterns. Include code examples."},

    {"name": "Go Programming Best Practices 2026", "tags": ["go", "golang", "backend"],
     "prompt": "Create a comprehensive guide to Go programming covering goroutines, channels, error handling, interfaces, testing, and production best practices. Include code examples."},

    # DevOps & Infrastructure
    {"name": "Kubernetes Production Guide 2026", "tags": ["kubernetes", "k8s", "devops"],
     "prompt": "Create a comprehensive Kubernetes guide covering pods, services, deployments, statefulsets, configmaps, secrets, networking, storage, and production best practices."},

    {"name": "Terraform Infrastructure as Code 2026", "tags": ["terraform", "iac", "devops"],
     "prompt": "Create a comprehensive Terraform guide covering resources, modules, state management, workspaces, best practices, and multi-cloud deployment."},

    # Security
    {"name": "API Security Best Practices 2026", "tags": ["security", "api", "authentication"],
     "prompt": "Create a comprehensive API security guide covering authentication, authorization, rate limiting, input validation, OWASP API Security Top 10, JWT, OAuth2."},

    {"name": "Docker Security Hardening 2026", "tags": ["docker", "security", "containers"],
     "prompt": "Create a comprehensive Docker security guide covering image scanning, runtime security, secrets management, network isolation, and production best practices."},

    # Databases
    {"name": "MongoDB Best Practices 2026", "tags": ["mongodb", "database", "nosql"],
     "prompt": "Create a comprehensive MongoDB guide covering data modeling, indexing, aggregation pipeline, transactions, sharding, replication, and performance optimization."},

    {"name": "Redis Caching Strategies 2026", "tags": ["redis", "caching", "performance"],
     "prompt": "Create a comprehensive Redis guide covering data structures, caching patterns, pub/sub, streams, persistence, clustering, and performance optimization."},

    # Frontend Advanced
    {"name": "Vue.js 3 Complete Guide 2026", "tags": ["vue", "javascript", "frontend"],
     "prompt": "Create a comprehensive Vue.js 3 guide covering composition API, reactivity, components, routing, state management (Pinia), performance optimization."},

    {"name": "Svelte and SvelteKit Guide 2026", "tags": ["svelte", "javascript", "frontend"],
     "prompt": "Create a comprehensive Svelte/SvelteKit guide covering reactivity, components, stores, routing, server-side rendering, and performance."},

    # Additional Topics
    {"name": "GraphQL API Development 2026", "tags": ["graphql", "api", "backend"],
     "prompt": "Create a comprehensive GraphQL guide covering schema design, resolvers, mutations, subscriptions, DataLoader, federation, and best practices."},

    {"name": "Microservices Architecture Patterns 2026", "tags": ["microservices", "architecture", "distributed-systems"],
     "prompt": "Create a comprehensive microservices guide covering service decomposition, communication patterns, API gateway, service mesh, observability, and resilience."},

    {"name": "CI/CD Pipeline Best Practices 2026", "tags": ["cicd", "devops", "automation"],
     "prompt": "Create a comprehensive CI/CD guide covering GitHub Actions, GitLab CI, Jenkins, Docker builds, testing strategies, deployment strategies, and security."},

    {"name": "Elasticsearch and Search Optimization 2026", "tags": ["elasticsearch", "search", "database"],
     "prompt": "Create a comprehensive Elasticsearch guide covering indexing, querying, aggregations, analyzers, performance tuning, cluster management."},

    {"name": "WebSocket and Real-time Communication 2026", "tags": ["websocket", "realtime", "networking"],
     "prompt": "Create a comprehensive WebSocket guide covering connection management, message protocols, scaling, authentication, fallback strategies, and alternatives like SSE."},
]

async def generate_content(topic: dict) -> str:
    """Generate content using local MLX API."""

    system_prompt = """You are a technical documentation expert. Create comprehensive,
    accurate reference guides with code examples, best practices, and current 2026 standards.

    Format with markdown including:
    - Clear section headers
    - Code examples with syntax highlighting
    - Tables for comparisons
    - Bullet points for lists
    - Best practices summary

    Target length: 40-80KB (very comprehensive).
    """

    user_prompt = f"{topic['prompt']}\n\nInclude practical code examples and real-world use cases."

    print(f"Generating: {topic['name']}...")

    response = await client.chat.completions.create(
        model="qwen2.5-7b-instruct",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
        max_tokens=8000,  # Generate long content
    )

    content = response.choices[0].message.content
    return content

async def save_to_obsidian(topic: dict, content: str):
    """Save generated content to Obsidian with YAML frontmatter."""

    # Create YAML frontmatter
    frontmatter = f"""---
type: reference
tags: {json.dumps(topic['tags'])}
captured_at: '2026-01-11'
generated_by: local-mlx
---

# {topic['name']}

{content}
"""

    filepath = OBSIDIAN_DIR / f"{topic['name']}.md"
    filepath.write_text(frontmatter)
    print(f"✅ Saved: {filepath}")

async def run_ingestion():
    """Run the CLI ingestion command."""
    import subprocess

    print("\n📥 Running ingestion...")
    result = subprocess.run(
        ["python", "cli.py", "ingest", "directory", str(OBSIDIAN_DIR)],
        cwd="/Users/d/claude-code/personal/knowledge-activation-system",
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("✅ Ingestion complete")
        # Extract stats
        for line in result.stdout.split('\n'):
            if 'Ingested' in line:
                print(f"  {line}")
    else:
        print(f"❌ Ingestion failed: {result.stderr}")

async def main():
    """Generate all content and ingest."""

    print(f"🚀 Starting batch generation of {len(TOPICS)} topics\n")

    for i, topic in enumerate(TOPICS, 1):
        try:
            print(f"\n[{i}/{len(TOPICS)}] {topic['name']}")

            # Generate content
            content = await generate_content(topic)

            # Save to Obsidian
            await save_to_obsidian(topic, content)

            # Brief pause to avoid overwhelming the server
            await asyncio.sleep(2)

        except Exception as e:
            print(f"❌ Failed: {e}")
            continue

    # Run ingestion after all files created
    await run_ingestion()

    print("\n✅ Batch generation complete!")
    print(f"Generated {len(TOPICS)} reference guides")

if __name__ == "__main__":
    asyncio.run(main())
```

**Usage:**
```bash
# 1. Start MLX server (in separate terminal)
cd /Users/d/claude-code/ai-tools/unified-mlx-app
source .venv/bin/activate
unified-mlx

# 2. Run batch generator (in project terminal)
cd /Users/d/claude-code/personal/knowledge-activation-system
source .venv/bin/activate
python scripts/batch_generate_content.py
```

**Expected output:** 15 new comprehensive guides = 15 database items

---

### Strategy 2: Ollama CLI Loop (SIMPLER)

Simpler approach using Ollama CLI directly.

**File:** `scripts/ollama_generate.sh`

```bash
#!/bin/bash

# Start ollama if not running
ollama serve &
sleep 5

# Pull model
ollama pull qwen2.5:7b

OBSIDIAN_DIR="/Users/d/Obsidian/Knowledge/Notes"

# Array of topics
topics=(
    "Rust Programming Guide 2026"
    "Go Programming Best Practices 2026"
    "Kubernetes Production Guide 2026"
    "Terraform Infrastructure as Code 2026"
    "API Security Best Practices 2026"
)

for topic in "${topics[@]}"; do
    echo "Generating: $topic"

    # Generate content with Ollama
    ollama run qwen2.5:7b "Create a comprehensive technical guide about '$topic'. Include code examples, best practices, and current 2026 standards. Format in markdown with clear sections. Make it very detailed (40-80KB)." > "/tmp/${topic}.md"

    # Add YAML frontmatter
    cat > "$OBSIDIAN_DIR/${topic}.md" << EOF
---
type: reference
tags: [programming, reference, 2026]
captured_at: '2026-01-11'
generated_by: ollama
---

$(cat "/tmp/${topic}.md")
EOF

    echo "✅ Saved: $topic"
    sleep 5  # Rate limiting
done

# Run ingestion
cd /Users/d/claude-code/personal/knowledge-activation-system
source .venv/bin/activate
python cli.py ingest directory "$OBSIDIAN_DIR"

echo "✅ Complete!"
```

**Usage:**
```bash
chmod +x scripts/ollama_generate.sh
./scripts/ollama_generate.sh
```

---

### Strategy 3: Hybrid Approach (FASTEST TO 1000)

Combine multiple sources:

1. **Local LLM generation** (15-20 items) - Use MLX script above
2. **Chrome bookmarks export** (200-300 items) - Manual HTML export
3. **YouTube transcripts** (50-100 items) - When rate limit resets
4. **Existing PDFs** (10-50 items) - Any technical PDFs in ~/Downloads

**Combined script:** `scripts/hybrid_ingest.sh`

```bash
#!/bin/bash

OBSIDIAN_DIR="/Users/d/Obsidian/Knowledge/Notes"
PROJECT_DIR="/Users/d/claude-code/personal/knowledge-activation-system"

cd "$PROJECT_DIR"
source .venv/bin/activate

echo "🚀 Hybrid Ingestion Strategy"
echo "============================"

# 1. Chrome bookmarks (if exists)
if [ -f ~/Downloads/bookmarks.html ]; then
    echo "📚 Ingesting Chrome bookmarks..."
    python cli.py ingest bookmarks ~/Downloads/bookmarks.html
fi

# 2. PDFs from Downloads
echo "📄 Ingesting PDFs from Downloads..."
find ~/Downloads -name "*.pdf" -type f | while read pdf; do
    python cli.py ingest pdf "$pdf"
done

# 3. Any new markdown files
echo "📝 Ingesting markdown files..."
python cli.py ingest directory "$OBSIDIAN_DIR"

# 4. Check stats
echo ""
echo "📊 Current Stats:"
python cli.py stats

echo "✅ Hybrid ingestion complete!"
```

---

## Recommended Next Steps

### Immediate (5 minutes):
1. **Export Chrome bookmarks**
   - Chrome → Bookmarks → Bookmark Manager → ⋮ → Export bookmarks
   - Save to `~/Downloads/bookmarks.html`
   - Run: `python cli.py ingest bookmarks ~/Downloads/bookmarks.html`
   - **Expected:** +200-300 items instantly

### Short-term (30 minutes):
2. **Run batch MLX generator**
   - Start MLX server
   - Run `batch_generate_content.py` script above
   - **Expected:** +15 items (high-quality reference guides)

### Medium-term (1 hour):
3. **Create more topic lists**
   - Expand TOPICS array in script to 50-100 topics
   - Run overnight
   - **Expected:** +50-100 items

---

## Cost Comparison

| Method | Time | Cost | Items | Quality |
|--------|------|------|-------|---------|
| **Claude Code** | 2 hours | High token usage | 87 items | Excellent |
| **Local MLX** | 1 hour | Free (electricity) | 50+ items | Very good |
| **Ollama** | 1 hour | Free (electricity) | 50+ items | Very good |
| **Bookmarks** | 5 min | Free | 200-300 items | Varies |
| **Hybrid** | 2 hours | Free | 300-400 items | Mixed |

---

## Automation Schedule

Set up cron jobs for continuous growth:

```bash
# Add to crontab (crontab -e)

# Generate 5 new guides daily at 2 AM (when computer idle)
0 2 * * * cd /Users/d/claude-code/personal/knowledge-activation-system && source .venv/bin/activate && python scripts/batch_generate_content.py

# Ingest any new files at 3 AM
0 3 * * * cd /Users/d/claude-code/personal/knowledge-activation-system && source .venv/bin/activate && python cli.py ingest directory /Users/d/Obsidian/Knowledge/Notes
```

**Result:** 5 new items/day × 30 days = 150 items/month automatically

---

## Monitoring

Check progress daily:

```bash
cd /Users/d/claude-code/personal/knowledge-activation-system
source .venv/bin/activate
python cli.py stats
```

---

## Summary

**Best approach to reach 1,000:**

1. **Today:** Export Chrome bookmarks → +250 items (572 → 822)
2. **Tonight:** Run MLX batch generator (15 topics) → +15 items (822 → 837)
3. **This week:** Expand topic list to 50 topics, run MLX → +50 items (837 → 887)
4. **Next week:** YouTube transcripts when rate limit resets → +50 items (887 → 937)
5. **Ongoing:** Automated cron job generating 5/day → +60 items/month

**Result:** Reach 1,000 items within 2-3 weeks, completely free!
