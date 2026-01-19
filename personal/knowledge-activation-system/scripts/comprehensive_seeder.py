#!/usr/bin/env python3
"""
Comprehensive Knowledge Seeder - Expands KAS content to 5000+ documents.

Uses local MLX API to generate diverse technical content across many categories.

Usage:
    # Generate all content (requires MLX server running)
    python scripts/comprehensive_seeder.py --generate

    # Ingest generated content into KAS
    python scripts/comprehensive_seeder.py --ingest

    # Both (generate then ingest)
    python scripts/comprehensive_seeder.py --all

    # List categories
    python scripts/comprehensive_seeder.py --list
"""

import asyncio
import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from itertools import product

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from openai import AsyncOpenAI
except ImportError:
    print("Installing openai...")
    subprocess.run(["pip", "install", "openai"], check=True)
    from openai import AsyncOpenAI

# Configuration
MLX_URL = "http://localhost:8080/v1"
OBSIDIAN_DIR = Path("/Users/d/Obsidian/Knowledge")
PROJECT_DIR = Path(__file__).parent.parent

client = AsyncOpenAI(base_url=MLX_URL, api_key="not-needed")


# =============================================================================
# Topic Categories - Comprehensive coverage for 5000+ documents
# =============================================================================

CATEGORIES = {
    "programming-languages": {
        "namespace": "languages",
        "topics": [
            ("Python Advanced", ["python", "advanced"], "async/await, metaclasses, decorators, type hints, context managers"),
            ("Python Data Science", ["python", "data-science"], "pandas, numpy, scikit-learn, data manipulation"),
            ("Python Web Development", ["python", "web"], "FastAPI, Django, Flask patterns and best practices"),
            ("JavaScript Modern", ["javascript", "es6+"], "ES2024 features, modules, async patterns"),
            ("TypeScript Advanced", ["typescript", "types"], "generics, utility types, type guards, declaration files"),
            ("Rust Systems", ["rust", "systems"], "ownership, borrowing, unsafe, FFI, async"),
            ("Go Concurrency", ["go", "concurrency"], "goroutines, channels, context, error handling"),
            ("Java Spring", ["java", "spring"], "Spring Boot, dependency injection, JPA, security"),
            ("C++ Modern", ["cpp", "modern"], "C++20/23 features, smart pointers, RAII, templates"),
            ("Kotlin Android", ["kotlin", "android"], "coroutines, flows, Jetpack Compose"),
            ("Swift iOS", ["swift", "ios"], "SwiftUI, Combine, async/await, Core Data"),
            ("Ruby Rails", ["ruby", "rails"], "Rails 7+, Hotwire, Active Record patterns"),
            ("PHP Laravel", ["php", "laravel"], "Laravel 11, Eloquent, queues, testing"),
            ("Elixir Phoenix", ["elixir", "phoenix"], "OTP, LiveView, Ecto, distributed systems"),
            ("Scala Functional", ["scala", "functional"], "FP patterns, Cats Effect, ZIO"),
        ]
    },
    "frontend-frameworks": {
        "namespace": "frontend",
        "topics": [
            ("React Hooks", ["react", "hooks"], "useState, useEffect, useContext, custom hooks"),
            ("React Performance", ["react", "performance"], "memo, useMemo, useCallback, code splitting"),
            ("React Server Components", ["react", "rsc"], "Next.js App Router, streaming, suspense"),
            ("Vue 3 Composition", ["vue", "composition"], "ref, reactive, computed, watch, provide/inject"),
            ("Vue Pinia", ["vue", "pinia"], "stores, actions, plugins, devtools"),
            ("Svelte Reactivity", ["svelte", "reactive"], "stores, derived, two-way binding"),
            ("SvelteKit Routing", ["sveltekit", "routing"], "layouts, load functions, form actions"),
            ("Angular Signals", ["angular", "signals"], "signals, computed, effect, RxJS interop"),
            ("Angular Architecture", ["angular", "architecture"], "modules, services, routing, guards"),
            ("Solid.js Primitives", ["solid", "reactive"], "createSignal, createMemo, createEffect"),
            ("Astro Islands", ["astro", "islands"], "partial hydration, content collections"),
            ("Qwik Resumability", ["qwik", "resumability"], "lazy loading, prefetching, optimization"),
            ("htmx HATEOAS", ["htmx", "hateoas"], "progressive enhancement, server-driven UI"),
            ("Alpine.js Directives", ["alpine", "directives"], "x-data, x-bind, x-on, x-model"),
            ("Remix Loaders", ["remix", "loaders"], "data loading, mutations, error handling"),
        ]
    },
    "backend-frameworks": {
        "namespace": "backend",
        "topics": [
            ("FastAPI Patterns", ["fastapi", "patterns"], "dependency injection, middleware, background tasks"),
            ("Django REST", ["django", "rest"], "DRF, serializers, viewsets, authentication"),
            ("Express Middleware", ["express", "middleware"], "routing, error handling, security"),
            ("NestJS Architecture", ["nestjs", "architecture"], "modules, providers, guards, interceptors"),
            ("Spring Boot Microservices", ["spring", "microservices"], "cloud, gateway, config server"),
            ("Rails API Mode", ["rails", "api"], "serializers, versioning, rate limiting"),
            ("Phoenix LiveView", ["phoenix", "liveview"], "real-time UI, channels, presence"),
            ("Gin Framework", ["gin", "go"], "routing, middleware, validation, binding"),
            ("Fiber HTTP", ["fiber", "go"], "fast routing, middleware, websockets"),
            ("Actix Web", ["actix", "rust"], "extractors, middleware, state management"),
            ("Axum Tower", ["axum", "rust"], "routing, layers, state, error handling"),
            ("Hono Edge", ["hono", "edge"], "workers, middleware, adapters"),
            ("Elysia Bun", ["elysia", "bun"], "type-safe routing, plugins, validation"),
            ("tRPC End-to-End", ["trpc", "typescript"], "type inference, procedures, adapters"),
            ("GraphQL Yoga", ["graphql", "yoga"], "schema, resolvers, subscriptions"),
        ]
    },
    "databases": {
        "namespace": "databases",
        "topics": [
            ("PostgreSQL Advanced", ["postgresql", "advanced"], "CTEs, window functions, JSONB, extensions"),
            ("PostgreSQL Performance", ["postgresql", "performance"], "indexing, query plans, partitioning"),
            ("MySQL Optimization", ["mysql", "optimization"], "indexes, query optimization, replication"),
            ("MongoDB Aggregation", ["mongodb", "aggregation"], "pipeline, operators, optimization"),
            ("Redis Patterns", ["redis", "patterns"], "caching, pub/sub, streams, data structures"),
            ("SQLite Embedded", ["sqlite", "embedded"], "WAL, FTS5, JSON1, performance"),
            ("Cassandra Distributed", ["cassandra", "distributed"], "partitioning, consistency, CQL"),
            ("DynamoDB Design", ["dynamodb", "design"], "single table, GSI, transactions"),
            ("Neo4j Graph", ["neo4j", "graph"], "Cypher, modeling, algorithms"),
            ("Elasticsearch Search", ["elasticsearch", "search"], "mapping, queries, aggregations"),
            ("ClickHouse Analytics", ["clickhouse", "analytics"], "columnar, MergeTree, materialized views"),
            ("TimescaleDB Time-Series", ["timescaledb", "timeseries"], "hypertables, compression, continuous aggregates"),
            ("CockroachDB Distributed SQL", ["cockroachdb", "distributed"], "distributed transactions, geo-partitioning"),
            ("Supabase Realtime", ["supabase", "realtime"], "row level security, functions, triggers"),
            ("PlanetScale Serverless", ["planetscale", "serverless"], "branching, deploy requests, vitess"),
        ]
    },
    "devops": {
        "namespace": "devops",
        "topics": [
            ("Docker Multi-stage", ["docker", "builds"], "optimization, layers, caching"),
            ("Docker Compose", ["docker", "compose"], "services, networks, volumes, secrets"),
            ("Kubernetes Core", ["kubernetes", "core"], "pods, deployments, services, configmaps"),
            ("Kubernetes Networking", ["kubernetes", "networking"], "ingress, service mesh, network policies"),
            ("Helm Charts", ["helm", "charts"], "templates, values, hooks, dependencies"),
            ("ArgoCD GitOps", ["argocd", "gitops"], "sync, health, rollback, multi-cluster"),
            ("Terraform Modules", ["terraform", "modules"], "composition, state, workspaces"),
            ("Ansible Automation", ["ansible", "automation"], "playbooks, roles, inventory, vault"),
            ("GitHub Actions", ["github", "actions"], "workflows, reusable, matrix, secrets"),
            ("GitLab CI", ["gitlab", "ci"], "pipelines, stages, artifacts, cache"),
            ("Jenkins Pipelines", ["jenkins", "pipelines"], "declarative, shared libraries, agents"),
            ("Prometheus Monitoring", ["prometheus", "monitoring"], "metrics, alerting, PromQL"),
            ("Grafana Dashboards", ["grafana", "dashboards"], "panels, variables, alerting"),
            ("Datadog APM", ["datadog", "apm"], "traces, metrics, logs, RUM"),
            ("AWS CDK", ["aws", "cdk"], "constructs, stacks, aspects, testing"),
        ]
    },
    "cloud": {
        "namespace": "cloud",
        "topics": [
            ("AWS Lambda", ["aws", "lambda"], "triggers, layers, cold starts, optimization"),
            ("AWS ECS/EKS", ["aws", "containers"], "task definitions, services, Fargate"),
            ("AWS DynamoDB", ["aws", "dynamodb"], "single table design, streams, transactions"),
            ("AWS S3", ["aws", "s3"], "lifecycle, replication, presigned URLs"),
            ("GCP Cloud Run", ["gcp", "cloudrun"], "containers, autoscaling, traffic splitting"),
            ("GCP BigQuery", ["gcp", "bigquery"], "SQL, streaming, ML, partitioning"),
            ("Azure Functions", ["azure", "functions"], "bindings, durable functions, deployment"),
            ("Azure AKS", ["azure", "aks"], "node pools, KEDA, workload identity"),
            ("Cloudflare Workers", ["cloudflare", "workers"], "KV, Durable Objects, R2"),
            ("Vercel Edge", ["vercel", "edge"], "middleware, ISR, edge functions"),
            ("Fly.io Global", ["flyio", "global"], "machines, volumes, postgres"),
            ("Railway Deployment", ["railway", "deployment"], "nixpacks, volumes, databases"),
            ("Render Services", ["render", "services"], "blueprints, preview environments"),
            ("DigitalOcean App Platform", ["digitalocean", "apps"], "components, jobs, databases"),
            ("Heroku Modern", ["heroku", "modern"], "dynos, addons, pipelines"),
        ]
    },
    "security": {
        "namespace": "security",
        "topics": [
            ("OWASP Top 10", ["owasp", "security"], "injection, XSS, CSRF, broken auth"),
            ("API Security", ["api", "security"], "authentication, authorization, rate limiting"),
            ("JWT Best Practices", ["jwt", "security"], "signing, validation, rotation, storage"),
            ("OAuth2 Flows", ["oauth", "authentication"], "authorization code, PKCE, refresh tokens"),
            ("Zero Trust", ["zerotrust", "security"], "identity, microsegmentation, least privilege"),
            ("Secrets Management", ["secrets", "security"], "Vault, AWS Secrets, rotation"),
            ("Container Security", ["container", "security"], "scanning, runtime, policies"),
            ("Supply Chain Security", ["supplychain", "security"], "SBOM, signing, provenance"),
            ("Penetration Testing", ["pentest", "security"], "methodology, tools, reporting"),
            ("Security Headers", ["headers", "security"], "CSP, HSTS, CORS, X-Frame"),
            ("Encryption at Rest", ["encryption", "data"], "AES, key management, HSM"),
            ("TLS/mTLS", ["tls", "security"], "certificates, chains, mutual auth"),
            ("WAF Configuration", ["waf", "security"], "rules, rate limiting, bot protection"),
            ("SAST/DAST", ["sast", "security"], "static analysis, dynamic testing, CI integration"),
            ("Compliance", ["compliance", "security"], "SOC2, GDPR, HIPAA, PCI-DSS"),
        ]
    },
    "ai-ml": {
        "namespace": "ai-ml",
        "topics": [
            ("LLM Fine-tuning", ["llm", "finetuning"], "LoRA, QLoRA, PEFT, dataset preparation"),
            ("RAG Systems", ["rag", "ai"], "chunking, retrieval, reranking, generation"),
            ("Vector Databases", ["vector", "ai"], "embeddings, indexing, similarity search"),
            ("Prompt Engineering", ["prompts", "ai"], "techniques, chain-of-thought, few-shot"),
            ("LangChain", ["langchain", "ai"], "chains, agents, tools, memory"),
            ("LlamaIndex", ["llamaindex", "ai"], "indexes, query engines, retrievers"),
            ("Hugging Face", ["huggingface", "ai"], "transformers, datasets, spaces"),
            ("MLflow", ["mlflow", "mlops"], "tracking, registry, deployment"),
            ("PyTorch Training", ["pytorch", "training"], "DataLoader, optimizers, distributed"),
            ("TensorFlow Serving", ["tensorflow", "serving"], "SavedModel, TF Serving, optimization"),
            ("Model Quantization", ["quantization", "ai"], "INT8, FP16, GPTQ, GGUF"),
            ("AI Agents", ["agents", "ai"], "planning, tools, memory, orchestration"),
            ("Computer Vision", ["cv", "ai"], "object detection, segmentation, OCR"),
            ("NLP Pipelines", ["nlp", "ai"], "tokenization, NER, classification"),
            ("Speech Recognition", ["speech", "ai"], "Whisper, transcription, diarization"),
        ]
    },
    "testing": {
        "namespace": "testing",
        "topics": [
            ("Jest Patterns", ["jest", "testing"], "mocking, snapshots, async testing"),
            ("Vitest Modern", ["vitest", "testing"], "mocking, coverage, workspace"),
            ("Pytest Advanced", ["pytest", "testing"], "fixtures, parametrize, plugins"),
            ("Playwright E2E", ["playwright", "e2e"], "locators, assertions, trace viewer"),
            ("Cypress Component", ["cypress", "testing"], "component testing, custom commands"),
            ("Testing Library", ["testing-library", "testing"], "queries, user events, accessibility"),
            ("MSW Mocking", ["msw", "mocking"], "handlers, scenarios, testing"),
            ("Storybook Testing", ["storybook", "testing"], "interaction tests, visual regression"),
            ("Contract Testing", ["contract", "testing"], "Pact, consumer-driven"),
            ("Load Testing", ["load", "testing"], "k6, Locust, scenarios"),
            ("Chaos Engineering", ["chaos", "testing"], "fault injection, resilience"),
            ("Mutation Testing", ["mutation", "testing"], "mutmut, Stryker, coverage"),
            ("API Testing", ["api", "testing"], "Postman, REST-assured, schema validation"),
            ("Security Testing", ["security", "testing"], "OWASP ZAP, Burp Suite automation"),
            ("Accessibility Testing", ["a11y", "testing"], "axe-core, WCAG, screen readers"),
        ]
    },
    "architecture": {
        "namespace": "architecture",
        "topics": [
            ("Clean Architecture", ["clean", "architecture"], "layers, dependencies, use cases"),
            ("Domain-Driven Design", ["ddd", "architecture"], "aggregates, entities, value objects"),
            ("Event Sourcing", ["eventsourcing", "architecture"], "events, projections, snapshots"),
            ("CQRS Pattern", ["cqrs", "architecture"], "commands, queries, separation"),
            ("Microservices Patterns", ["microservices", "patterns"], "decomposition, communication, data"),
            ("API Gateway", ["gateway", "architecture"], "routing, rate limiting, auth"),
            ("Service Mesh", ["servicemesh", "architecture"], "sidecar, observability, security"),
            ("Event-Driven Architecture", ["eventdriven", "architecture"], "pub/sub, event bus, choreography"),
            ("Saga Pattern", ["saga", "architecture"], "orchestration, choreography, compensation"),
            ("Circuit Breaker", ["circuitbreaker", "architecture"], "states, fallback, monitoring"),
            ("Strangler Fig", ["strangler", "migration"], "incremental migration, routing"),
            ("Backends for Frontends", ["bff", "architecture"], "aggregation, optimization"),
            ("Data Mesh", ["datamesh", "architecture"], "domains, products, self-serve"),
            ("Cell-Based Architecture", ["cell", "architecture"], "isolation, blast radius, routing"),
            ("Edge Computing", ["edge", "architecture"], "latency, distribution, sync"),
        ]
    },
}


def generate_topic_list():
    """Generate full list of topics from categories."""
    topics = []
    for category, data in CATEGORIES.items():
        for name, tags, description in data["topics"]:
            topics.append({
                "name": f"{name} Guide 2026",
                "category": category,
                "namespace": data["namespace"],
                "tags": tags + [category],
                "description": description,
                "prompt": f"""Create a comprehensive technical guide about {name} covering:

Key areas: {description}

Include:
- Detailed explanations with practical examples
- Code snippets with comments
- Best practices and common pitfalls
- Performance considerations
- Real-world use cases
- Comparison with alternatives where relevant
- 2026 current standards and practices

Format in clean markdown with headers, code blocks, and bullet points."""
            })
    return topics


async def generate_content(topic: dict, model: str = "qwen2.5-7b-instruct") -> str:
    """Generate content using local MLX API."""
    system_prompt = """You are a technical documentation expert. Create comprehensive,
accurate, and practical reference guides with extensive code examples.

Guidelines:
- Use clear section headers (##, ###)
- Include practical code examples with comments
- Add tables for comparisons where useful
- Use bullet points for lists
- Include a "Best Practices Summary" section at the end
- Target length: Comprehensive coverage (2000-4000 words)
- Focus on current 2026 standards and practices
- Include real-world use cases and patterns

Format in clean markdown."""

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": topic["prompt"]}
        ],
        temperature=0.7,
        max_tokens=6000,
    )
    return response.choices[0].message.content


async def save_content(topic: dict, content: str) -> Path:
    """Save generated content to Obsidian with YAML frontmatter."""
    tags_str = ", ".join(topic["tags"])
    today = datetime.now().strftime("%Y-%m-%d")

    frontmatter = f"""---
type: reference
tags: [{tags_str}]
namespace: {topic["namespace"]}
captured_at: '{today}'
generated_by: local-mlx-comprehensive-seeder
---

# {topic["name"]}

{content}

---

*Generated by Comprehensive Knowledge Seeder on {today}*
"""

    # Create category directory
    category_dir = OBSIDIAN_DIR / "Notes" / topic["category"].replace("-", "_")
    category_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_name = topic["name"].replace("/", "-").replace(":", "-")
    filepath = category_dir / f"{safe_name}.md"

    filepath.write_text(frontmatter, encoding="utf-8")
    return filepath


async def check_mlx_server():
    """Check if MLX server is running."""
    try:
        await client.chat.completions.create(
            model="qwen2.5-7b-instruct",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=10
        )
        return True
    except Exception:
        return False


async def generate_all(batch_size: int = 5, start_from: int = 0):
    """Generate all content in batches."""
    topics = generate_topic_list()

    print(f"📚 Total topics: {len(topics)}")
    print(f"🚀 Starting from topic {start_from}")

    if not await check_mlx_server():
        print("❌ MLX server not running!")
        print("\nStart it with:")
        print("  cd ~/claude-code/ai-tools/unified-mlx-app && unified-mlx")
        return

    generated = []
    failed = []

    for i, topic in enumerate(topics[start_from:], start=start_from):
        try:
            print(f"\n[{i+1}/{len(topics)}] {topic['name']}")
            print(f"    Category: {topic['category']}")

            content = await generate_content(topic)
            filepath = await save_content(topic, content)
            generated.append(filepath)
            print(f"    ✅ Saved: {filepath.name}")

            # Batch pause
            if (i + 1) % batch_size == 0:
                print(f"\n⏸️  Completed batch of {batch_size}. Pausing...")
                await asyncio.sleep(2)

        except Exception as e:
            print(f"    ❌ Failed: {e}")
            failed.append(topic["name"])
            continue

    print(f"\n{'='*60}")
    print(f"✅ Generated: {len(generated)} documents")
    print(f"❌ Failed: {len(failed)} documents")


async def run_ingestion():
    """Run the CLI ingestion command."""
    print("\n📥 Running database ingestion...")

    notes_dir = OBSIDIAN_DIR / "Notes"
    if not notes_dir.exists():
        print(f"❌ Notes directory not found: {notes_dir}")
        return

    result = subprocess.run(
        ["python", "cli.py", "ingest", "directory", str(notes_dir)],
        cwd=str(PROJECT_DIR),
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("✅ Ingestion complete")
        for line in result.stdout.split("\n"):
            if any(kw in line for kw in ["Ingested", "Found", "Total", "chunks"]):
                print(f"  {line}")
    else:
        print(f"❌ Ingestion failed: {result.stderr}")


def list_categories():
    """List all available categories and topics."""
    topics = generate_topic_list()
    print(f"\n📚 Knowledge Seeder Categories ({len(topics)} total topics)\n")

    for category, data in CATEGORIES.items():
        print(f"\n{category.upper()} (namespace: {data['namespace']})")
        print("-" * 50)
        for name, tags, desc in data["topics"]:
            print(f"  • {name}")
            print(f"    Tags: {', '.join(tags)}")


def main():
    parser = argparse.ArgumentParser(description="Comprehensive Knowledge Seeder")
    parser.add_argument("--generate", action="store_true", help="Generate content using MLX")
    parser.add_argument("--ingest", action="store_true", help="Ingest generated content into KAS")
    parser.add_argument("--all", action="store_true", help="Generate and ingest")
    parser.add_argument("--list", action="store_true", help="List categories and topics")
    parser.add_argument("--start-from", type=int, default=0, help="Start from topic N")
    parser.add_argument("--batch-size", type=int, default=5, help="Batch size before pause")

    args = parser.parse_args()

    if args.list:
        list_categories()
        return

    if args.generate or args.all:
        asyncio.run(generate_all(batch_size=args.batch_size, start_from=args.start_from))

    if args.ingest or args.all:
        asyncio.run(run_ingestion())

    if not any([args.generate, args.ingest, args.all, args.list]):
        parser.print_help()


if __name__ == "__main__":
    main()
