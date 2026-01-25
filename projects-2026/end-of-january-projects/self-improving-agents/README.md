# SIA - Self-Improving Agents Framework

A production-grade framework for building AI agents that improve themselves through code self-modification, skill accumulation, and prompt optimization.

## Features

- **Code Self-Modification** (Gödel Agent style): Agents can modify their own code at runtime with sandboxed validation and automatic rollback
- **Skill Accumulation** (Voyager-style): Discover, store, and compose reusable skills from successful executions
- **Prompt Optimization** (DSPy MIPROv2/SIMBA): Automatic prompt improvement using bootstrapping and Bayesian optimization

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Ollama with models: `qwen2.5:7b`, `nomic-embed-text:v1.5`

### Installation

```bash
# Clone the repository
cd self-improving-agents

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env

# Start database
docker compose -f docker/docker-compose.yml up -d

# Initialize database
sia db init

# Verify installation
sia db health
```

### Basic Usage

```bash
# Run an agent with a task
sia agent run decomposer "Break down the task of building a REST API"

# Search skills
sia skill search "web scraping"

# Start optimization run
sia optimize run researcher

# Start API server
sia api serve
```

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     SELF-IMPROVING AGENTS FRAMEWORK                       │
├──────────────────────────────────────────────────────────────────────────┤
│  User Interfaces: CLI | REST API | SDK | Dashboard                       │
├──────────────────────────────────────────────────────────────────────────┤
│  Agent Execution Layer: Single-Agent | Multi-Agent | Workflow            │
├──────────────────────────────────────────────────────────────────────────┤
│  Self-Improvement: Code Evolution | Skill Learning | Prompt Optimization │
├──────────────────────────────────────────────────────────────────────────┤
│  Memory System: Episodic | Semantic | Procedural (PostgreSQL + pgvector) │
├──────────────────────────────────────────────────────────────────────────┤
│  Evaluation: Metrics | Benchmarks | Feedback | Decision Engine           │
├──────────────────────────────────────────────────────────────────────────┤
│  LLM Layer: Ollama (local) → OpenRouter → DeepSeek → Claude (fallback)   │
└──────────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
src/sia/
├── agents/         # Agent definitions and executor
├── api/            # FastAPI REST API
├── cli/            # Typer CLI commands
├── config.py       # Configuration management
├── coordination/   # Multi-agent coordination
├── crud/           # Database CRUD operations
├── db/             # Database connection and utilities
├── evaluation/     # Metrics and benchmarking
├── evolution/      # Code self-modification (Gödel Agent)
├── feedback/       # Human and automated feedback
├── llm/            # LLM router and utilities
├── memory/         # Memory system (episodic, semantic, procedural)
├── models/         # SQLAlchemy models
├── monitoring/     # Prometheus metrics, Langfuse
├── optimization/   # DSPy prompt optimization
├── schemas/        # Pydantic schemas
├── sdk/            # Python SDK
└── skills/         # Skill discovery, storage, composition
```

## Configuration

All configuration is done via environment variables. See `.env.example` for available options.

Key settings:
- `SIA_DATABASE_URL`: PostgreSQL connection string
- `SIA_OLLAMA_BASE_URL`: Ollama API endpoint
- `SIA_OLLAMA_MODEL`: Default LLM model

## Development

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=sia

# Type checking
mypy src/sia

# Linting
ruff check src/sia

# Format code
ruff format src/sia
```

## License

MIT
