#!/usr/bin/env python3
"""
Batch content generator using local MLX API.
Generates reference guides and automatically ingests them.

Usage:
    1. Start MLX server: cd ~/claude-code/ai-tools/unified-mlx-app && unified-mlx
    2. Run this script: python scripts/batch_generate_content.py
"""

import asyncio
import subprocess
from pathlib import Path
from datetime import datetime
import json

try:
    from openai import AsyncOpenAI
except ImportError:
    print("❌ OpenAI library not installed. Installing...")
    subprocess.run(["pip", "install", "openai"], check=True)
    from openai import AsyncOpenAI

# Configure to use local MLX server
client = AsyncOpenAI(
    base_url="http://localhost:8080/v1",
    api_key="not-needed"  # Local server doesn't need auth
)

OBSIDIAN_DIR = Path("/Users/d/Obsidian/Knowledge/Notes")
PROJECT_DIR = Path("/Users/d/claude-code/personal/knowledge-activation-system")

# Topics to generate (add more as needed)
TOPICS = [
    # Programming Languages
    {
        "name": "Rust Programming Guide 2026",
        "tags": ["rust", "programming", "systems", "memory-safety"],
        "prompt": """Create a comprehensive guide to Rust programming in 2026 covering:
        - Ownership, borrowing, and lifetimes with detailed examples
        - Async/await and tokio runtime
        - Error handling patterns (Result, Option, anyhow, thiserror)
        - Common patterns and idioms
        - Cargo workspace management
        - Testing and benchmarking
        - Unsafe Rust and FFI
        - Production best practices
        Include practical code examples for each section."""
    },
    {
        "name": "Go Programming Best Practices 2026",
        "tags": ["go", "golang", "backend", "concurrency"],
        "prompt": """Create a comprehensive Go programming guide covering:
        - Goroutines and channels patterns
        - Context and cancellation
        - Error handling and wrapping
        - Interfaces and composition
        - Testing (unit, integration, table-driven)
        - Dependency injection
        - Performance profiling (pprof)
        - Production deployment best practices
        Include code examples and real-world patterns."""
    },

    # DevOps & Infrastructure
    {
        "name": "Kubernetes Production Guide 2026",
        "tags": ["kubernetes", "k8s", "devops", "containers"],
        "prompt": """Create a comprehensive Kubernetes guide for production deployments:
        - Pods, Services, Deployments, StatefulSets
        - ConfigMaps and Secrets management
        - Networking (Ingress, Service Mesh)
        - Storage (PersistentVolumes, StorageClasses)
        - Security (RBAC, Network Policies, Pod Security)
        - Monitoring and logging
        - Auto-scaling (HPA, VPA, Cluster Autoscaler)
        - Helm charts and GitOps (ArgoCD)
        - Multi-cluster management
        Include YAML examples and production patterns."""
    },
    {
        "name": "Terraform Infrastructure as Code 2026",
        "tags": ["terraform", "iac", "devops", "cloud"],
        "prompt": """Create a comprehensive Terraform guide covering:
        - Resources and data sources
        - Modules and composition
        - State management and backends
        - Workspaces and environments
        - Variables and outputs
        - Provisioners and null resources
        - Testing (terratest)
        - Multi-cloud strategies
        - Security best practices
        Include HCL examples for AWS, GCP, and Azure."""
    },

    # Security
    {
        "name": "API Security Best Practices 2026",
        "tags": ["security", "api", "authentication", "authorization"],
        "prompt": """Create a comprehensive API security guide:
        - OWASP API Security Top 10 (2025 update)
        - Authentication (JWT, OAuth2, OIDC)
        - Authorization (RBAC, ABAC)
        - Rate limiting and DDoS protection
        - Input validation and sanitization
        - CORS and CSRF protection
        - API keys and secret management
        - Security headers
        - Logging and monitoring
        Include code examples and implementation patterns."""
    },
    {
        "name": "Docker Security Hardening 2026",
        "tags": ["docker", "security", "containers", "devops"],
        "prompt": """Create a comprehensive Docker security guide:
        - Image scanning and vulnerability detection
        - Minimal base images (distroless, Alpine)
        - Multi-stage builds for security
        - Runtime security (AppArmor, Seccomp)
        - Secrets management
        - Network isolation
        - User namespaces and rootless mode
        - Docker Content Trust
        - Security scanning in CI/CD
        Include Dockerfile examples and best practices."""
    },

    # Databases
    {
        "name": "MongoDB Best Practices 2026",
        "tags": ["mongodb", "database", "nosql", "performance"],
        "prompt": """Create a comprehensive MongoDB guide:
        - Data modeling patterns
        - Indexing strategies and compound indexes
        - Aggregation pipeline optimization
        - Transactions and ACID guarantees
        - Sharding and data distribution
        - Replication and replica sets
        - Performance tuning
        - Backup and disaster recovery
        - Security and authentication
        Include query examples and schema patterns."""
    },
    {
        "name": "Redis Caching Strategies 2026",
        "tags": ["redis", "caching", "performance", "database"],
        "prompt": """Create a comprehensive Redis guide:
        - Data structures (strings, hashes, lists, sets, sorted sets)
        - Caching patterns (cache-aside, write-through, write-behind)
        - Pub/Sub messaging
        - Redis Streams
        - Persistence (RDB, AOF)
        - Clustering and Sentinel
        - Redis Stack (JSON, Search, TimeSeries)
        - Performance optimization
        Include code examples for common patterns."""
    },

    # Frontend Advanced
    {
        "name": "Vue.js 3 Complete Guide 2026",
        "tags": ["vue", "javascript", "frontend", "reactive"],
        "prompt": """Create a comprehensive Vue.js 3 guide:
        - Composition API and script setup
        - Reactivity system (ref, reactive, computed)
        - Components and props
        - Vue Router 4 and navigation
        - State management with Pinia
        - Suspense and async components
        - Performance optimization
        - TypeScript integration
        - Testing (Vitest, Vue Test Utils)
        Include code examples and best practices."""
    },
    {
        "name": "Svelte and SvelteKit Guide 2026",
        "tags": ["svelte", "javascript", "frontend", "sveltekit"],
        "prompt": """Create a comprehensive Svelte/SvelteKit guide:
        - Svelte reactivity and stores
        - Component composition
        - SvelteKit routing and layouts
        - Server-side rendering (SSR)
        - Server-side endpoints
        - Form actions and progressive enhancement
        - Adapters and deployment
        - Performance optimization
        - TypeScript support
        Include code examples and patterns."""
    },

    # Additional Core Topics
    {
        "name": "GraphQL API Development 2026",
        "tags": ["graphql", "api", "backend", "schema"],
        "prompt": """Create a comprehensive GraphQL guide:
        - Schema design and type system
        - Resolvers and data loaders
        - Mutations and subscriptions
        - DataLoader pattern for N+1 prevention
        - Apollo Server setup
        - Authentication and authorization
        - Federation and schema stitching
        - Error handling
        - Performance and caching
        Include schema and resolver examples."""
    },
    {
        "name": "Microservices Architecture Patterns 2026",
        "tags": ["microservices", "architecture", "distributed-systems"],
        "prompt": """Create a comprehensive microservices guide:
        - Service decomposition strategies
        - Communication patterns (sync vs async)
        - API Gateway pattern
        - Service mesh (Istio, Linkerd)
        - Event-driven architecture
        - Saga pattern for distributed transactions
        - Circuit breaker and retry patterns
        - Observability and distributed tracing
        - Data consistency patterns
        Include architecture diagrams and code examples."""
    },
    {
        "name": "CI/CD Pipeline Best Practices 2026",
        "tags": ["cicd", "devops", "automation", "testing"],
        "prompt": """Create a comprehensive CI/CD guide:
        - GitHub Actions workflows
        - GitLab CI pipelines
        - Jenkins declarative pipelines
        - Docker build optimization
        - Testing strategies (unit, integration, E2E)
        - Deployment strategies (blue/green, canary, rolling)
        - Secrets management
        - Security scanning (SAST, DAST)
        - Artifact management
        Include YAML examples for different platforms."""
    },
    {
        "name": "Elasticsearch and Search Optimization 2026",
        "tags": ["elasticsearch", "search", "database", "full-text"],
        "prompt": """Create a comprehensive Elasticsearch guide:
        - Index design and mappings
        - Query DSL and full-text search
        - Aggregations and analytics
        - Analyzers and tokenizers
        - Performance tuning
        - Cluster management
        - Security and authentication
        - Kibana visualization
        - ELK stack integration
        Include query examples and mapping patterns."""
    },
    {
        "name": "WebSocket and Real-time Communication 2026",
        "tags": ["websocket", "realtime", "networking", "sse"],
        "prompt": """Create a comprehensive WebSocket and real-time guide:
        - WebSocket protocol fundamentals
        - Connection lifecycle management
        - Message protocols and formats
        - Authentication and authorization
        - Scaling with Redis pub/sub
        - Load balancing sticky sessions
        - Fallback strategies (polling, SSE)
        - WebRTC for peer-to-peer
        - Socket.io and alternatives
        Include client and server code examples."""
    },
]


async def generate_content(topic: dict) -> str:
    """Generate content using local MLX API."""

    system_prompt = """You are a technical documentation expert. Create comprehensive,
accurate, and practical reference guides with extensive code examples.

Guidelines:
- Use clear section headers (##, ###)
- Include practical code examples with comments
- Add tables for comparisons
- Use bullet points for lists
- Include a "Best Practices Summary" section at the end
- Target length: Very comprehensive (aim for detailed coverage)
- Focus on 2026 current standards and practices
- Include real-world use cases and patterns

Format in clean markdown."""

    user_prompt = topic['prompt']

    print(f"  📝 Generating content...")

    try:
        response = await client.chat.completions.create(
            model="qwen2.5-7b-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=8000,  # Generate comprehensive content
        )

        content = response.choices[0].message.content
        return content

    except Exception as e:
        print(f"  ❌ Error generating content: {e}")
        raise


async def save_to_obsidian(topic: dict, content: str) -> Path:
    """Save generated content to Obsidian with YAML frontmatter."""

    # Create YAML frontmatter
    tags_str = ', '.join(topic['tags'])
    today = datetime.now().strftime('%Y-%m-%d')

    frontmatter = f"""---
type: reference
tags: [{tags_str}]
captured_at: '{today}'
generated_by: local-mlx-qwen2.5
---

# {topic['name']}

{content}

---

## Sources

Generated using local MLX inference with Qwen2.5-7B-Instruct model.
"""

    filepath = OBSIDIAN_DIR / f"{topic['name']}.md"

    # Ensure directory exists
    OBSIDIAN_DIR.mkdir(parents=True, exist_ok=True)

    filepath.write_text(frontmatter, encoding='utf-8')
    print(f"  ✅ Saved: {filepath.name}")

    return filepath


async def run_ingestion():
    """Run the CLI ingestion command."""

    print("\n" + "="*60)
    print("📥 Running database ingestion...")
    print("="*60)

    result = subprocess.run(
        ["python", "cli.py", "ingest", "directory", str(OBSIDIAN_DIR)],
        cwd=str(PROJECT_DIR),
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("✅ Ingestion complete\n")
        # Show relevant output
        for line in result.stdout.split('\n'):
            if any(keyword in line for keyword in ['Ingested', 'Found', 'Total']):
                print(f"  {line}")
    else:
        print(f"❌ Ingestion failed:\n{result.stderr}")


async def check_mlx_server():
    """Check if MLX server is running."""
    try:
        response = await client.chat.completions.create(
            model="qwen2.5-7b-instruct",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=10
        )
        return True
    except Exception as e:
        return False


async def main():
    """Generate all content and ingest."""

    print("="*60)
    print("🚀 Batch Content Generator (Local MLX)")
    print("="*60)

    # Check if MLX server is running
    print("\n🔍 Checking MLX server...")
    if not await check_mlx_server():
        print("❌ MLX server not running!")
        print("\nPlease start it in another terminal:")
        print("  cd ~/claude-code/ai-tools/unified-mlx-app")
        print("  source .venv/bin/activate")
        print("  unified-mlx")
        return

    print("✅ MLX server is running")

    print(f"\n📚 Generating {len(TOPICS)} comprehensive guides...\n")

    generated = []
    failed = []

    for i, topic in enumerate(TOPICS, 1):
        try:
            print(f"[{i}/{len(TOPICS)}] {topic['name']}")

            # Generate content
            content = await generate_content(topic)

            # Save to Obsidian
            filepath = await save_to_obsidian(topic, content)
            generated.append(filepath)

            # Brief pause to avoid overwhelming the server
            await asyncio.sleep(1)

        except Exception as e:
            print(f"  ❌ Failed: {e}")
            failed.append(topic['name'])
            continue

    # Run ingestion after all files created
    if generated:
        await run_ingestion()

    # Final summary
    print("\n" + "="*60)
    print("📊 Generation Summary")
    print("="*60)
    print(f"✅ Successfully generated: {len(generated)} guides")
    if failed:
        print(f"❌ Failed: {len(failed)} guides")
        for name in failed:
            print(f"   - {name}")

    print("\n✅ Batch generation complete!")


if __name__ == "__main__":
    asyncio.run(main())
