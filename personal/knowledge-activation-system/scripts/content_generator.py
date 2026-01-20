#!/usr/bin/env python3
"""Comprehensive content generator for KAS using Ollama."""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path

import httpx

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:14b"
OBSIDIAN_BASE = Path.home() / "Obsidian" / "Knowledge" / "Notes"

# Content categories with topics
CONTENT_PLAN = {
    "agents": {
        "namespace": "agents",
        "topics": [
            ("AI Agent Fundamentals", "What are AI agents, how they work, and core concepts"),
            ("ReAct Pattern for Agents", "Reason-Act-Observe loop, implementation, examples"),
            ("LangGraph State Management", "Building stateful agents with LangGraph"),
            ("Tool Use with Claude", "Implementing tool calling with Anthropic Claude API"),
            ("Agent Memory Systems", "Short-term and long-term memory for AI agents"),
            ("Multi-Agent Orchestration", "Coordinating multiple agents, communication patterns"),
            ("CrewAI Framework Guide", "Building agent crews with CrewAI"),
            ("AutoGen Multi-Agent Systems", "Microsoft AutoGen for agent collaboration"),
            ("Agent Planning Strategies", "Task decomposition, goal-oriented planning"),
            ("Agent Error Handling", "Recovery strategies, fallbacks, graceful degradation"),
            ("Autonomous Coding Agents", "Code generation agents, Devin-style systems"),
            ("Agent Evaluation Methods", "Measuring agent performance and reliability"),
            ("Agent Security Considerations", "Sandboxing, permission management, safety"),
            ("LangChain Agents Deep Dive", "Agent types, tools, and execution in LangChain"),
            ("Function Calling Patterns", "OpenAI and Anthropic function calling best practices"),
            ("Agent Debugging Techniques", "Tracing, logging, and debugging agent behavior"),
            ("Reflexion and Self-Improvement", "Agents that learn from mistakes"),
            ("Agent Benchmarks", "AgentBench, WebArena, and evaluation frameworks"),
            ("Building Custom Agent Tools", "Creating tools for agent use"),
            ("Agent Deployment Patterns", "Production deployment of AI agents"),
        ]
    },
    "devops": {
        "namespace": "devops",
        "topics": [
            ("CI/CD Pipeline Fundamentals", "Continuous integration and deployment basics"),
            ("GitHub Actions Complete Guide", "Workflows, actions, secrets, and best practices"),
            ("GitLab CI/CD Tutorial", "Pipeline configuration and GitLab runners"),
            ("Docker Best Practices", "Image optimization, multi-stage builds, security"),
            ("Kubernetes Deployment Strategies", "Rolling updates, blue-green, canary deployments"),
            ("Infrastructure as Code with Terraform", "IaC fundamentals and Terraform usage"),
            ("Ansible Automation Guide", "Configuration management and playbooks"),
            ("Monitoring with Prometheus", "Metrics collection, alerting, and dashboards"),
            ("Grafana Dashboard Design", "Visualization best practices for observability"),
            ("Log Management with ELK", "Elasticsearch, Logstash, Kibana stack"),
            ("Container Security Scanning", "Trivy, Snyk, and vulnerability management"),
            ("Secrets Management", "HashiCorp Vault, AWS Secrets Manager, best practices"),
            ("ArgoCD GitOps Workflow", "Declarative continuous delivery for Kubernetes"),
            ("Helm Charts Development", "Kubernetes package management"),
            ("Service Mesh with Istio", "Traffic management, security, observability"),
            ("Cloud Cost Optimization", "AWS, GCP, Azure cost management strategies"),
            ("Incident Response Playbooks", "On-call practices and incident management"),
            ("SRE Practices Guide", "Site reliability engineering fundamentals"),
            ("Feature Flags Implementation", "LaunchDarkly, feature toggles, progressive rollout"),
            ("Database DevOps", "Schema migrations, backup strategies, DR planning"),
        ]
    },
    "optimization": {
        "namespace": "optimization",
        "topics": [
            ("Database Query Optimization", "Index strategies, query planning, EXPLAIN analysis"),
            ("Python Performance Tuning", "Profiling, optimization techniques, async patterns"),
            ("API Response Time Optimization", "Caching, pagination, lazy loading"),
            ("Search Performance Tuning", "Index optimization, query caching, relevance tuning"),
            ("Memory Optimization Techniques", "Memory profiling, leak detection, efficient data structures"),
            ("Caching Strategies", "Redis, Memcached, CDN, cache invalidation patterns"),
            ("Load Balancing Patterns", "Algorithms, health checks, session persistence"),
            ("Connection Pooling", "Database and HTTP connection management"),
            ("Batch Processing Optimization", "Chunking, parallel processing, queue management"),
            ("Frontend Performance", "Core Web Vitals, bundle optimization, lazy loading"),
            ("Image Optimization", "Compression, responsive images, WebP/AVIF"),
            ("Network Optimization", "HTTP/2, compression, connection reuse"),
            ("Serverless Cold Start Mitigation", "Warm-up strategies, provisioned concurrency"),
            ("Database Sharding Strategies", "Horizontal scaling, partition strategies"),
            ("Read Replica Optimization", "Read scaling, consistency considerations"),
            ("Async Processing Patterns", "Message queues, background jobs, event-driven"),
            ("GraphQL Performance", "N+1 problem, DataLoader, query complexity"),
            ("Microservices Performance", "Service mesh optimization, gRPC, circuit breakers"),
            ("ML Model Inference Optimization", "Quantization, batching, hardware acceleration"),
            ("Full-Text Search Optimization", "Elasticsearch, PostgreSQL FTS tuning"),
        ]
    },
    "tools": {
        "namespace": "tools",
        "topics": [
            ("Ollama Complete Guide", "Local LLM deployment, model management, API usage"),
            ("Embedding Models Comparison", "nomic-embed, bge, e5, performance comparison"),
            ("Vector Database Selection", "pgvector, Pinecone, Weaviate, Chroma comparison"),
            ("LLM Development Tools", "LangSmith, Weights & Biases, evaluation tools"),
            ("Code Editor AI Integration", "Copilot, Cursor, Claude Code setup"),
            ("Terminal Productivity Tools", "zsh, tmux, fzf, modern CLI tools"),
            ("Git Advanced Workflows", "Rebase, cherry-pick, bisect, hooks"),
            ("Docker Compose Patterns", "Multi-service development, networking, volumes"),
            ("Postman API Testing", "Collections, environments, automated testing"),
            ("HTTPie and curl Guide", "HTTP client tools for API development"),
            ("jq JSON Processing", "Command-line JSON manipulation"),
            ("VS Code Extensions for AI Dev", "Essential extensions for AI/ML development"),
            ("Jupyter Lab Setup", "Extensions, kernels, collaboration features"),
            ("MLflow Experiment Tracking", "Model versioning, metrics, artifacts"),
            ("DVC Data Version Control", "Dataset versioning, pipelines, remote storage"),
            ("Hugging Face Hub Guide", "Model sharing, datasets, spaces"),
            ("Weights and Biases Guide", "Experiment tracking, hyperparameter sweeps"),
            ("Streamlit App Development", "Building data apps and demos"),
            ("Gradio Interface Creation", "ML model demos and interfaces"),
            ("LiteLLM Proxy Guide", "Universal LLM API proxy setup"),
        ]
    },
    "testing": {
        "namespace": "testing",
        "topics": [
            ("pytest Advanced Patterns", "Fixtures, parametrization, plugins"),
            ("Test-Driven Development Guide", "TDD workflow, red-green-refactor"),
            ("API Testing Strategies", "Integration tests, contract testing, mocking"),
            ("Load Testing with Locust", "Performance testing, distributed load testing"),
            ("E2E Testing with Playwright", "Browser automation, visual regression"),
            ("Unit Testing Best Practices", "Isolation, mocking, assertion patterns"),
            ("Test Coverage Analysis", "Coverage tools, metrics, coverage goals"),
            ("Mutation Testing Guide", "Quality assessment with mutation testing"),
            ("Property-Based Testing", "Hypothesis library, generative testing"),
            ("Snapshot Testing", "Jest snapshots, pytest-snapshot, when to use"),
            ("Mocking External Services", "VCR, responses, httpx mock"),
            ("Database Testing Patterns", "Test databases, fixtures, factories"),
            ("CI Test Optimization", "Parallel testing, test splitting, caching"),
            ("Flaky Test Detection", "Identifying and fixing unreliable tests"),
            ("Security Testing Basics", "SAST, DAST, dependency scanning"),
            ("Accessibility Testing", "a11y testing tools and automation"),
            ("Performance Testing Metrics", "Latency, throughput, percentiles"),
            ("Chaos Engineering Intro", "Fault injection, resilience testing"),
            ("Contract Testing with Pact", "Consumer-driven contract testing"),
            ("Test Data Management", "Factories, fixtures, synthetic data"),
        ]
    },
    "ai-ml": {
        "namespace": "ai-ml",
        "topics": [
            ("Embedding Models Deep Dive", "Architecture, training, use cases"),
            ("Fine-Tuning LLMs Guide", "LoRA, QLoRA, full fine-tuning strategies"),
            ("Chain-of-Thought Prompting", "CoT techniques, examples, when to use"),
            ("Prompt Engineering Patterns", "System prompts, few-shot, structured output"),
            ("Vector Search Algorithms", "HNSW, IVF, product quantization"),
            ("Semantic Chunking Strategies", "Chunk size, overlap, content-aware splitting"),
            ("LLM Output Parsing", "Structured extraction, JSON mode, function calling"),
            ("Retrieval Strategies for RAG", "Dense, sparse, hybrid retrieval"),
            ("Context Window Management", "Long context handling, summarization"),
            ("LLM Caching Strategies", "Semantic cache, prompt cache, KV cache"),
            ("Model Quantization Guide", "GGUF, AWQ, GPTQ, performance tradeoffs"),
            ("Local LLM Deployment", "Ollama, llama.cpp, vLLM comparison"),
            ("Multimodal AI Systems", "Vision-language models, image understanding"),
            ("AI Safety and Alignment", "RLHF, constitutional AI, safety measures"),
            ("Evaluation Metrics for LLMs", "Perplexity, BLEU, human evaluation"),
            ("Agentic RAG Patterns", "Self-RAG, corrective RAG, adaptive retrieval"),
            ("Knowledge Graph for RAG", "Entity extraction, graph-enhanced retrieval"),
            ("Reranking Models Guide", "Cross-encoders, ColBERT, reranking strategies"),
            ("LLM Hallucination Mitigation", "Grounding, verification, confidence scoring"),
            ("Synthetic Data Generation", "Using LLMs to generate training data"),
        ]
    },
}

ARTICLE_PROMPT = """Write a comprehensive technical guide about: {title}

Context: {description}

Requirements:
1. Write 800-1200 words of substantive technical content
2. Include practical code examples where relevant
3. Use clear headings and structure
4. Include best practices and common pitfalls
5. Be specific and actionable, not generic
6. Target an intermediate developer audience

Format the response as a complete markdown article with:
- A clear introduction explaining the topic
- Main content with code examples
- Best practices section
- Common mistakes to avoid
- Conclusion with key takeaways

Do NOT include YAML frontmatter - just the article content starting with the main heading."""


async def generate_article(client: httpx.AsyncClient, title: str, description: str) -> str:
    """Generate a single article using Ollama."""
    prompt = ARTICLE_PROMPT.format(title=title, description=description)

    response = await client.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 2000,
            }
        },
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json()["response"]


def create_frontmatter(title: str, namespace: str, tags: list[str]) -> str:
    """Create YAML frontmatter for the article."""
    tag_str = "\n".join(f"  - {tag}" for tag in tags)
    return f"""---
title: "{title}"
namespace: {namespace}
tags:
{tag_str}
created: {datetime.now().strftime("%Y-%m-%d")}
type: guide
---

"""


def title_to_filename(title: str) -> str:
    """Convert title to a valid filename."""
    # Remove special characters, replace spaces with hyphens
    filename = re.sub(r'[^\w\s-]', '', title.lower())
    filename = re.sub(r'[\s_]+', '-', filename)
    return filename + ".md"


def extract_tags(title: str, description: str, namespace: str) -> list[str]:
    """Extract relevant tags from title and description."""
    # Common words to filter out
    stopwords = {'a', 'an', 'the', 'and', 'or', 'for', 'to', 'in', 'with', 'of', 'on', 'is', 'how', 'what', 'guide', 'complete', 'deep', 'dive', 'tutorial', 'introduction', 'basics', 'fundamentals'}

    # Extract words from title
    words = re.findall(r'\b[a-z]+\b', title.lower())
    tags = [w for w in words if w not in stopwords and len(w) > 2]

    # Add namespace as tag
    tags.append(namespace)

    # Limit to 8 tags
    return list(dict.fromkeys(tags))[:8]


async def generate_category(category: str, config: dict, start_idx: int = 0) -> int:
    """Generate all articles for a category."""
    namespace = config["namespace"]
    topics = config["topics"]

    # Create output directory
    output_dir = OBSIDIAN_BASE / category
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Generating {len(topics)} articles for: {category}")
    print(f"Output: {output_dir}")
    print(f"{'='*60}")

    generated = 0

    async with httpx.AsyncClient() as client:
        for i, (title, description) in enumerate(topics[start_idx:], start=start_idx + 1):
            filename = title_to_filename(title)
            filepath = output_dir / filename

            # Skip if already exists
            if filepath.exists():
                print(f"  [{i}/{len(topics)}] SKIP (exists): {title}")
                continue

            print(f"  [{i}/{len(topics)}] Generating: {title}...")

            try:
                content = await generate_article(client, title, description)
                tags = extract_tags(title, description, namespace)
                frontmatter = create_frontmatter(title, namespace, tags)

                # Write file
                filepath.write_text(frontmatter + content)
                generated += 1
                print(f"           ✓ Saved: {filename}")

            except Exception as e:
                print(f"           ✗ Error: {e}")
                continue

            # Small delay to avoid overwhelming Ollama
            await asyncio.sleep(1)

    return generated


async def main():
    """Generate all content."""
    print("="*60)
    print("KAS Comprehensive Content Generator")
    print(f"Model: {MODEL}")
    print(f"Output: {OBSIDIAN_BASE}")
    print("="*60)

    total_generated = 0

    for category, config in CONTENT_PLAN.items():
        generated = await generate_category(category, config)
        total_generated += generated

    print(f"\n{'='*60}")
    print(f"COMPLETE: Generated {total_generated} new articles")
    print("="*60)
    print("\nNext steps:")
    print("1. Review generated content in Obsidian")
    print("2. Ingest into KAS:")
    print(f"   uv run python cli.py ingest directory ~/Obsidian/Knowledge/Notes --recursive")
    print("3. Run evaluation:")
    print("   uv run python evaluation/evaluate.py")


if __name__ == "__main__":
    asyncio.run(main())
