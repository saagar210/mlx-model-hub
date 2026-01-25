# SIA - Self-Improving Agents Framework

## Project Overview
Production-grade framework for AI agents that improve through code self-modification, skill accumulation, and prompt optimization.

## Tech Stack
- Python 3.11+, FastAPI, Typer
- PostgreSQL 16 + pgvector + pgvectorscale
- DSPy for prompt optimization
- Ollama (local LLM), OpenRouter/DeepSeek/Claude (cloud fallback)

## Key Commands
```bash
# Database
sia db init          # Initialize database schema
sia db health        # Check database connection

# Agents
sia agent run <name> <task>   # Execute agent
sia agent list                # List available agents

# Skills
sia skill search <query>      # Search skill library
sia skill list                # List all skills

# Optimization
sia optimize run <agent>      # Start DSPy optimization

# API
sia api serve                 # Start REST API server
```

## Architecture Principles
1. **Memory-first**: All executions traced to episodic memory
2. **Fail-safe evolution**: Sandboxed code mutations with auto-rollback
3. **Local-first LLM**: Prefer Ollama, escalate to cloud on failure
4. **Skill reuse**: Extract and compose skills from successful runs

## File Conventions
- Models: `src/sia/models/<entity>.py`
- Schemas: `src/sia/schemas/<entity>.py`
- CRUD: `src/sia/crud/<entity>.py`
- API routes: `src/sia/api/routes/<entity>.py`

## Testing
```bash
pytest                    # Run all tests
pytest tests/test_db.py   # Run specific test file
pytest -k "agent"         # Run tests matching pattern
```

## Database
- PostgreSQL on localhost:5432
- Use `docker compose -f docker/docker-compose.yml up -d` to start
- Schema in `docker/postgres/init.sql`
