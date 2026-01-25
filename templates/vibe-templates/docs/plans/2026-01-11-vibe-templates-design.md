# Vibe Templates Design

**Date:** January 11, 2026
**Status:** Approved, implementing

## Overview

A CLI tool (`vibe`) that generates fully-configured projects with CLAUDE.md, Task Master, and template-specific workflows.

## Key Decisions

| Decision | Choice |
|----------|--------|
| Interface | CLI + Claude Code skill wrapper |
| Must-haves | CLAUDE.md (lean) + Task Master |
| Nice-to-haves | Docker, tests, CI/CD (via flags) |
| Location | Auto-detect (ML → ai-tools/, else → personal/) |
| CLAUDE.md philosophy | Minimal; guidance in commands |
| Python tooling | uv (default), pip+venv for simple projects |

## Templates

1. **python-api** - FastAPI + uvicorn + pydantic → `personal/`
2. **python-ml** - MLX + Gradio → `ai-tools/`
3. **nextjs** - Next.js 14 App Router + TypeScript → `personal/`
4. **fullstack** - python-api + nextjs combined → `personal/`

## Project Structure

```
templates/vibe-templates/
├── vibe/
│   ├── __init__.py
│   ├── cli.py
│   ├── generator.py
│   ├── config.py
│   └── templates/
│       ├── base/
│       ├── python-api/
│       ├── python-ml/
│       ├── nextjs/
│       └── fullstack/
├── pyproject.toml
└── README.md
```

## Usage

```bash
vibe new python-api my-backend           # Quick mode
vibe new                                  # Interactive mode
vibe new python-api my-app --docker       # With optional features
```

## Generated Output

```
~/claude-code/personal/my-backend/
├── CLAUDE.md
├── .taskmaster/
├── .claude/commands/
├── src/
├── pyproject.toml
└── .gitignore
```
